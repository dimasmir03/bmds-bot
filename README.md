# BMDS Bot

Асинхронный backend Telegram-бота-стилиста: пользователь присылает своё фото и описывает
одежду, бот возвращает фото этого человека в новом образе. Редактирование выполняет локальная
модель [FLUX.2 klein 9B](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B)
(`IMAGE_PROVIDER=flux2_klein`). Для разработки без GPU остаётся `MockImageEditorProvider`
(`IMAGE_PROVIDER=mock`): он имитирует задержку и возвращает копию исходного файла.

## Архитектура

```text
Telegram → handlers/FSM → JobService → PostgreSQL → Redis queue
                                                  ↓
Telegram ← result notification ← Worker ← ImageEditorProvider ← Storage
```

Telegram-слой зависит только от `JobService`. Worker получает provider через фабрику, а
`ImageEditorProvider` является границей между backend и будущим AI engine. Поэтому local
GPU-модель, внешний HTTP API или ComfyUI можно подключить без изменения handlers и очереди.

Подробности и диаграмма: [docs/architecture.md](docs/architecture.md).

## Быстрый запуск через Docker Compose

Нужны Docker с Compose plugin и токен Telegram-бота.

1. Создайте бота у [@BotFather](https://t.me/BotFather) командой `/newbot` и сохраните токен.
2. Скопируйте конфигурацию:

   ```bash
   cp .env.example .env
   ```

3. Заполните `TELEGRAM_BOT_TOKEN`, замените `ADMIN_API_KEY` и при необходимости пароль
   PostgreSQL одновременно в `POSTGRES_PASSWORD` и `DATABASE_URL`.
4. Запустите весь stack:

   ```bash
   docker compose up --build -d
   docker compose ps
   docker compose logs -f bot worker
   ```

Сервис `migrate` автоматически выполняет `alembic upgrade head`. После его успешного
завершения запускаются `api`, `bot` и `worker`. Остановить stack:

```bash
docker compose down
```

Чтобы удалить также БД, Redis и изображения, явно выполните `docker compose down -v`.

## Запуск с моделью FLUX.2 klein (GPU)

Требования:

- NVIDIA GPU: для 9B в bf16 ~29 ГБ VRAM; на картах меньше включите квантизацию
  (`MODEL_QUANTIZATION=8bit|4bit`) и/или `MODEL_CPU_OFFLOAD=true`. Для 8 ГБ VRAM / 16 ГБ RAM
  используйте профиль из `.env.example`: `FLUX.2-klein-4B` + `MODEL_QUANTIZATION=4bit` +
  `MODEL_MAX_IMAGE_SIDE=768` (~5–6 ГБ VRAM);
- на Windows: Docker Desktop с WSL 2 и лимит памяти WSL в `%USERPROFILE%\.wslconfig`
  (`memory=12GB`), иначе WSL получает только половину RAM;
- CUDA-сборка torch задаётся `TORCH_INDEX_URL` (по умолчанию `cu128`); если драйвер старый и
  torch не видит GPU, обновите драйвер NVIDIA или соберите с
  `TORCH_INDEX_URL=https://download.pytorch.org/whl/cu126`;
- на хосте установлены драйвер NVIDIA и `nvidia-container-toolkit` (`nvidia-smi` работает
  внутри `docker run --gpus all ...`);
- ~40 ГБ диска под веса модели;
- 9B — gated: примите условия на странице модели и создайте read-токен Hugging Face
  (4B открыта, токен не обязателен).

В `.env` задайте:

```bash
IMAGE_PROVIDER=flux2_klein
HF_TOKEN=hf_...
```

Запуск с GPU-override (worker собирается из target `worker` с torch/diffusers, получает GPU и
volume `hf_cache` для весов):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
docker compose logs -f worker
```

При первом старте worker скачивает веса в `hf_cache` и загружает модель до того, как начнёт
брать задачи из очереди (в логах `status=loading` → `status=loaded`). Модель загружается
один раз на процесс и общая для всех consumer loops; инференс на GPU выполняется строго по
одной задаче.

Pipeline provider-а (`app/providers/image_editor/flux2_klein.py`):

1. открыть фото, применить EXIF-поворот, перевести в RGB;
2. масштабировать так, чтобы длинная сторона стала `MODEL_MAX_IMAGE_SIDE`, с сохранением
   пропорций и размерами, кратными 16;
3. обернуть запрос пользователя в `MODEL_PROMPT_TEMPLATE` (меняется только одежда, лицо,
   поза и фон сохраняются);
4. вызвать `Flux2KleinPipeline(image=..., prompt=..., num_inference_steps=4, guidance_scale=1.0)`;
5. сохранить результат в формате исходного файла. CUDA OOM завершает job как `FAILED`.

Лицензия FLUX.2 klein 9B — FLUX Non-Commercial: только некоммерческое использование. Для
коммерческого варианта можно указать `HF_MODEL_ID=black-forest-labs/FLUX.2-klein-4B`
(Apache 2.0).

## Проверка API

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/api/jobs/JOB_UUID
```

`/health` проверяет процесс API, `/ready` — соединения с PostgreSQL и Redis. Endpoint job
закрыт внутренним ключом и не отдаётся публично без `X-API-Key`.

## Пользовательский сценарий

- `/start` — начать и получить инструкцию;
- отправить своё фото (Telegram `photo` или документ JPEG/PNG/WEBP/HEIC, лучше в полный рост
  и документом — без сжатия Telegram). HEIC (iPhone) сразу конвертируется в JPEG в
  `StorageService`, дальше pipeline работает только с JPEG/PNG/WEBP;
- описать одежду, например «чёрный классический костюм» — отдельным сообщением или сразу
  подписью к фото (тогда job создаётся без дополнительного шага). Новое фото принимается в
  любой момент и начинает новую примерку, а новое описание после результата примеряет другой
  образ на то же фото. Результат приходит картинкой в чат (при ошибке — файлом);
- `/status` — посмотреть последнюю задачу;
- `/cancel` — сбросить FSM, отменить queued job или запросить отмену processing job.

Handler сохраняет безопасный UUID-файл, создаёт job и кладёт только его UUID в Redis.
Worker меняет статус на `PROCESSING`, вызывает provider, сохраняет output, переводит job
в `COMPLETED` и отправляет документ пользователю. Для processing job отмена ставит
`cancel_requested`; provider завершается, но результат пользователю не отправляется.

## Переменные окружения

| Переменная | Назначение | Пример/значение по умолчанию |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен BotFather | обязательно |
| `DATABASE_URL` | SQLAlchemy async URL | `postgresql+asyncpg://...` |
| `POSTGRES_PASSWORD` | Пароль контейнера PostgreSQL | `bmds` |
| `REDIS_URL` | Redis для queue, FSM и rate limit | `redis://redis:6379/0` |
| `ADMIN_API_KEY` | Ключ внутреннего API | заменить |
| `IMAGE_PROVIDER` | Provider: `mock` или `flux2_klein` | `mock` |
| `STORAGE_ROOT` | Корень input/output/temp | `/app/storage` |
| `MAX_IMAGE_SIZE_MB` | Максимальный размер файла | `20` |
| `LOG_LEVEL` | Уровень логов | `INFO` |
| `MOCK_PROCESSING_DELAY_SECONDS` | Задержка mock | `2` |
| `MAX_CONCURRENT_JOBS` | Число consumer loops worker | `1` |
| `RATE_LIMIT_JOBS` | Job на одно окно | `5` |
| `RATE_LIMIT_WINDOW_SECONDS` | Длина окна rate limit | `60` |
| `REDIS_QUEUE_NAME` | Имя Redis list | `image_jobs` |
| `HF_TOKEN` | Read-токен Hugging Face (модель gated) | для `flux2_klein` |
| `HF_MODEL_ID` | Модель на Hugging Face | `black-forest-labs/FLUX.2-klein-9B` |
| `MODEL_DEVICE` | Устройство инференса | `cuda` |
| `MODEL_CPU_OFFLOAD` | Выгрузка частей модели в RAM при нехватке VRAM | `false` |
| `MODEL_QUANTIZATION` | `none`, `8bit`, `4bit` (bitsandbytes, transformer + text encoder) | `none` |
| `MODEL_NUM_INFERENCE_STEPS` | Шаги диффузии (klein дистиллирована под 4) | `4` |
| `MODEL_GUIDANCE_SCALE` | Guidance scale | `1.0` |
| `MODEL_MAX_IMAGE_SIDE` | Длинная сторона изображения для модели | `1024` |
| `MODEL_SEED` | Фиксированный seed; пусто — случайный | не задан |
| `MODEL_PROMPT_TEMPLATE` | Шаблон промпта, обязательно содержит `{request}` | см. `app/core/config.py` |

Секреты не коммитятся: `.env` находится в `.gitignore`.

## Локальная разработка

Проект требует Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
docker compose up -d postgres redis
alembic upgrade head
python -m app.bot.bot
python -m app.worker.worker
uvicorn app.api.app:app --reload
```

Отдельный worker запускается командой `python -m app.worker.worker`. Его concurrency
определяет `MAX_CONCURRENT_JOBS`; для одной GPU по умолчанию используется `1`.

Проверки:

```bash
ruff check .
ruff format --check .
pytest
```

## Добавление AI provider

Пример реального provider-а — `app/providers/image_editor/flux2_klein.py`.

1. Создайте, например, `app/providers/image_editor/local_model.py`.
2. Реализуйте `ImageEditorProvider.edit(...)` и верните `ImageEditResult` с одним или
   несколькими `ImageOutput`. Тяжёлую загрузку (веса модели) делайте в `startup()`: worker
   вызывает его один раз до начала обработки очереди.
3. Зарегистрируйте provider в `factory.py`. Тяжёлые зависимости импортируйте внутри ветки
   фабрики, чтобы `api` и `bot` не требовали torch.
4. Установите `IMAGE_PROVIDER=local`.

Provider может работать в процессе, обращаться к удалённому HTTP API, использовать GPU,
выполняться несколько минут и возвращать несколько вариантов. Telegram handlers при этом
не меняются. Для HTTP-варианта используйте async `httpx.AsyncClient` с явными timeout.

## Redis queue и восстановление

Очередь инкапсулирована протоколом `JobQueue`; текущая реализация использует `RPUSH/BLPOP`.
Повторно полученная завершённая, отменённая или failed job не обрабатывается. Это простая
очередь для текущего этапа: для строгой гарантии доставки после падения worker можно позже
заменить реализацию на Redis Streams или processing-list, не меняя `JobService`.

## Миграции

```bash
alembic upgrade head
alembic revision --autogenerate -m "describe change"
alembic downgrade -1
```

## Структура

```text
app/
  api/                  FastAPI и внутренние routes
  bot/                  aiogram, FSM и handlers
  core/                 config и logging
  db/models/            SQLAlchemy entities
  db/repositories/      доступ к данным
  providers/image_editor/ provider contract, mock и factory
  queue/                абстракция и Redis implementation
  services/             business logic, storage, rate limit
  worker/               consumer и job processor
alembic/                 миграции
deploy/ansible/          опциональный deployment
docs/                    архитектурная документация
storage/                 локальные input/output/temp
tests/                   unit/integration tests без Telegram API
```

## Ansible (опционально)

Скопируйте `inventory.example.ini` и `group_vars/all.example.yml`, сохраните секреты через
`ansible-vault`, установите collection и запустите:

```bash
cd deploy/ansible
ansible-galaxy collection install -r requirements.yml
ansible-playbook playbook.yml --ask-vault-pass
```

Playbook рассчитан на Debian/Ubuntu, устанавливает Docker/Git, checkout-ит Git-репозиторий,
создаёт `.env` с mode `0600` и запускает Compose. При `nvidia_gpu: true` он проверяет драйвер
(`nvidia-smi`), устанавливает `nvidia-container-toolkit`, настраивает Docker runtime и
запускает Compose вместе с `docker-compose.gpu.yml`. Драйвер NVIDIA playbook не ставит — он
должен быть на хосте заранее. `hf_token` храните в `ansible-vault`.

## Git и публикация

Репозиторий уже инициализирован с веткой `main`. После создания пустого remote:

```bash
git remote add origin git@github.com:YOUR_USER/bmds-bot.git
git push -u origin main
```


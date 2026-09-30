# BMDS Bot

Асинхронный backend Telegram-бота для редактирования изображений. Сейчас весь pipeline
работает с `MockImageEditorProvider`: он имитирует задержку и возвращает копию исходного
файла. Реальная AI-модель намеренно не подключена.

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
- отправить Telegram `photo` или документ JPEG/PNG/WEBP;
- отправить текст изменения;
- `/status` — посмотреть последнюю задачу;
- `/cancel` — сбросить FSM, отменить queued job или запросить отмену processing job.

Handler сохраняет безопасный UUID-файл, создаёт job и кладёт только его UUID в Redis.
Worker меняет статус на `PROCESSING`, вызывает mock provider, сохраняет output, переводит job
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
| `IMAGE_PROVIDER` | Provider, сейчас только `mock` | `mock` |
| `STORAGE_ROOT` | Корень input/output/temp | `/app/storage` |
| `MAX_IMAGE_SIZE_MB` | Максимальный размер файла | `20` |
| `LOG_LEVEL` | Уровень логов | `INFO` |
| `MOCK_PROCESSING_DELAY_SECONDS` | Задержка mock | `2` |
| `MAX_CONCURRENT_JOBS` | Число consumer loops worker | `1` |
| `RATE_LIMIT_JOBS` | Job на одно окно | `5` |
| `RATE_LIMIT_WINDOW_SECONDS` | Длина окна rate limit | `60` |
| `REDIS_QUEUE_NAME` | Имя Redis list | `image_jobs` |

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

1. Создайте, например, `app/providers/image_editor/local_model.py`.
2. Реализуйте `ImageEditorProvider.edit(...)` и верните `ImageEditResult` с одним или
   несколькими `ImageOutput`.
3. Зарегистрируйте provider в `factory.py`.
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
создаёт `.env` с mode `0600` и запускает Compose.

## Git и публикация

Репозиторий уже инициализирован с веткой `main`. После создания пустого remote:

```bash
git remote add origin git@github.com:YOUR_USER/bmds-bot.git
git push -u origin main
```


import asyncio
import logging
import signal

from aiogram import Bot
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import session_factory
from app.providers.image_editor.base import ImageEditorProvider
from app.providers.image_editor.factory import create_image_editor_provider
from app.queue.redis_queue import RedisJobQueue
from app.services.image_service import ImageService
from app.services.storage_service import StorageService
from app.worker.processor import JobProcessor

logger = logging.getLogger(__name__)


async def run_worker(
    worker_number: int,
    queue: RedisJobQueue,
    bot: Bot,
    provider: ImageEditorProvider,
    stop_event: asyncio.Event,
) -> None:
    settings = get_settings()
    storage = StorageService(settings.storage_root, settings.max_image_size_bytes)
    logger.info("worker=%s status=started provider=%s", worker_number, provider.name)
    while not stop_event.is_set():
        job_id = await queue.dequeue(wait_seconds=5)
        if job_id is None:
            continue
        async with session_factory() as session:
            processor = JobProcessor(session, ImageService(storage, provider), bot)
            await processor.process(job_id)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    redis = Redis.from_url(settings.redis_url)
    queue = RedisJobQueue(redis, settings.redis_queue_name)
    bot = Bot(settings.telegram_bot_token)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass
    # A single provider per process: the model is loaded once and shared by all loops.
    provider = create_image_editor_provider(settings)
    await provider.startup()
    tasks = [
        asyncio.create_task(run_worker(number, queue, bot, provider, stop_event))
        for number in range(1, settings.max_concurrent_jobs + 1)
    ]
    try:
        await stop_event.wait()
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await queue.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

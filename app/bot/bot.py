import asyncio

from aiogram import Bot
from redis.asyncio import Redis

from app.bot.dispatcher import create_dispatcher
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import session_factory
from app.queue.redis_queue import RedisJobQueue
from app.services.rate_limiter import RateLimiter
from app.services.storage_service import StorageService


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    redis = Redis.from_url(settings.redis_url)
    bot = Bot(settings.telegram_bot_token)
    dispatcher = create_dispatcher(redis)
    queue = RedisJobQueue(redis, settings.redis_queue_name)
    try:
        await dispatcher.start_polling(
            bot,
            settings=settings,
            storage_service=StorageService(settings.storage_root, settings.max_image_size_bytes),
            session_factory=session_factory,
            job_queue=queue,
            rate_limiter=RateLimiter(
                redis, settings.rate_limit_jobs, settings.rate_limit_window_seconds
            ),
        )
    finally:
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

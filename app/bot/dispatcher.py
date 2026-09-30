from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.bot.handlers import cancel, image, jobs, start


def create_dispatcher(redis: Redis) -> Dispatcher:
    dispatcher = Dispatcher(storage=RedisStorage(redis=redis))
    dispatcher.include_routers(start.router, cancel.router, jobs.router, image.router)
    return dispatcher

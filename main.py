from __future__ import annotations

import asyncio
import logging
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot import db
from bot.config import config
from bot.handlers import admin, client, common
from bot.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("nexoda")


SETUP_HELP = """
============================================================
  Бот не запущен: не указан токен.
============================================================
Что нужно сделать (один раз, 2 минуты):

1) Открой Telegram, найди @BotFather и отправь /newbot.
   Придумай имя и @username бота — получишь ТОКЕН
   (выглядит так: 1234567890:AAE...).

2) В папке проекта скопируй файл .env.example в .env
   и впиши токен в строку BOT_TOKEN=...

3) Узнай свой Telegram ID: запусти бота, напиши ему /id,
   и впиши число в строку ADMIN_IDS=... в файле .env.

4) Запусти снова:  python main.py
============================================================
"""


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="id", description="Мой Telegram ID"),
            BotCommand(command="admin", description="Панель владельца"),
        ]
    )


async def main() -> None:
    if not config.bot_token:
        print(SETUP_HELP)
        return

    await db.init_db()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: админка перехватывает свои апдейты первой.
    dp.include_router(admin.router)
    dp.include_router(client.router)
    dp.include_router(common.router)

    scheduler = setup_scheduler(bot)

    try:
        await set_commands(bot)
        me = await bot.get_me()
        logger.info("Бот запущен: @%s (id %s)", me.username, me.id)
        if not await db.any_admin_exists():
            logger.warning("Владелец не задан. Укажите ADMIN_IDS в .env и перезапустите бота.")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await db.close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановлено.")

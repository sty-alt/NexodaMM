from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .. import db, keyboards as kb, texts

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    name = await db.get_setting("business_name", "Наш салон")
    await message.answer(texts.WELCOME.format(name=name), reply_markup=kb.main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP, reply_markup=kb.main_menu_kb())


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(
        f"🪪 Ваш Telegram ID: <code>{message.from_user.id}</code>\n\n"
        "Чтобы стать владельцем-админом, добавьте этот ID в файл .env (ADMIN_IDS) и перезапустите бота."
    )


@router.message(Command("admin"))
async def cmd_admin_denied(message: Message) -> None:
    await message.answer(texts.ADMIN_DENIED.format(uid=message.from_user.id))

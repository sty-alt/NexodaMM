from __future__ import annotations

from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import db, keyboards as kb, texts
from ..config import config
from ..states import BookingSG
from ..utils import (
    available_slots,
    booking_horizon_dates,
    format_date_full,
    format_price,
    min_to_hhmm,
    today_str,
)

router = Router()


async def notify_admins(bot, text: str) -> None:
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


def valid_phone(text: str) -> bool:
    return sum(c.isdigit() for c in text) >= 7


# ---------------- Старт записи ----------------
@router.message(F.text == kb.BTN_BOOK)
async def start_booking(message: Message, state: FSMContext) -> None:
    await state.clear()
    services = await db.list_services(active_only=True)
    if not services:
        await message.answer(texts.NO_SERVICES)
        return
    await state.set_state(BookingSG.service)
    await message.answer(texts.CHOOSE_SERVICE, reply_markup=kb.services_kb(services))


@router.callback_query(F.data == "bk:cancel")
async def cancel_booking(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Запись отменена. Возвращайтесь, когда будет удобно 🙂")
    await callback.answer()


@router.callback_query(F.data.startswith("bk:svc:"))
async def choose_service(callback: CallbackQuery, state: FSMContext) -> None:
    service_id = int(callback.data.split(":")[2])
    service = await db.get_service(service_id)
    if not service or not service["is_active"]:
        await callback.answer("Услуга недоступна", show_alert=True)
        return
    await state.update_data(
        service_id=service["id"],
        service_name=service["name"],
        price=service["price"],
        duration=service["duration_min"],
    )
    masters = await db.list_masters(active_only=True)
    if not masters:
        await callback.answer("Нет доступных мастеров", show_alert=True)
        return
    if len(masters) == 1:
        m = masters[0]
        await state.update_data(master_id=m["id"], master_name=m["name"])
        await _show_dates(callback, state)
    else:
        await state.set_state(BookingSG.master)
        await callback.message.edit_text(texts.CHOOSE_MASTER, reply_markup=kb.masters_kb(masters))
    await callback.answer()


@router.callback_query(F.data.startswith("bk:mst:"))
async def choose_master(callback: CallbackQuery, state: FSMContext) -> None:
    master_id = int(callback.data.split(":")[2])
    master = await db.get_master(master_id)
    if not master or not master["is_active"]:
        await callback.answer("Мастер недоступен", show_alert=True)
        return
    await state.update_data(master_id=master["id"], master_name=master["name"])
    await _show_dates(callback, state)
    await callback.answer()


async def _show_dates(callback: CallbackQuery, state: FSMContext) -> None:
    dates = await booking_horizon_dates()
    if not dates:
        await callback.message.edit_text(
            "😔 Сейчас нет доступных дат для записи. Загляните позже."
        )
        await state.clear()
        return
    await state.set_state(BookingSG.date)
    await callback.message.edit_text(texts.CHOOSE_DATE, reply_markup=kb.dates_kb(dates))


@router.callback_query(F.data == "bk:back_dates")
async def back_to_dates(callback: CallbackQuery, state: FSMContext) -> None:
    await _show_dates(callback, state)
    await callback.answer()


@router.callback_query(F.data.startswith("bk:date:"))
async def choose_date(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if "master_id" not in data or "duration" not in data:
        await callback.answer("Сессия истекла, начните заново", show_alert=True)
        await state.clear()
        return
    date_str = callback.data.split(":", 2)[2]
    slots = await available_slots(date_str, data["duration"], data["master_id"])
    if not slots:
        await callback.answer(texts.NO_SLOTS, show_alert=True)
        return
    await state.update_data(date=date_str)
    await state.set_state(BookingSG.time)
    d = date.fromisoformat(date_str)
    await callback.message.edit_text(
        f"{texts.CHOOSE_TIME}\n📆 {format_date_full(d)}", reply_markup=kb.times_kb(slots)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bk:time:"))
async def choose_time(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if "date" not in data:
        await callback.answer("Сессия истекла, начните заново", show_alert=True)
        await state.clear()
        return
    start_min = int(callback.data.split(":")[2])
    await state.update_data(start_min=start_min)
    await state.set_state(BookingSG.name)
    await callback.message.edit_text(texts.ENTER_NAME)
    await callback.answer()


@router.message(BookingSG.name, F.text)
async def enter_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if name == kb.BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.main_menu_kb())
        return
    if len(name) < 2:
        await message.answer("Пожалуйста, напишите имя (минимум 2 буквы):")
        return
    await state.update_data(user_name=name)
    await state.set_state(BookingSG.phone)
    await message.answer(texts.ENTER_PHONE, reply_markup=kb.contact_kb())


@router.message(BookingSG.phone, F.contact)
async def enter_phone_contact(message: Message, state: FSMContext) -> None:
    await _save_phone_and_confirm(message, state, message.contact.phone_number)


@router.message(BookingSG.phone, F.text)
async def enter_phone_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text == kb.BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.main_menu_kb())
        return
    if not valid_phone(text):
        await message.answer("Не похоже на номер. Введите телефон или нажмите кнопку ниже:")
        return
    await _save_phone_and_confirm(message, state, text)


async def _save_phone_and_confirm(message: Message, state: FSMContext, phone: str) -> None:
    await state.update_data(phone=phone)
    data = await state.get_data()
    currency = await db.get_setting("currency", "сум")
    d = date.fromisoformat(data["date"])
    summary = (
        "📝 <b>Проверьте запись:</b>\n\n"
        f"💈 Услуга: <b>{data['service_name']}</b>\n"
        f"👤 Мастер: {data['master_name']}\n"
        f"📆 {format_date_full(d)}\n"
        f"🕐 Время: <b>{min_to_hhmm(data['start_min'])}</b>\n"
        f"💰 Цена: {format_price(data['price'], currency)}\n\n"
        f"Имя: {data['user_name']}\n"
        f"Телефон: {phone}\n\n"
        "Всё верно?"
    )
    await state.set_state(BookingSG.confirm)
    await message.answer("Спасибо! 🙌", reply_markup=kb.main_menu_kb())
    await message.answer(summary, reply_markup=kb.confirm_kb())


@router.callback_query(F.data == "bk:confirm")
async def confirm_booking(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    required = {"service_id", "master_id", "date", "start_min", "duration", "user_name", "phone"}
    if not required.issubset(data.keys()):
        await callback.answer("Сессия истекла, начните заново", show_alert=True)
        await state.clear()
        return

    # Повторная проверка, что слот всё ещё свободен
    slots = await available_slots(data["date"], data["duration"], data["master_id"])
    if data["start_min"] not in slots:
        await callback.message.edit_text(
            "😔 К сожалению, это время только что заняли. Пожалуйста, выберите другое — нажмите «📅 Записаться»."
        )
        await state.clear()
        await callback.answer()
        return

    booking_id = await db.add_booking(
        user_id=callback.from_user.id,
        user_name=data["user_name"],
        phone=data["phone"],
        service_id=data["service_id"],
        service_name=data["service_name"],
        price=data["price"],
        master_id=data["master_id"],
        master_name=data["master_name"],
        date=data["date"],
        start_min=data["start_min"],
        duration_min=data["duration"],
    )

    currency = await db.get_setting("currency", "сум")
    d = date.fromisoformat(data["date"])
    user_text = (
        "✅ <b>Готово! Вы записаны.</b>\n\n"
        f"💈 {data['service_name']}\n"
        f"👤 Мастер: {data['master_name']}\n"
        f"📆 {format_date_full(d)} в <b>{min_to_hhmm(data['start_min'])}</b>\n"
        f"💰 {format_price(data['price'], currency)}\n\n"
        "Мы пришлём напоминание перед визитом. "
        "Посмотреть или отменить — «🗓 Мои записи»."
    )
    await callback.message.edit_text(user_text)
    await state.clear()

    username = f"@{callback.from_user.username}" if callback.from_user.username else "—"
    admin_text = (
        f"🔔 <b>Новая запись #{booking_id}</b>\n\n"
        f"💈 {data['service_name']} · {format_price(data['price'], currency)}\n"
        f"👤 Мастер: {data['master_name']}\n"
        f"📆 {format_date_full(d)} в {min_to_hhmm(data['start_min'])}\n\n"
        f"🙋 Клиент: {data['user_name']}\n"
        f"📱 {data['phone']}\n"
        f"💬 {username} (id {callback.from_user.id})"
    )
    await notify_admins(callback.bot, admin_text)
    await callback.answer("Запись создана ✅")


# ---------------- Мои записи ----------------
@router.message(F.text == kb.BTN_MY)
async def my_bookings(message: Message, state: FSMContext) -> None:
    await state.clear()
    bookings = await db.user_upcoming_bookings(message.from_user.id, today_str())
    if not bookings:
        await message.answer(texts.NO_BOOKINGS, reply_markup=kb.main_menu_kb())
        return
    currency = await db.get_setting("currency", "сум")
    lines = ["🗓 <b>Ваши записи:</b>\n"]
    for b in bookings:
        d = date.fromisoformat(b["date"])
        lines.append(
            f"• {format_date_full(d)} в <b>{min_to_hhmm(b['start_min'])}</b>\n"
            f"  {b['service_name']} · {b['master_name']} · {format_price(b['price'], currency)}"
        )
    await message.answer("\n".join(lines), reply_markup=kb.my_bookings_kb(bookings))


@router.callback_query(F.data.startswith("my:cancel:"))
async def cancel_my_booking(callback: CallbackQuery) -> None:
    booking_id = int(callback.data.split(":")[2])
    booking = await db.get_booking(booking_id)
    if not booking or booking["user_id"] != callback.from_user.id:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    if booking["status"] != "active":
        await callback.answer("Запись уже отменена", show_alert=True)
        return
    await db.cancel_booking(booking_id)
    await callback.answer("Запись отменена")
    d = date.fromisoformat(booking["date"])
    await callback.message.edit_text(
        f"❌ Запись отменена:\n{format_date_full(d)} в {min_to_hhmm(booking['start_min'])}"
    )
    admin_text = (
        f"❌ <b>Отмена записи #{booking_id}</b>\n"
        f"{booking['service_name']} · {format_date_full(d)} в {min_to_hhmm(booking['start_min'])}\n"
        f"Клиент: {booking['user_name']} · {booking['phone']}"
    )
    await notify_admins(callback.bot, admin_text)


# ---------------- О нас ----------------
@router.message(F.text == kb.BTN_ABOUT)
async def about(message: Message, state: FSMContext) -> None:
    await state.clear()
    name = await db.get_setting("business_name", "Наш салон")
    address = await db.get_setting("address", "")
    phone = await db.get_setting("phone", "")
    wh = await db.get_working_hours()

    from ..utils import WEEKDAYS_FULL

    lines = [f"ℹ️ <b>{name}</b>\n"]
    if address:
        lines.append(f"📍 {address}")
    if phone:
        lines.append(f"📞 {phone}")
    lines.append("\n🕐 <b>Часы работы:</b>")
    for wd in range(7):
        day = wh.get(wd)
        if day and not day["is_day_off"]:
            lines.append(f"{WEEKDAYS_FULL[wd]}: {min_to_hhmm(day['start_min'])}–{min_to_hhmm(day['end_min'])}")
        else:
            lines.append(f"{WEEKDAYS_FULL[wd]}: выходной")
    await message.answer("\n".join(lines), reply_markup=kb.main_menu_kb())

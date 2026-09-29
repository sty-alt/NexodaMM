from __future__ import annotations

from datetime import date

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import db, keyboards as kb
from ..states import AdminSG
from ..utils import (
    WEEKDAYS_FULL,
    format_date_full,
    format_date_human,
    format_price,
    min_to_hhmm,
    parse_time_range,
    today_str,
)

router = Router()


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return bool(event.from_user) and await db.is_admin(event.from_user.id)


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def parse_int(text: str) -> int | None:
    digits = "".join(c for c in text if c.isdigit())
    return int(digits) if digits else None


# ===================== Главное меню =====================
HOME_TEXT = "🛠 <b>Панель управления</b>\nВыберите раздел:"


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(HOME_TEXT, reply_markup=kb.admin_menu_kb())


@router.callback_query(F.data == "adm:home")
async def adm_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(HOME_TEXT, reply_markup=kb.admin_menu_kb())
    await callback.answer()


# ===================== Записи =====================
@router.callback_query(F.data == "adm:today")
async def adm_today(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    bookings = await db.bookings_by_date(today_str(), "active")
    currency = await db.get_setting("currency", "сум")
    d = date.fromisoformat(today_str())
    lines = [f"📋 <b>Записи на сегодня</b> ({format_date_human(d)})\n"]
    if not bookings:
        lines.append("Записей нет.")
    else:
        for b in bookings:
            lines.append(
                f"🕐 <b>{min_to_hhmm(b['start_min'])}</b> — {b['service_name']}\n"
                f"   👤 {b['master_name']} · 🙋 {b['user_name']} · 📱 {b['phone']}\n"
                f"   💰 {format_price(b['price'], currency)}"
            )
    await callback.message.edit_text("\n".join(lines), reply_markup=kb.back_home_kb())
    await callback.answer()


@router.callback_query(F.data == "adm:upcoming")
async def adm_upcoming(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    bookings = await db.upcoming_bookings(today_str(), limit=40)
    lines = ["🗓 <b>Ближайшие записи</b>\n"]
    if not bookings:
        lines.append("Записей нет.")
    else:
        cur_date = None
        for b in bookings:
            if b["date"] != cur_date:
                cur_date = b["date"]
                d = date.fromisoformat(cur_date)
                lines.append(f"\n📆 <b>{format_date_full(d)}</b>")
            lines.append(
                f"  🕐 {min_to_hhmm(b['start_min'])} — {b['service_name']} · "
                f"{b['master_name']} · {b['user_name']} ({b['phone']})"
            )
    await callback.message.edit_text("\n".join(lines), reply_markup=kb.back_home_kb())
    await callback.answer()


# ===================== Услуги =====================
async def show_services(callback: CallbackQuery) -> None:
    services = await db.list_services(active_only=False)
    text = "💈 <b>Услуги</b>\nНажмите на услугу, чтобы изменить. ✅ — видна клиентам, 🚫 — скрыта."
    if not services:
        text = "💈 <b>Услуги</b>\nПока нет ни одной услуги. Добавьте первую 👇"
    await callback.message.edit_text(text, reply_markup=kb.admin_services_kb(services))


@router.callback_query(F.data == "adm:services")
async def adm_services(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_services(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:svc:"))
async def adm_service_card(callback: CallbackQuery) -> None:
    service_id = int(callback.data.split(":")[2])
    s = await db.get_service(service_id)
    if not s:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    currency = await db.get_setting("currency", "сум")
    status = "✅ видна клиентам" if s["is_active"] else "🚫 скрыта"
    text = (
        f"💈 <b>{s['name']}</b>\n\n"
        f"⏱ Длительность: {s['duration_min']} мин\n"
        f"💰 Цена: {format_price(s['price'], currency)}\n"
        f"Статус: {status}"
    )
    await callback.message.edit_text(text, reply_markup=kb.admin_service_card_kb(s))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:svc_toggle:"))
async def adm_service_toggle(callback: CallbackQuery) -> None:
    service_id = int(callback.data.split(":")[2])
    s = await db.get_service(service_id)
    if not s:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    await db.set_service_active(service_id, not s["is_active"])
    await callback.answer("Готово")
    await show_services(callback)


@router.callback_query(F.data == "adm:svc_add")
async def adm_service_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminSG.svc_name)
    await state.update_data(editing_id=None)
    await callback.message.edit_text("➕ Новая услуга.\nНапишите <b>название</b>:")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:svc_edit:"))
async def adm_service_edit(callback: CallbackQuery, state: FSMContext) -> None:
    service_id = int(callback.data.split(":")[2])
    await state.clear()
    await state.set_state(AdminSG.svc_name)
    await state.update_data(editing_id=service_id)
    await callback.message.edit_text("✏️ Изменение услуги.\nНапишите новое <b>название</b>:")
    await callback.answer()


@router.message(AdminSG.svc_name, F.text)
async def adm_svc_name(message: Message, state: FSMContext) -> None:
    await state.update_data(svc_name=message.text.strip())
    await state.set_state(AdminSG.svc_duration)
    await message.answer("⏱ Сколько минут занимает услуга? Введите число (например 30):")


@router.message(AdminSG.svc_duration, F.text)
async def adm_svc_duration(message: Message, state: FSMContext) -> None:
    minutes = parse_int(message.text)
    if not minutes or minutes <= 0 or minutes > 600:
        await message.answer("Введите число минут от 1 до 600 (например 30):")
        return
    await state.update_data(svc_duration=minutes)
    await state.set_state(AdminSG.svc_price)
    await message.answer("💰 Цена услуги? Введите число (например 50000), или 0 — «по договорённости»:")


@router.message(AdminSG.svc_price, F.text)
async def adm_svc_price(message: Message, state: FSMContext) -> None:
    price = parse_int(message.text)
    if price is None:
        await message.answer("Введите цену числом (например 50000) или 0:")
        return
    data = await state.get_data()
    if data.get("editing_id"):
        await db.update_service(data["editing_id"], data["svc_name"], data["svc_duration"], price)
        msg = "✅ Услуга обновлена."
    else:
        await db.add_service(data["svc_name"], data["svc_duration"], price)
        msg = "✅ Услуга добавлена."
    await state.clear()
    services = await db.list_services(active_only=False)
    await message.answer(msg, reply_markup=kb.admin_services_kb(services))


# ===================== Мастера =====================
async def show_masters(callback: CallbackQuery) -> None:
    masters = await db.list_masters(active_only=False)
    text = "👤 <b>Мастера</b>\nНажмите на мастера, чтобы изменить."
    if not masters:
        text = "👤 <b>Мастера</b>\nПока нет ни одного мастера. Добавьте 👇"
    await callback.message.edit_text(text, reply_markup=kb.admin_masters_kb(masters))


@router.callback_query(F.data == "adm:masters")
async def adm_masters(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_masters(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:mst:"))
async def adm_master_card(callback: CallbackQuery) -> None:
    master_id = int(callback.data.split(":")[2])
    m = await db.get_master(master_id)
    if not m:
        await callback.answer("Мастер не найден", show_alert=True)
        return
    status = "✅ активен" if m["is_active"] else "🚫 скрыт"
    await callback.message.edit_text(
        f"👤 <b>{m['name']}</b>\nСтатус: {status}", reply_markup=kb.admin_master_card_kb(m)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:mst_toggle:"))
async def adm_master_toggle(callback: CallbackQuery) -> None:
    master_id = int(callback.data.split(":")[2])
    m = await db.get_master(master_id)
    if not m:
        await callback.answer("Мастер не найден", show_alert=True)
        return
    if m["is_active"] and await db.count_active_masters() <= 1:
        await callback.answer("Нельзя скрыть последнего активного мастера", show_alert=True)
        return
    await db.set_master_active(master_id, not m["is_active"])
    await callback.answer("Готово")
    await show_masters(callback)


@router.callback_query(F.data == "adm:mst_add")
async def adm_master_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminSG.master_name)
    await callback.message.edit_text("➕ Новый мастер.\nНапишите <b>имя</b>:")
    await callback.answer()


@router.message(AdminSG.master_name, F.text)
async def adm_master_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Слишком коротко. Введите имя мастера:")
        return
    await db.add_master(name)
    await state.clear()
    masters = await db.list_masters(active_only=False)
    await message.answer("✅ Мастер добавлен.", reply_markup=kb.admin_masters_kb(masters))


@router.callback_query(F.data.startswith("adm:mst_rename:"))
async def adm_master_rename(callback: CallbackQuery, state: FSMContext) -> None:
    master_id = int(callback.data.split(":")[2])
    await state.clear()
    await state.set_state(AdminSG.master_rename)
    await state.update_data(master_id=master_id)
    await callback.message.edit_text("✏️ Напишите новое имя мастера:")
    await callback.answer()


@router.message(AdminSG.master_rename, F.text)
async def adm_master_rename_save(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Слишком коротко. Введите имя мастера:")
        return
    data = await state.get_data()
    await db.rename_master(data["master_id"], name)
    await state.clear()
    masters = await db.list_masters(active_only=False)
    await message.answer("✅ Имя обновлено.", reply_markup=kb.admin_masters_kb(masters))


# ===================== Рабочие часы =====================
async def show_hours(callback: CallbackQuery) -> None:
    wh = await db.get_working_hours()
    await callback.message.edit_text(
        "🕐 <b>Рабочие часы</b>\nНажмите на день, чтобы изменить.",
        reply_markup=kb.admin_hours_kb(wh),
    )


@router.callback_query(F.data == "adm:hours")
async def adm_hours(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_hours(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:wh:"))
async def adm_hours_day(callback: CallbackQuery) -> None:
    wd = int(callback.data.split(":")[2])
    day = await db.get_working_day(wd)
    if day and not day["is_day_off"]:
        info = f"Сейчас: {min_to_hhmm(day['start_min'])}–{min_to_hhmm(day['end_min'])}"
    else:
        info = "Сейчас: выходной"
    is_off = bool(day and day["is_day_off"]) or day is None
    await callback.message.edit_text(
        f"🕐 <b>{WEEKDAYS_FULL[wd]}</b>\n{info}",
        reply_markup=kb.admin_hours_day_kb(wd, is_off),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:wh_off:"))
async def adm_hours_off(callback: CallbackQuery) -> None:
    wd = int(callback.data.split(":")[2])
    day = await db.get_working_day(wd)
    start = day["start_min"] if day else 9 * 60
    end = day["end_min"] if day else 20 * 60
    await db.set_working_day(wd, start, end, True)
    await callback.answer("День сделан выходным")
    await show_hours(callback)


@router.callback_query(F.data.startswith("adm:wh_on:"))
async def adm_hours_on(callback: CallbackQuery) -> None:
    wd = int(callback.data.split(":")[2])
    day = await db.get_working_day(wd)
    start = day["start_min"] if day else 9 * 60
    end = day["end_min"] if day else 20 * 60
    await db.set_working_day(wd, start, end, False)
    await callback.answer("День сделан рабочим")
    await show_hours(callback)


@router.callback_query(F.data.startswith("adm:wh_set:"))
async def adm_hours_set(callback: CallbackQuery, state: FSMContext) -> None:
    wd = int(callback.data.split(":")[2])
    await state.clear()
    await state.set_state(AdminSG.wh_input)
    await state.update_data(wd=wd)
    await callback.message.edit_text(
        f"🕐 <b>{WEEKDAYS_FULL[wd]}</b>\nВведите часы работы в формате <code>09:00-20:00</code>:"
    )
    await callback.answer()


@router.message(AdminSG.wh_input, F.text)
async def adm_hours_input(message: Message, state: FSMContext) -> None:
    rng = parse_time_range(message.text)
    if not rng:
        await message.answer("Неверный формат. Пример: <code>09:00-20:00</code>")
        return
    data = await state.get_data()
    await db.set_working_day(data["wd"], rng[0], rng[1], False)
    await state.clear()
    wh = await db.get_working_hours()
    await message.answer("✅ Часы обновлены.", reply_markup=kb.admin_hours_kb(wh))


# ===================== Блокировки времени =====================
async def show_blocks(callback: CallbackQuery) -> None:
    blocks = await db.list_blocks(today_str())
    text = (
        "⛔️ <b>Блокировки времени</b>\n"
        "Здесь можно закрыть время (перерыв, отпуск), чтобы клиенты не записались.\n"
    )
    if not blocks:
        text += "\nАктивных блокировок нет."
    await callback.message.edit_text(text, reply_markup=kb.admin_blocks_kb(blocks))


@router.callback_query(F.data == "adm:blocks")
async def adm_blocks(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_blocks(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:block_del:"))
async def adm_block_del(callback: CallbackQuery) -> None:
    block_id = int(callback.data.split(":")[2])
    await db.delete_block(block_id)
    await callback.answer("Блокировка снята")
    await show_blocks(callback)


@router.callback_query(F.data == "adm:block_add")
async def adm_block_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminSG.block_date)
    await callback.message.edit_text(
        "⛔️ Новая блокировка.\nВведите дату в формате <code>2026-06-10</code>:"
    )
    await callback.answer()


@router.message(AdminSG.block_date, F.text)
async def adm_block_date(message: Message, state: FSMContext) -> None:
    try:
        d = date.fromisoformat(message.text.strip())
    except ValueError:
        await message.answer("Неверная дата. Пример: <code>2026-06-10</code>")
        return
    await state.update_data(block_date=d.isoformat())
    await state.set_state(AdminSG.block_time)
    await message.answer("Введите интервал в формате <code>13:00-14:00</code>:")


@router.message(AdminSG.block_time, F.text)
async def adm_block_time(message: Message, state: FSMContext) -> None:
    rng = parse_time_range(message.text)
    if not rng:
        await message.answer("Неверный формат. Пример: <code>13:00-14:00</code>")
        return
    data = await state.get_data()
    await db.add_block(None, data["block_date"], rng[0], rng[1], "перерыв")
    await state.clear()
    blocks = await db.list_blocks(today_str())
    await message.answer("✅ Время заблокировано.", reply_markup=kb.admin_blocks_kb(blocks))


# ===================== Рассылка =====================
@router.callback_query(F.data == "adm:broadcast")
async def adm_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    ids = await db.all_client_ids()
    await state.set_state(AdminSG.broadcast)
    await callback.message.edit_text(
        f"📣 <b>Рассылка</b>\nСообщение получат все клиенты ({len(ids)} чел.).\n\n"
        "Напишите текст сообщения (или /cancel для отмены):"
    )
    await callback.answer()


@router.message(AdminSG.broadcast, Command("cancel"))
async def adm_broadcast_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Рассылка отменена.", reply_markup=kb.admin_menu_kb())


@router.message(AdminSG.broadcast, F.text)
async def adm_broadcast_send(message: Message, state: FSMContext) -> None:
    await state.clear()
    ids = await db.all_client_ids()
    ok, fail = 0, 0
    for uid in ids:
        try:
            await message.bot.send_message(uid, message.text)
            ok += 1
        except Exception:
            fail += 1
    await message.answer(
        f"📣 Рассылка завершена.\nДоставлено: {ok}\nНе доставлено: {fail}",
        reply_markup=kb.admin_menu_kb(),
    )


# ===================== Настройки =====================
SETTING_PROMPTS = {
    "business_name": "Введите название бизнеса:",
    "address": "Введите адрес:",
    "phone": "Введите контактный телефон:",
    "currency": "Введите валюту (например: сум):",
    "reminder_hours": "За сколько часов до визита напоминать? Введите число (например 2):",
    "horizon_days": "На сколько дней вперёд открыть запись? Введите число (например 14):",
    "slot_step": "Шаг сетки времени в минутах (например 30):",
}
NUMERIC_SETTINGS = {"reminder_hours", "horizon_days", "slot_step"}


async def show_settings(callback: CallbackQuery) -> None:
    name = await db.get_setting("business_name", "—")
    address = await db.get_setting("address", "") or "—"
    phone = await db.get_setting("phone", "") or "—"
    currency = await db.get_setting("currency", "сум")
    reminder = await db.get_setting("reminder_hours", "2")
    horizon = await db.get_setting("horizon_days", "14")
    step = await db.get_setting("slot_step", "30")
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"🏷 Название: {name}\n"
        f"📍 Адрес: {address}\n"
        f"📞 Телефон: {phone}\n"
        f"💱 Валюта: {currency}\n"
        f"⏰ Напоминать за: {reminder} ч\n"
        f"📅 Горизонт записи: {horizon} дн\n"
        f"🪜 Шаг времени: {step} мин"
    )
    await callback.message.edit_text(text, reply_markup=kb.admin_settings_kb())


@router.callback_query(F.data == "adm:settings")
async def adm_settings(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_settings(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:set:"))
async def adm_setting_edit(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":")[2]
    if key not in SETTING_PROMPTS:
        await callback.answer("Неизвестная настройка", show_alert=True)
        return
    await state.clear()
    await state.set_state(AdminSG.set_value)
    await state.update_data(set_key=key)
    await callback.message.edit_text(SETTING_PROMPTS[key])
    await callback.answer()


@router.message(AdminSG.set_value, F.text)
async def adm_setting_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    key = data.get("set_key")
    value = message.text.strip()
    if key in NUMERIC_SETTINGS:
        num = parse_int(value)
        if not num or num <= 0:
            await message.answer("Введите положительное число:")
            return
        if key == "reminder_hours" and num > 72:
            num = 72
        if key == "horizon_days" and num > 60:
            num = 60
        if key == "slot_step" and (num < 5 or num > 120):
            await message.answer("Шаг должен быть от 5 до 120 минут:")
            return
        value = str(num)
    await db.set_setting(key, value)
    await state.clear()
    await message.answer("✅ Сохранено.", reply_markup=kb.admin_menu_kb())

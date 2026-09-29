from __future__ import annotations

from datetime import date

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from .utils import format_date_human, format_price, min_to_hhmm

# Метки кнопок главного меню (используются и в обработчиках текста)
BTN_BOOK = "📅 Записаться"
BTN_MY = "🗓 Мои записи"
BTN_ABOUT = "ℹ️ О нас"
BTN_SEND_PHONE = "📱 Отправить мой номер"
BTN_CANCEL = "✖️ Отмена"


def main_menu_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text=BTN_BOOK))
    kb.row(KeyboardButton(text=BTN_MY), KeyboardButton(text=BTN_ABOUT))
    return kb.as_markup(resize_keyboard=True)


def contact_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text=BTN_SEND_PHONE, request_contact=True))
    kb.row(KeyboardButton(text=BTN_CANCEL))
    return kb.as_markup(resize_keyboard=True)


def _cancel_row(builder: InlineKeyboardBuilder) -> None:
    builder.row(InlineKeyboardButton(text="✖️ Отмена", callback_data="bk:cancel"))


def services_kb(services) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in services:
        kb.row(
            InlineKeyboardButton(
                text=f"{s['name']} · {format_price(s['price'])}",
                callback_data=f"bk:svc:{s['id']}",
            )
        )
    _cancel_row(kb)
    return kb.as_markup()


def masters_kb(masters) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for m in masters:
        kb.row(InlineKeyboardButton(text=f"👤 {m['name']}", callback_data=f"bk:mst:{m['id']}"))
    _cancel_row(kb)
    return kb.as_markup()


def dates_kb(dates: list[date]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    buttons = [
        InlineKeyboardButton(text=format_date_human(d), callback_data=f"bk:date:{d.isoformat()}")
        for d in dates
    ]
    kb.add(*buttons)
    kb.adjust(2)
    _cancel_row(kb)
    return kb.as_markup()


def times_kb(slots: list[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    buttons = [
        InlineKeyboardButton(text=min_to_hhmm(s), callback_data=f"bk:time:{s}") for s in slots
    ]
    kb.add(*buttons)
    kb.adjust(4)
    kb.row(InlineKeyboardButton(text="⬅️ К датам", callback_data="bk:back_dates"))
    _cancel_row(kb)
    return kb.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="bk:confirm"),
        InlineKeyboardButton(text="✖️ Отмена", callback_data="bk:cancel"),
    )
    return kb.as_markup()


def my_bookings_kb(bookings) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in bookings:
        d = date.fromisoformat(b["date"])
        kb.row(
            InlineKeyboardButton(
                text=f"✖️ Отменить {format_date_human(d)} {min_to_hhmm(b['start_min'])}",
                callback_data=f"my:cancel:{b['id']}",
            )
        )
    return kb.as_markup()


# ===================== АДМИНКА =====================

def admin_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📋 Записи на сегодня", callback_data="adm:today"))
    kb.row(InlineKeyboardButton(text="🗓 Ближайшие записи", callback_data="adm:upcoming"))
    kb.row(
        InlineKeyboardButton(text="💈 Услуги", callback_data="adm:services"),
        InlineKeyboardButton(text="👤 Мастера", callback_data="adm:masters"),
    )
    kb.row(
        InlineKeyboardButton(text="🕐 Рабочие часы", callback_data="adm:hours"),
        InlineKeyboardButton(text="⛔️ Блокировки", callback_data="adm:blocks"),
    )
    kb.row(
        InlineKeyboardButton(text="📣 Рассылка", callback_data="adm:broadcast"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="adm:settings"),
    )
    return kb.as_markup()


def back_home_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:home"))
    return kb.as_markup()


def admin_services_kb(services) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in services:
        mark = "✅" if s["is_active"] else "🚫"
        kb.row(
            InlineKeyboardButton(
                text=f"{mark} {s['name']} · {format_price(s['price'])}",
                callback_data=f"adm:svc:{s['id']}",
            )
        )
    kb.row(InlineKeyboardButton(text="➕ Добавить услугу", callback_data="adm:svc_add"))
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:home"))
    return kb.as_markup()


def admin_service_card_kb(service) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✏️ Изменить", callback_data=f"adm:svc_edit:{service['id']}"))
    if service["is_active"]:
        kb.row(InlineKeyboardButton(text="🚫 Скрыть", callback_data=f"adm:svc_toggle:{service['id']}"))
    else:
        kb.row(InlineKeyboardButton(text="✅ Показать", callback_data=f"adm:svc_toggle:{service['id']}"))
    kb.row(InlineKeyboardButton(text="⬅️ К услугам", callback_data="adm:services"))
    return kb.as_markup()


def admin_masters_kb(masters) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for m in masters:
        mark = "✅" if m["is_active"] else "🚫"
        kb.row(InlineKeyboardButton(text=f"{mark} {m['name']}", callback_data=f"adm:mst:{m['id']}"))
    kb.row(InlineKeyboardButton(text="➕ Добавить мастера", callback_data="adm:mst_add"))
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:home"))
    return kb.as_markup()


def admin_master_card_kb(master) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"adm:mst_rename:{master['id']}"))
    if master["is_active"]:
        kb.row(InlineKeyboardButton(text="🚫 Скрыть", callback_data=f"adm:mst_toggle:{master['id']}"))
    else:
        kb.row(InlineKeyboardButton(text="✅ Показать", callback_data=f"adm:mst_toggle:{master['id']}"))
    kb.row(InlineKeyboardButton(text="⬅️ К мастерам", callback_data="adm:masters"))
    return kb.as_markup()


def admin_hours_kb(working_hours: dict) -> InlineKeyboardMarkup:
    from .utils import WEEKDAYS_FULL

    kb = InlineKeyboardBuilder()
    for wd in range(7):
        day = working_hours.get(wd)
        if day and not day["is_day_off"]:
            label = f"{WEEKDAYS_FULL[wd]}: {min_to_hhmm(day['start_min'])}–{min_to_hhmm(day['end_min'])}"
        else:
            label = f"{WEEKDAYS_FULL[wd]}: выходной"
        kb.row(InlineKeyboardButton(text=label, callback_data=f"adm:wh:{wd}"))
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:home"))
    return kb.as_markup()


def admin_hours_day_kb(wd: int, is_day_off: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🕐 Задать часы", callback_data=f"adm:wh_set:{wd}"))
    if is_day_off:
        kb.row(InlineKeyboardButton(text="✅ Сделать рабочим", callback_data=f"adm:wh_on:{wd}"))
    else:
        kb.row(InlineKeyboardButton(text="🚫 Сделать выходным", callback_data=f"adm:wh_off:{wd}"))
    kb.row(InlineKeyboardButton(text="⬅️ К расписанию", callback_data="adm:hours"))
    return kb.as_markup()


def admin_blocks_kb(blocks) -> InlineKeyboardMarkup:
    from datetime import date as _date

    kb = InlineKeyboardBuilder()
    for bl in blocks:
        d = _date.fromisoformat(bl["date"])
        kb.row(
            InlineKeyboardButton(
                text=f"🗑 {format_date_human(d)} {min_to_hhmm(bl['start_min'])}–{min_to_hhmm(bl['end_min'])}",
                callback_data=f"adm:block_del:{bl['id']}",
            )
        )
    kb.row(InlineKeyboardButton(text="➕ Добавить блокировку", callback_data="adm:block_add"))
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:home"))
    return kb.as_markup()


def admin_settings_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏷 Название бизнеса", callback_data="adm:set:business_name"))
    kb.row(InlineKeyboardButton(text="📍 Адрес", callback_data="adm:set:address"))
    kb.row(InlineKeyboardButton(text="📞 Телефон", callback_data="adm:set:phone"))
    kb.row(InlineKeyboardButton(text="💱 Валюта", callback_data="adm:set:currency"))
    kb.row(InlineKeyboardButton(text="⏰ Напоминать за (часов)", callback_data="adm:set:reminder_hours"))
    kb.row(InlineKeyboardButton(text="📅 Горизонт записи (дней)", callback_data="adm:set:horizon_days"))
    kb.row(InlineKeyboardButton(text="🪜 Шаг времени (минут)", callback_data="adm:set:slot_step"))
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:home"))
    return kb.as_markup()

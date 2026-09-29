from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import db
from .config import config

WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_FULL = [
    "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье",
]
MONTHS_GEN = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def tz() -> ZoneInfo:
    try:
        return ZoneInfo(config.timezone)
    except Exception:
        return ZoneInfo("Asia/Tashkent")


def now_local() -> datetime:
    return datetime.now(tz())


def today_str() -> str:
    return now_local().date().isoformat()


def min_to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def hhmm_to_min(text: str) -> int | None:
    text = text.strip().replace(".", ":").replace("-", ":")
    if ":" not in text:
        return None
    parts = text.split(":")
    if len(parts) != 2:
        return None
    h, m = parts
    if not (h.strip().isdigit() and m.strip().isdigit()):
        return None
    h, m = int(h), int(m)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m


def parse_time_range(text: str) -> tuple[int, int] | None:
    """'09:00-20:00' -> (540, 1200)."""
    for sep in ("-", "—", "–", " "):
        if sep in text:
            left, _, right = text.partition(sep)
            a = hhmm_to_min(left)
            b = hhmm_to_min(right)
            if a is not None and b is not None and b > a:
                return a, b
    return None


def format_price(price: int, currency: str = "сум") -> str:
    if price is None or price <= 0:
        return "по договорённости"
    return f"{price:,}".replace(",", " ") + f" {currency}"


def format_date_human(d: date) -> str:
    return f"{WEEKDAYS_SHORT[d.weekday()]}, {d.day} {MONTHS_GEN[d.month - 1]}"


def format_date_full(d: date) -> str:
    return f"{WEEKDAYS_FULL[d.weekday()]}, {d.day} {MONTHS_GEN[d.month - 1]} {d.year}"


async def booking_horizon_dates() -> list[date]:
    """Список дат, на которые открыта запись (только рабочие дни)."""
    horizon = await db.get_int_setting("horizon_days", 14)
    wh = await db.get_working_hours()
    start = now_local().date()
    result: list[date] = []
    for i in range(max(1, horizon)):
        d = start + timedelta(days=i)
        day = wh.get(d.weekday())
        if day and not day["is_day_off"]:
            result.append(d)
    return result


async def available_slots(date_str: str, duration_min: int, master_id: int) -> list[int]:
    """Свободные времена начала (в минутах от полуночи) для мастера на дату."""
    d = date.fromisoformat(date_str)
    day = await db.get_working_day(d.weekday())
    if not day or day["is_day_off"]:
        return []

    step = max(5, await db.get_int_setting("slot_step", 30))
    work_start = day["start_min"]
    work_end = day["end_min"]

    busy: list[tuple[int, int]] = []
    for b in await db.active_bookings_for_master_date(master_id, date_str):
        busy.append((b["start_min"], b["start_min"] + b["duration_min"]))
    for bl in await db.blocks_for(date_str, master_id):
        busy.append((bl["start_min"], bl["end_min"]))

    min_start = 0
    if d == now_local().date():
        n = now_local()
        min_start = n.hour * 60 + n.minute + 15  # буфер 15 минут

    slots: list[int] = []
    s = work_start
    while s + duration_min <= work_end:
        slot_end = s + duration_min
        if s >= min_start and not any(not (slot_end <= bs or s >= be) for bs, be in busy):
            slots.append(s)
        s += step
    return slots


async def format_booking_short(b, currency: str | None = None) -> str:
    if currency is None:
        currency = await db.get_setting("currency", "сум")
    d = date.fromisoformat(b["date"])
    return (
        f"<b>{format_date_human(d)}</b> в <b>{min_to_hhmm(b['start_min'])}</b>\n"
        f"💈 {b['service_name']} · {format_price(b['price'], currency)}\n"
        f"👤 Мастер: {b['master_name']}"
    )

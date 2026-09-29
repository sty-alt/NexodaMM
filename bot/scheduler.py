from __future__ import annotations

from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import db
from .utils import format_date_full, min_to_hhmm, now_local, tz


def _reminder_text(b) -> str:
    d = date.fromisoformat(b["date"])
    return (
        "⏰ <b>Напоминание о записи!</b>\n\n"
        f"💈 {b['service_name']}\n"
        f"👤 Мастер: {b['master_name']}\n"
        f"📆 {format_date_full(d)} в <b>{min_to_hhmm(b['start_min'])}</b>\n\n"
        "Ждём вас! Если планы изменились — отмените запись в «🗓 Мои записи»."
    )


async def reminder_tick(bot) -> None:
    reminder_hours = await db.get_int_setting("reminder_hours", 2)
    window = max(1, reminder_hours) * 60
    now = now_local()
    now_min = now.hour * 60 + now.minute

    for b in await db.bookings_pending_reminder(now.date().isoformat()):
        bd = date.fromisoformat(b["date"])
        minutes_until = (bd - now.date()).days * 1440 + b["start_min"] - now_min
        if 0 <= minutes_until <= window:
            try:
                await bot.send_message(b["user_id"], _reminder_text(b))
            except Exception:
                pass
            finally:
                await db.mark_reminded(b["id"])


def setup_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=tz())
    scheduler.add_job(reminder_tick, "interval", seconds=60, args=[bot], id="reminders")
    scheduler.start()
    return scheduler

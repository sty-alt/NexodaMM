"""Проверка ядра бота без Telegram: слоты, бронь, отмена, настройки.

Запуск:  python selftest.py
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from bot import db
from bot.utils import (
    available_slots,
    format_price,
    hhmm_to_min,
    min_to_hhmm,
    parse_time_range,
)


def check(name: str, cond: bool) -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}")
    if not cond:
        raise AssertionError(name)


async def run() -> None:
    tmp = Path(tempfile.gettempdir()) / "nexoda_selftest.db"
    if tmp.exists():
        tmp.unlink()
    await db.init_db(tmp)

    # 1) Сидирование по умолчанию
    masters = await db.list_masters()
    services = await db.list_services()
    check("есть хотя бы один мастер", len(masters) >= 1)
    check("есть услуги по умолчанию", len(services) >= 1)

    master = masters[0]
    service = services[0]

    # 2) Находим ближайший рабочий день
    from datetime import date, timedelta

    from bot.utils import now_local

    target = None
    for i in range(0, 14):
        d = now_local().date() + timedelta(days=i)
        day = await db.get_working_day(d.weekday())
        if day and not day["is_day_off"]:
            target = d.isoformat()
            break
    check("найден рабочий день", target is not None)

    # 3) Свободные слоты есть
    slots_before = await available_slots(target, service["duration_min"], master["id"])
    check("есть свободные слоты", len(slots_before) > 0)

    # 4) Создаём бронь на первый слот
    slot = slots_before[0]
    bid = await db.add_booking(
        user_id=111,
        user_name="Тест Клиент",
        phone="+998901112233",
        service_id=service["id"],
        service_name=service["name"],
        price=service["price"],
        master_id=master["id"],
        master_name=master["name"],
        date=target,
        start_min=slot,
        duration_min=service["duration_min"],
    )
    check("бронь создана", bid > 0)

    # 5) Слот должен исчезнуть из доступных
    slots_after = await available_slots(target, service["duration_min"], master["id"])
    check("занятый слот недоступен", slot not in slots_after)
    check("слотов стало меньше", len(slots_after) < len(slots_before))

    # 6) Отмена возвращает слот
    await db.cancel_booking(bid)
    slots_restored = await available_slots(target, service["duration_min"], master["id"])
    check("после отмены слот снова свободен", slot in slots_restored)

    # 7) Блокировка времени убирает слоты
    await db.add_block(None, target, slot, slot + service["duration_min"], "тест")
    slots_blocked = await available_slots(target, service["duration_min"], master["id"])
    check("заблокированный слот недоступен", slot not in slots_blocked)

    # 8) Настройки
    await db.set_setting("business_name", "Барбершоп Тест")
    check("настройка сохраняется", await db.get_setting("business_name") == "Барбершоп Тест")
    check("числовая настройка по умолчанию", await db.get_int_setting("reminder_hours", 2) == 2)

    # 9) Утилиты времени/цены
    check("parse_time_range", parse_time_range("09:00-20:00") == (540, 1200))
    check("hhmm_to_min", hhmm_to_min("09:30") == 570)
    check("min_to_hhmm", min_to_hhmm(570) == "09:30")
    check("неверное время -> None", hhmm_to_min("25:00") is None)
    check("format_price", format_price(50000, "сум") == "50 000 сум")
    check("format_price ноль", format_price(0) == "по договорённости")

    await db.close_db()
    print("\nВсё ядро работает корректно ✅")


if __name__ == "__main__":
    asyncio.run(run())

"""Применить готовый пресет ниши (услуги, мастера, часы, название).

Список:        python apply_preset.py
Применить:     python apply_preset.py barbershop
С перезаписью: python apply_preset.py barbershop --force   (если в базе уже есть записи)
"""
from __future__ import annotations

import asyncio
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from bot import db, presets
from bot.utils import hhmm_to_min


async def apply(key: str, force: bool) -> bool:
    p = presets.PRESETS[key]
    await db.init_db()

    if await db.count_bookings() > 0 and not force:
        await db.close_db()
        print(
            "⚠️  В базе уже есть записи. Применение пресета перезапишет услуги/мастеров/часы.\n"
            "    Если уверен — запусти снова с флагом --force"
        )
        return False

    await db.reset_business_data()

    open_min = hhmm_to_min(p["open"])
    close_min = hhmm_to_min(p["close"])
    for wd in range(7):
        await db.set_working_day(wd, open_min, close_min, wd in p["days_off"])

    for name in p["masters"]:
        await db.add_master(name)
    for name, duration, price in p["services"]:
        await db.add_service(name, duration, price)

    await db.set_setting("business_name", p["business_name"])
    await db.set_setting("currency", p.get("currency", "сум"))

    await db.close_db()
    return True


def main() -> None:
    keys = list(presets.PRESETS)
    if len(sys.argv) < 2 or sys.argv[1] not in presets.PRESETS:
        print("Доступные пресеты:\n")
        for k, v in presets.PRESETS.items():
            print(f"  {k:<12} — {v['title']}")
        print("\nПример:  python apply_preset.py barbershop")
        return

    key = sys.argv[1]
    force = "--force" in sys.argv[2:]
    ok = asyncio.run(apply(key, force))
    if ok:
        p = presets.PRESETS[key]
        print(
            f"✅ Применён пресет «{p['title']}».\n"
            f"   Услуг: {len(p['services'])}, мастеров: {len(p['masters'])}, "
            f"часы: {p['open']}–{p['close']}.\n\n"
            "Запусти бота:  python main.py  (или start.bat)\n"
            "Затем донастрой в Telegram через /admin."
        )


if __name__ == "__main__":
    main()

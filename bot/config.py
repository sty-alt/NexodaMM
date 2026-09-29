from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "nexoda.db"

load_dotenv(BASE_DIR / ".env")


def _parse_admins(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.add(int(part))
    return ids


@dataclass
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "").strip()
    admin_ids: set[int] = field(default_factory=lambda: _parse_admins(os.getenv("ADMIN_IDS", "")))
    timezone: str = (os.getenv("TIMEZONE", "Asia/Tashkent").strip() or "Asia/Tashkent")
    business_name_default: str = os.getenv("BUSINESS_NAME", "Наш салон").strip() or "Наш салон"


config = Config()

# Настройки, которые владелец может менять прямо из админки (хранятся в БД).
DEFAULT_SETTINGS: dict[str, str] = {
    "business_name": config.business_name_default,
    "currency": "сум",
    "reminder_hours": "2",   # за сколько часов до визита напоминать
    "horizon_days": "14",    # на сколько дней вперёд открыта запись
    "slot_step": "30",       # шаг сетки времени в минутах
    "address": "",
    "phone": "",
}

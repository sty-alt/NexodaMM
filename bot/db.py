from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from .config import DB_PATH, DEFAULT_SETTINGS, config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS masters (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS services (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    duration_min INTEGER NOT NULL DEFAULT 30,
    price        INTEGER NOT NULL DEFAULT 0,
    is_active    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS working_hours (
    weekday    INTEGER PRIMARY KEY,   -- 0=Пн ... 6=Вс
    start_min  INTEGER NOT NULL,
    end_min    INTEGER NOT NULL,
    is_day_off INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    user_name    TEXT,
    phone        TEXT,
    service_id   INTEGER,
    service_name TEXT,
    price        INTEGER,
    master_id    INTEGER,
    master_name  TEXT,
    date         TEXT NOT NULL,          -- YYYY-MM-DD
    start_min    INTEGER NOT NULL,
    duration_min INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'active',  -- active / cancelled / done
    reminded     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id INTEGER,                  -- NULL = для всех мастеров
    date      TEXT NOT NULL,
    start_min INTEGER NOT NULL,
    end_min   INTEGER NOT NULL,
    reason    TEXT
);

CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date, status);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id, status);
"""

_db: Optional[aiosqlite.Connection] = None


def db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("База данных не инициализирована. Сначала вызови init_db().")
    return _db


async def init_db(path: str | Path | None = None) -> None:
    global _db
    _db = await aiosqlite.connect(str(path or DB_PATH))
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _db.commit()
    await seed_defaults()


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def seed_defaults() -> None:
    conn = db()
    # Настройки по умолчанию
    for key, value in DEFAULT_SETTINGS.items():
        await conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value)
        )
    # Рабочие часы: Пн-Сб 09:00-20:00, Вс выходной
    cur = await conn.execute("SELECT COUNT(*) AS c FROM working_hours")
    row = await cur.fetchone()
    if row["c"] == 0:
        for wd in range(7):
            is_off = 1 if wd == 6 else 0
            await conn.execute(
                "INSERT INTO working_hours(weekday, start_min, end_min, is_day_off) VALUES (?, ?, ?, ?)",
                (wd, 9 * 60, 20 * 60, is_off),
            )
    # Хотя бы один мастер
    cur = await conn.execute("SELECT COUNT(*) AS c FROM masters")
    if (await cur.fetchone())["c"] == 0:
        await conn.execute("INSERT INTO masters(name, is_active) VALUES (?, 1)", ("Мастер",))
    # Примеры услуг (владелец потом отредактирует/удалит)
    cur = await conn.execute("SELECT COUNT(*) AS c FROM services")
    if (await cur.fetchone())["c"] == 0:
        await conn.execute(
            "INSERT INTO services(name, duration_min, price) VALUES (?, ?, ?)",
            ("Стрижка", 30, 50000),
        )
        await conn.execute(
            "INSERT INTO services(name, duration_min, price) VALUES (?, ?, ?)",
            ("Стрижка + борода", 45, 70000),
        )
    await conn.commit()


async def reset_business_data() -> None:
    """Очистить услуги/мастеров/часы/блокировки (для применения пресета). Брони не трогаем."""
    conn = db()
    await conn.execute("DELETE FROM services")
    await conn.execute("DELETE FROM masters")
    await conn.execute("DELETE FROM working_hours")
    await conn.execute("DELETE FROM blocks")
    await conn.commit()


async def count_bookings() -> int:
    cur = await db().execute("SELECT COUNT(*) AS c FROM bookings")
    return (await cur.fetchone())["c"]


# ---------- Настройки ----------
async def get_setting(key: str, default: str = "") -> str:
    cur = await db().execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cur.fetchone()
    return row["value"] if row else default


async def get_int_setting(key: str, default: int = 0) -> int:
    raw = await get_setting(key, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


async def set_setting(key: str, value: str) -> None:
    await db().execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    await db().commit()


# ---------- Администраторы (из .env + назначенные в боте) ----------
async def get_db_admins() -> set[int]:
    raw = await get_setting("db_admins", "")
    return {
        int(x) for x in raw.replace(";", ",").split(",")
        if x.strip().lstrip("-").isdigit()
    }


async def add_db_admin(uid: int) -> None:
    admins = await get_db_admins()
    admins.add(uid)
    await set_setting("db_admins", ",".join(str(a) for a in sorted(admins)))


async def is_admin(uid: int) -> bool:
    if uid in config.admin_ids:
        return True
    return uid in await get_db_admins()


async def any_admin_exists() -> bool:
    if config.admin_ids:
        return True
    return bool(await get_db_admins())


# ---------- Мастера ----------
async def list_masters(active_only: bool = True) -> list[aiosqlite.Row]:
    q = "SELECT * FROM masters"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY id"
    cur = await db().execute(q)
    return list(await cur.fetchall())


async def get_master(master_id: int) -> Optional[aiosqlite.Row]:
    cur = await db().execute("SELECT * FROM masters WHERE id = ?", (master_id,))
    return await cur.fetchone()


async def add_master(name: str) -> int:
    cur = await db().execute("INSERT INTO masters(name, is_active) VALUES (?, 1)", (name,))
    await db().commit()
    return cur.lastrowid


async def rename_master(master_id: int, name: str) -> None:
    await db().execute("UPDATE masters SET name = ? WHERE id = ?", (name, master_id))
    await db().commit()


async def set_master_active(master_id: int, active: bool) -> None:
    await db().execute(
        "UPDATE masters SET is_active = ? WHERE id = ?", (1 if active else 0, master_id)
    )
    await db().commit()


async def count_active_masters() -> int:
    cur = await db().execute("SELECT COUNT(*) AS c FROM masters WHERE is_active = 1")
    return (await cur.fetchone())["c"]


# ---------- Услуги ----------
async def list_services(active_only: bool = True) -> list[aiosqlite.Row]:
    q = "SELECT * FROM services"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY id"
    cur = await db().execute(q)
    return list(await cur.fetchall())


async def get_service(service_id: int) -> Optional[aiosqlite.Row]:
    cur = await db().execute("SELECT * FROM services WHERE id = ?", (service_id,))
    return await cur.fetchone()


async def add_service(name: str, duration_min: int, price: int) -> int:
    cur = await db().execute(
        "INSERT INTO services(name, duration_min, price) VALUES (?, ?, ?)",
        (name, duration_min, price),
    )
    await db().commit()
    return cur.lastrowid


async def update_service(service_id: int, name: str, duration_min: int, price: int) -> None:
    await db().execute(
        "UPDATE services SET name = ?, duration_min = ?, price = ? WHERE id = ?",
        (name, duration_min, price, service_id),
    )
    await db().commit()


async def set_service_active(service_id: int, active: bool) -> None:
    await db().execute(
        "UPDATE services SET is_active = ? WHERE id = ?", (1 if active else 0, service_id)
    )
    await db().commit()


# ---------- Рабочие часы ----------
async def get_working_hours() -> dict[int, aiosqlite.Row]:
    cur = await db().execute("SELECT * FROM working_hours")
    return {row["weekday"]: row for row in await cur.fetchall()}


async def get_working_day(weekday: int) -> Optional[aiosqlite.Row]:
    cur = await db().execute("SELECT * FROM working_hours WHERE weekday = ?", (weekday,))
    return await cur.fetchone()


async def set_working_day(weekday: int, start_min: int, end_min: int, is_day_off: bool) -> None:
    await db().execute(
        "INSERT INTO working_hours(weekday, start_min, end_min, is_day_off) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(weekday) DO UPDATE SET start_min=excluded.start_min, "
        "end_min=excluded.end_min, is_day_off=excluded.is_day_off",
        (weekday, start_min, end_min, 1 if is_day_off else 0),
    )
    await db().commit()


# ---------- Брони ----------
async def add_booking(
    user_id: int,
    user_name: str,
    phone: str,
    service_id: int,
    service_name: str,
    price: int,
    master_id: int,
    master_name: str,
    date: str,
    start_min: int,
    duration_min: int,
) -> int:
    cur = await db().execute(
        """INSERT INTO bookings
        (user_id, user_name, phone, service_id, service_name, price, master_id, master_name,
         date, start_min, duration_min, status, reminded, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, ?)""",
        (
            user_id, user_name, phone, service_id, service_name, price, master_id, master_name,
            date, start_min, duration_min, datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    await db().commit()
    return cur.lastrowid


async def get_booking(booking_id: int) -> Optional[aiosqlite.Row]:
    cur = await db().execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
    return await cur.fetchone()


async def active_bookings_for_master_date(master_id: int, date: str) -> list[aiosqlite.Row]:
    cur = await db().execute(
        "SELECT * FROM bookings WHERE master_id = ? AND date = ? AND status = 'active' "
        "ORDER BY start_min",
        (master_id, date),
    )
    return list(await cur.fetchall())


async def bookings_by_date(date: str, status: str = "active") -> list[aiosqlite.Row]:
    cur = await db().execute(
        "SELECT * FROM bookings WHERE date = ? AND status = ? ORDER BY start_min",
        (date, status),
    )
    return list(await cur.fetchall())


async def upcoming_bookings(from_date: str, limit: int = 50) -> list[aiosqlite.Row]:
    cur = await db().execute(
        "SELECT * FROM bookings WHERE date >= ? AND status = 'active' "
        "ORDER BY date, start_min LIMIT ?",
        (from_date, limit),
    )
    return list(await cur.fetchall())


async def user_upcoming_bookings(user_id: int, from_date: str) -> list[aiosqlite.Row]:
    cur = await db().execute(
        "SELECT * FROM bookings WHERE user_id = ? AND status = 'active' AND date >= ? "
        "ORDER BY date, start_min",
        (user_id, from_date),
    )
    return list(await cur.fetchall())


async def cancel_booking(booking_id: int) -> None:
    await db().execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    await db().commit()


async def bookings_pending_reminder(from_date: str) -> list[aiosqlite.Row]:
    """Активные брони (с указанной даты), по которым напоминание ещё не отправлено."""
    cur = await db().execute(
        "SELECT * FROM bookings WHERE status = 'active' AND reminded = 0 AND date >= ? "
        "ORDER BY date, start_min",
        (from_date,),
    )
    return list(await cur.fetchall())


async def mark_reminded(booking_id: int) -> None:
    await db().execute("UPDATE bookings SET reminded = 1 WHERE id = ?", (booking_id,))
    await db().commit()


async def all_client_ids() -> list[int]:
    cur = await db().execute("SELECT DISTINCT user_id FROM bookings")
    return [row["user_id"] for row in await cur.fetchall()]


# ---------- Блокировки времени (перерывы/отпуск) ----------
async def add_block(master_id: Optional[int], date: str, start_min: int, end_min: int, reason: str) -> int:
    cur = await db().execute(
        "INSERT INTO blocks(master_id, date, start_min, end_min, reason) VALUES (?, ?, ?, ?, ?)",
        (master_id, date, start_min, end_min, reason),
    )
    await db().commit()
    return cur.lastrowid


async def blocks_for(date: str, master_id: int) -> list[aiosqlite.Row]:
    cur = await db().execute(
        "SELECT * FROM blocks WHERE date = ? AND (master_id IS NULL OR master_id = ?)",
        (date, master_id),
    )
    return list(await cur.fetchall())


async def list_blocks(from_date: str) -> list[aiosqlite.Row]:
    cur = await db().execute(
        "SELECT * FROM blocks WHERE date >= ? ORDER BY date, start_min", (from_date,)
    )
    return list(await cur.fetchall())


async def delete_block(block_id: int) -> None:
    await db().execute("DELETE FROM blocks WHERE id = ?", (block_id,))
    await db().commit()

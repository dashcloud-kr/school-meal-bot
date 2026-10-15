"""SQLite 저장소 (학교 등록·알림 설정)."""

from __future__ import annotations

from dataclasses import dataclass

from app.clients.neis import School
from app.db import Database


@dataclass(frozen=True)
class SchoolEntry:
    id: int
    edu_code: str
    school_code: str
    name: str
    location: str


@dataclass(frozen=True)
class AlarmSetting:
    chat_id: int
    alarm_time: str | None
    last_sent_date: str | None


class Repository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ---- 학교 -------------------------------------------------------------

    async def add_school(self, user_id: int, chat_id: int, school: School) -> bool:
        affected = await self._db.execute_affected(
            "INSERT OR IGNORE INTO schools "
            "(user_id, chat_id, edu_code, school_code, school_name, location) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, chat_id, school.edu_code, school.school_code, school.name, school.location),
        )
        return affected > 0

    async def list_schools(self, chat_id: int) -> list[SchoolEntry]:
        rows = await self._db.fetchall(
            "SELECT id, edu_code, school_code, school_name, location "
            "FROM schools WHERE chat_id = ? ORDER BY id",
            (chat_id,),
        )
        return [
            SchoolEntry(
                id=int(row["id"]),
                edu_code=str(row["edu_code"]),
                school_code=str(row["school_code"]),
                name=str(row["school_name"]),
                location=str(row["location"] or ""),
            )
            for row in rows
        ]

    async def remove_school(self, chat_id: int, school_id: int) -> bool:
        affected = await self._db.execute_affected(
            "DELETE FROM schools WHERE chat_id = ? AND id = ?",
            (chat_id, school_id),
        )
        return affected > 0

    async def count_schools(self, chat_id: int) -> int:
        row = await self._db.fetchone(
            "SELECT COUNT(*) AS count FROM schools WHERE chat_id = ?", (chat_id,)
        )
        return int(row["count"]) if row is not None else 0

    # ---- 알림 -------------------------------------------------------------

    async def set_alarm(self, chat_id: int, alarm_time: str | None) -> None:
        await self._db.execute(
            "INSERT INTO alarm_settings (chat_id, alarm_time) VALUES (?, ?) "
            "ON CONFLICT (chat_id) DO UPDATE SET alarm_time = excluded.alarm_time",
            (chat_id, alarm_time),
        )

    async def get_alarm(self, chat_id: int) -> AlarmSetting:
        row = await self._db.fetchone(
            "SELECT chat_id, alarm_time, last_sent_date FROM alarm_settings WHERE chat_id = ?",
            (chat_id,),
        )
        if row is None:
            return AlarmSetting(chat_id=chat_id, alarm_time=None, last_sent_date=None)
        return AlarmSetting(
            chat_id=int(row["chat_id"]),
            alarm_time=str(row["alarm_time"]) if row["alarm_time"] is not None else None,
            last_sent_date=(
                str(row["last_sent_date"]) if row["last_sent_date"] is not None else None
            ),
        )

    async def mark_alarm_sent(self, chat_id: int, ymd: str) -> None:
        await self._db.execute(
            "UPDATE alarm_settings SET last_sent_date = ? WHERE chat_id = ?", (ymd, chat_id)
        )

    async def all_alarms(self) -> list[AlarmSetting]:
        rows = await self._db.fetchall(
            "SELECT chat_id, alarm_time, last_sent_date FROM alarm_settings "
            "WHERE alarm_time IS NOT NULL"
        )
        return [
            AlarmSetting(
                chat_id=int(row["chat_id"]),
                alarm_time=str(row["alarm_time"]),
                last_sent_date=(
                    str(row["last_sent_date"]) if row["last_sent_date"] is not None else None
                ),
            )
            for row in rows
        ]

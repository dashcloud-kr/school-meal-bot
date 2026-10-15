"""school-meal-bot 엔트리포인트.

나이스(NEIS) 급식 정보를 조회하고 매일 아침 알림을 보내는 24/7 텔레그램 봇.
"""

from __future__ import annotations

import logging

import httpx
from dotenv import load_dotenv
from telegram import BotCommand, Update

from app.bot import build_application
from app.clients.neis import NeisClient
from app.config import Config
from app.handlers import schoolmeal
from app.services.repository import Repository

MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS schools (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      chat_id INTEGER NOT NULL,
      edu_code TEXT NOT NULL,
      school_code TEXT NOT NULL,
      school_name TEXT NOT NULL,
      location TEXT,
      UNIQUE (chat_id, school_code)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS alarm_settings (
      chat_id INTEGER PRIMARY KEY,
      alarm_time TEXT,
      last_sent_date TEXT
    );
    """,
]

COMMANDS = [
    BotCommand("school", "학교 검색·등록"),
    BotCommand("myschools", "등록한 학교 목록"),
    BotCommand("rmschool", "학교 삭제"),
    BotCommand("meal", "오늘 급식 (내일/날짜 지정 가능)"),
    BotCommand("week", "이번 주 급식"),
    BotCommand("alarm", "아침 급식 알림 설정"),
    BotCommand("start", "시작"),
    BotCommand("help", "명령어 목록"),
    BotCommand("status", "봇 상태"),
    BotCommand("id", "내 chat id"),
]

ALARM_CHECK_INTERVAL_SECONDS = 60


async def setup(application) -> None:
    config: Config = application.bot_data["config"]
    http = httpx.AsyncClient(timeout=20.0)
    application.bot_data["http"] = http
    application.bot_data["neis"] = NeisClient(http, config.neis_api_key)
    application.bot_data["repo"] = Repository(application.bot_data["db"])


async def teardown(application) -> None:
    http: httpx.AsyncClient | None = application.bot_data.get("http")
    if http is not None:
        await http.aclose()


def main() -> None:
    load_dotenv()
    config = Config.from_env()
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    application = build_application(
        config,
        migrations=MIGRATIONS,
        extra_handlers=schoolmeal.handlers(),
        help_text=schoolmeal.SCHOOL_HELP,
        commands=COMMANDS,
        setup=setup,
        teardown=teardown,
    )
    application.job_queue.run_repeating(
        schoolmeal.alarm_job,
        interval=ALARM_CHECK_INTERVAL_SECONDS,
        first=30,
        name="alarm",
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

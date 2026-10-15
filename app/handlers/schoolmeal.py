"""급식 명령어와 아침 알림 잡."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from app.clients.neis import NeisClient, NeisError, School
from app.services.meals import format_meal, format_week
from app.services.repository import Repository

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

SCHOOL_LIMIT = 3
SEARCH_RESULTS_KEY = "school_results"
WEEKDAY_COUNT = 5

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

HTTP_FAIL_MESSAGE = "급식 정보를 가져오지 못했습니다. 잠시 후 다시 시도하세요."
NO_MEAL_MESSAGE = "급식 정보가 없습니다 (휴업일이거나 아직 등록되지 않았어요)."

SCHOOL_HELP = """급식 알림 봇 — 명령어 목록

/school 미금초 — 학교 검색 후 등록 (최대 3개)
/myschools — 등록한 학교 목록
/rmschool 2 — 학교 삭제

/meal — 오늘 급식
/meal 내일 — 내일 급식
/meal 20261020 — 특정 날짜 급식
/week — 이번 주 급식 (월~금)

/alarm 07:30 — 매일 아침 급식 알림
/alarm off — 알림 끄기

/status — 봇 상태 · /id — 내 chat id

출처: 나이스 교육정보 개방포털 (NEIS)"""


def handlers() -> list[CommandHandler | CallbackQueryHandler]:
    return [
        CommandHandler("school", cmd_school),
        CommandHandler("myschools", cmd_myschools),
        CommandHandler("rmschool", cmd_rmschool),
        CommandHandler("meal", cmd_meal),
        CommandHandler("week", cmd_week),
        CommandHandler("alarm", cmd_alarm),
        CallbackQueryHandler(on_register_callback, pattern=r"^reg:\d+$"),
    ]


# ---- 내부 헬퍼 -------------------------------------------------------------


def _repo(context: ContextTypes.DEFAULT_TYPE) -> Repository:
    return context.bot_data["repo"]


def _neis(context: ContextTypes.DEFAULT_TYPE) -> NeisClient:
    return context.bot_data["neis"]


def _ids(update: Update) -> tuple[int, int] | None:
    if update.effective_user is None or update.effective_chat is None:
        return None
    return update.effective_user.id, update.effective_chat.id


async def _say(update: Update, text: str) -> None:
    if update.effective_message is not None:
        await update.effective_message.reply_text(text)


def _today() -> datetime:
    return datetime.now(KST)


def resolve_date(raw: str) -> str | None:
    """'오늘'/'내일'/YYYYMMDD → YYYYMMDD. 잘못된 입력이면 None."""
    today = _today()
    if raw in {"오늘", "today"}:
        return today.strftime("%Y%m%d")
    if raw in {"내일", "tomorrow"}:
        return (today + timedelta(days=1)).strftime("%Y%m%d")
    if re.fullmatch(r"\d{8}", raw):
        try:
            datetime.strptime(raw, "%Y%m%d")
        except ValueError:
            return None
        return raw
    return None


async def _fetch_meals(context: ContextTypes.DEFAULT_TYPE, entry, ymd: str):
    """NeisError/HTTPError를 삼키고 (meals, error_message)를 반환."""
    try:
        return await _neis(context).get_meals(entry.edu_code, entry.school_code, ymd), None
    except NeisError:
        logger.warning("나이스 API 오류", exc_info=True)
        return [], "나이스 API 오류가 발생했습니다. 잠시 후 다시 시도하세요."
    except httpx.HTTPError:
        logger.warning("나이스 통신 실패", exc_info=True)
        return [], HTTP_FAIL_MESSAGE


# ---- 명령어 ----------------------------------------------------------------


async def cmd_school(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await _say(update, "사용법: /school 미금초등학교")
        return
    query = " ".join(context.args)
    try:
        schools = await _neis(context).search_schools(query)
    except NeisError:
        logger.warning("나이스 API 오류", exc_info=True)
        await _say(update, "나이스 API 오류가 발생했습니다. 잠시 후 다시 시도하세요.")
        return
    except httpx.HTTPError:
        logger.warning("나이스 통신 실패", exc_info=True)
        await _say(update, HTTP_FAIL_MESSAGE)
        return

    if not schools:
        await _say(update, f"'{query}' 검색 결과가 없습니다. 학교 이름을 더 정확히 입력해보세요.")
        return

    context.user_data[SEARCH_RESULTS_KEY] = schools
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{school.name} ({school.location})", callback_data=f"reg:{index}"
                )
            ]
            for index, school in enumerate(schools)
        ]
    )
    if update.effective_message is not None:
        await update.effective_message.reply_text(
            "검색 결과 — 등록할 학교를 선택하세요 (최대 3개까지 등록 가능)",
            reply_markup=keyboard,
        )


async def on_register_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    schools: list[School] = context.user_data.get(SEARCH_RESULTS_KEY) or []
    index_text = (query.data or "").removeprefix("reg:")
    if not index_text.isdigit() or int(index_text) >= len(schools):
        await _notify_chat(
            context, query, "검색 결과가 만료됐습니다. /school 로 다시 검색해주세요."
        )
        return

    school = schools[int(index_text)]
    chat = query.message.chat if query.message is not None else None
    user = query.from_user
    if chat is None:
        return

    repo = _repo(context)
    if await repo.count_schools(chat.id) >= SCHOOL_LIMIT:
        await _notify_chat(
            context, query, f"학교는 최대 {SCHOOL_LIMIT}개까지 등록할 수 있습니다."
        )
        return

    if await repo.add_school(user.id, chat.id, school):
        await _notify_chat(
            context,
            query,
            f"등록 완료: {school.name} ({school.location})\n/meal 로 오늘 급식을 확인하세요.",
        )
    else:
        await _notify_chat(context, query, f"{school.name}은(는) 이미 등록되어 있습니다.")


async def _notify_chat(context: ContextTypes.DEFAULT_TYPE, query, text: str) -> None:
    chat = query.message.chat if query.message is not None else None
    if chat is None:
        return
    try:
        await context.bot.send_message(chat_id=chat.id, text=text)
    except TelegramError:
        logger.warning("메시지 전송 실패", exc_info=True)


async def cmd_myschools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    _user_id, chat_id = ids
    schools = await _repo(context).list_schools(chat_id)
    if not schools:
        await _say(update, "등록된 학교가 없습니다. /school 미금초 로 검색해보세요.")
        return
    lines = ["등록한 학교"]
    for entry in schools:
        lines.append(f"#{entry.id} {entry.name} ({entry.location})")
    await _say(update, "\n".join(lines))


async def cmd_rmschool(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    _user_id, chat_id = ids
    if not context.args or not context.args[0].isdigit():
        await _say(update, "사용법: /rmschool 2 (/myschools 에서 번호 확인)")
        return
    removed = await _repo(context).remove_school(chat_id, int(context.args[0]))
    await _say(update, "삭제했습니다." if removed else "해당 번호의 학교가 없습니다.")


async def cmd_meal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    _user_id, chat_id = ids
    raw = context.args[0] if context.args else "오늘"
    ymd = resolve_date(raw)
    if ymd is None:
        await _say(update, "사용법: /meal · /meal 내일 · /meal 20261020")
        return

    schools = await _repo(context).list_schools(chat_id)
    if not schools:
        await _say(update, "등록된 학교가 없습니다. /school 미금초 로 검색해보세요.")
        return

    for entry in schools:
        meals, error = await _fetch_meals(context, entry, ymd)
        if error:
            await _say(update, error)
            continue
        if not meals:
            await _say(update, f"{entry.name}: {NO_MEAL_MESSAGE}")
            continue
        for meal in meals:
            await _say(update, format_meal(entry.name, meal))


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    _user_id, chat_id = ids
    schools = await _repo(context).list_schools(chat_id)
    if not schools:
        await _say(update, "등록된 학교가 없습니다. /school 미금초 로 검색해보세요.")
        return

    today = _today()
    monday = today - timedelta(days=today.weekday())
    days = [(monday + timedelta(days=offset)).strftime("%Y%m%d") for offset in range(WEEKDAY_COUNT)]

    for entry in schools:
        weekly_meals = []
        for ymd in days:
            meals, error = await _fetch_meals(context, entry, ymd)
            if error:
                await _say(update, error)
                weekly_meals = []
                break
            weekly_meals.extend(meal for meal in meals if meal.meal_type == "중식")
        if not weekly_meals:
            await _say(update, f"{entry.name}: 이번 주 급식 정보가 없습니다.")
            continue
        for chunk in format_week(entry.name, weekly_meals):
            await _say(update, chunk)


async def cmd_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    _user_id, chat_id = ids
    repo = _repo(context)

    if not context.args:
        setting = await repo.get_alarm(chat_id)
        state = f"{setting.alarm_time} (KST)" if setting.alarm_time else "꺼짐"
        await _say(update, f"아침 급식 알림: {state}\n사용법: /alarm 07:30 또는 /alarm off")
        return

    arg = context.args[0].lower()
    if arg in {"off", "끄기", "해제"}:
        await repo.set_alarm(chat_id, None)
        await _say(update, "아침 급식 알림을 껐습니다.")
        return
    if not TIME_RE.match(arg):
        await _say(update, "시간은 HH:MM 형식으로 입력하세요. 예: /alarm 07:30")
        return
    await repo.set_alarm(chat_id, arg)
    await _say(
        update,
        f"아침 급식 알림을 {arg} (KST)로 설정했습니다. "
        "매일 그 시각에 오늘 중식이 전송됩니다.",
    )


# ---- 백그라운드 잡 ---------------------------------------------------------


async def alarm_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """매 분 확인해 설정 시각이 되면 오늘 중식을 보낸다 (하루 1회)."""
    now = _today()
    hhmm = now.strftime("%H:%M")
    today = now.strftime("%Y%m%d")

    repo = _repo(context)
    for setting in await repo.all_alarms():
        if setting.alarm_time != hhmm or setting.last_sent_date == today:
            continue
        schools = await repo.list_schools(setting.chat_id)
        if not schools:
            await repo.mark_alarm_sent(setting.chat_id, today)
            continue

        sent_any = False
        for entry in schools:
            meals, error = await _fetch_meals(context, entry, today)
            if error:
                continue
            lunch = next((m for m in meals if m.meal_type == "중식"), meals[0] if meals else None)
            if lunch is None:
                continue
            try:
                await context.bot.send_message(
                    chat_id=setting.chat_id, text=format_meal(entry.name, lunch)
                )
                sent_any = True
            except TelegramError:
                logger.warning("알림 전송 실패 (chat_id=%s)", setting.chat_id, exc_info=True)
        if sent_any:
            await repo.mark_alarm_sent(setting.chat_id, today)

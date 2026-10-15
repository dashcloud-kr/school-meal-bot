"""급식 명령어 핸들러 테스트."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.handlers import schoolmeal
from tests.factories import make_callback_update, make_context, make_message_update
from tests.stubs import FailingNeis, StubNeis, make_meal, make_school


def _ctx(update, repo, neis):
    message = update.effective_message
    args = message.text.split()[1:] if message is not None and message.text else []
    return make_context(args=args, bot_data={"repo": repo, "neis": neis})


def _texts(update) -> list[str]:
    return [call.kwargs["text"] for call in update.get_bot().send_message.await_args_list]


def _last(update) -> str:
    return _texts(update)[-1]


def _ctx_texts(ctx) -> list[str]:
    return [call.kwargs["text"] for call in ctx.bot.send_message.await_args_list]


def _today_ymd() -> str:
    return datetime.now(schoolmeal.KST).strftime("%Y%m%d")


# ---- /school + 콜백 ---------------------------------------------------------


async def test_school_사용법과_검색결과없음(repo):
    update = make_message_update("/school")
    await schoolmeal.cmd_school(update, _ctx(update, repo, StubNeis()))
    assert "사용법" in _last(update)

    update = make_message_update("/school 없는학교")
    await schoolmeal.cmd_school(update, _ctx(update, repo, StubNeis()))
    assert "검색 결과가 없습니다" in _last(update)


async def test_school_검색과_등록_콜백(repo):
    neis = StubNeis(schools=[make_school(), make_school("7551076", "성남양지초등학교")])
    update = make_message_update("/school 미금초")
    ctx = _ctx(update, repo, neis)
    await schoolmeal.cmd_school(update, ctx)

    assert neis.search_calls == ["미금초"]
    bot = update.get_bot()
    bot.send_message.assert_awaited_once()
    call = bot.send_message.await_args
    assert "검색 결과" in call.kwargs["text"]
    assert call.kwargs["reply_markup"] is not None

    # 콜백으로 첫 번째 학교 등록
    callback = make_callback_update("reg:0")
    await schoolmeal.on_register_callback(callback, ctx)

    schools = await repo.list_schools(100)
    assert len(schools) == 1
    assert schools[0].name == "성남미금초등학교"
    assert any("등록 완료" in text for text in _ctx_texts(ctx))


async def test_school_콜백_만료(repo):
    ctx = make_context(bot_data={"repo": repo, "neis": StubNeis()})
    callback = make_callback_update("reg:0")
    await schoolmeal.on_register_callback(callback, ctx)
    assert any("만료" in text for text in _ctx_texts(ctx))


async def test_school_등록_한도와_중복(repo):
    neis = StubNeis(schools=[make_school()])
    update = make_message_update("/school 미금초")
    ctx = _ctx(update, repo, neis)
    await schoolmeal.cmd_school(update, ctx)

    callback = make_callback_update("reg:0")
    await schoolmeal.on_register_callback(callback, ctx)
    await schoolmeal.on_register_callback(callback, ctx)  # 중복
    assert any("이미 등록" in text for text in _ctx_texts(ctx))

    for code in ("A1", "A2"):
        await repo.add_school(100, 100, make_school(code, f"{code}초"))
    await schoolmeal.on_register_callback(callback, ctx)  # 한도 초과
    assert any("최대 3개" in text for text in _ctx_texts(ctx))


# ---- /myschools, /rmschool --------------------------------------------------


async def test_myschools_빈목록과_목록(repo):
    update = make_message_update("/myschools")
    await schoolmeal.cmd_myschools(update, _ctx(update, repo, StubNeis()))
    assert "등록된 학교가 없습니다" in _last(update)

    await repo.add_school(100, 100, make_school())
    update = make_message_update("/myschools")
    await schoolmeal.cmd_myschools(update, _ctx(update, repo, StubNeis()))
    assert "성남미금초등학교" in _last(update)


async def test_rmschool(repo):
    await repo.add_school(100, 100, make_school())
    schools = await repo.list_schools(100)

    update = make_message_update(f"/rmschool {schools[0].id}")
    await schoolmeal.cmd_rmschool(update, _ctx(update, repo, StubNeis()))
    assert "삭제했습니다" in _last(update)

    update = make_message_update("/rmschool abc")
    await schoolmeal.cmd_rmschool(update, _ctx(update, repo, StubNeis()))
    assert "사용법" in _last(update)


# ---- /meal ------------------------------------------------------------------


async def test_meal_학교_없으면_안내(repo):
    update = make_message_update("/meal")
    await schoolmeal.cmd_meal(update, _ctx(update, repo, StubNeis()))
    assert "등록된 학교가 없습니다" in _last(update)


async def test_meal_오늘(repo):
    await repo.add_school(100, 100, make_school())
    neis = StubNeis(meals={_today_ymd(): [make_meal(_today_ymd())]})
    update = make_message_update("/meal")
    await schoolmeal.cmd_meal(update, _ctx(update, repo, neis))
    text = _last(update)
    assert "성남미금초등학교 · 중식" in text
    assert "베이컨김치볶음밥" in text


async def test_meal_내일(repo):
    await repo.add_school(100, 100, make_school())
    tomorrow = (datetime.now(schoolmeal.KST) + timedelta(days=1)).strftime("%Y%m%d")
    neis = StubNeis(meals={tomorrow: [make_meal(tomorrow)]})
    update = make_message_update("/meal 내일")
    await schoolmeal.cmd_meal(update, _ctx(update, repo, neis))
    assert "중식" in _last(update)


async def test_meal_급식_없는_날(repo):
    await repo.add_school(100, 100, make_school())
    update = make_message_update("/meal 20261018")
    await schoolmeal.cmd_meal(update, _ctx(update, repo, StubNeis()))
    assert "급식 정보가 없습니다" in _last(update)


async def test_meal_잘못된_날짜(repo):
    update = make_message_update("/meal 어제")
    await schoolmeal.cmd_meal(update, _ctx(update, repo, StubNeis()))
    assert "사용법" in _last(update)


async def test_meal_나이스_오류(repo):
    await repo.add_school(100, 100, make_school())
    update = make_message_update("/meal")
    await schoolmeal.cmd_meal(update, _ctx(update, repo, FailingNeis()))
    assert "오류" in _last(update)


# ---- /week ------------------------------------------------------------------


async def test_week_주간(repo):
    await repo.add_school(100, 100, make_school())
    today = datetime.now(schoolmeal.KST)
    monday = today - timedelta(days=today.weekday())
    meals = {
        (monday + timedelta(days=offset)).strftime("%Y%m%d"): [
            make_meal((monday + timedelta(days=offset)).strftime("%Y%m%d"))
        ]
        for offset in range(5)
    }
    update = make_message_update("/week")
    await schoolmeal.cmd_week(update, _ctx(update, repo, StubNeis(meals=meals)))
    text = _last(update)
    assert "주간 급식" in text
    assert text.count("중식") == 5


# ---- /alarm -----------------------------------------------------------------


async def test_alarm_상태와_설정(repo):
    update = make_message_update("/alarm")
    await schoolmeal.cmd_alarm(update, _ctx(update, repo, StubNeis()))
    assert "꺼짐" in _last(update)

    update = make_message_update("/alarm 07:30")
    await schoolmeal.cmd_alarm(update, _ctx(update, repo, StubNeis()))
    assert "07:30" in _last(update)
    assert (await repo.get_alarm(100)).alarm_time == "07:30"

    update = make_message_update("/alarm 25:99")
    await schoolmeal.cmd_alarm(update, _ctx(update, repo, StubNeis()))
    assert "HH:MM" in _last(update)

    update = make_message_update("/alarm off")
    await schoolmeal.cmd_alarm(update, _ctx(update, repo, StubNeis()))
    assert (await repo.get_alarm(100)).alarm_time is None


def test_resolve_date():
    today = datetime.now(schoolmeal.KST)
    assert schoolmeal.resolve_date("오늘") == today.strftime("%Y%m%d")
    assert schoolmeal.resolve_date("내일") == (today + timedelta(days=1)).strftime("%Y%m%d")
    assert schoolmeal.resolve_date("20261014") == "20261014"
    assert schoolmeal.resolve_date("20261399") is None
    assert schoolmeal.resolve_date("어제") is None

"""아침 알림 잡 테스트."""

from __future__ import annotations

from datetime import datetime

from app.handlers import schoolmeal
from tests.factories import make_context
from tests.stubs import FailingNeis, StubNeis, make_meal, make_school


def _ctx(repo, neis):
    return make_context(bot_data={"repo": repo, "neis": neis})


def _texts(ctx) -> list[str]:
    return [call.kwargs["text"] for call in ctx.bot.send_message.await_args_list]


def _now_hhmm() -> str:
    return datetime.now(schoolmeal.KST).strftime("%H:%M")


def _today() -> str:
    return datetime.now(schoolmeal.KST).strftime("%Y%m%d")


async def test_설정시각에_중식_발송(repo):
    await repo.add_school(100, 100, make_school())
    await repo.set_alarm(100, _now_hhmm())
    neis = StubNeis(meals={_today(): [make_meal(_today(), "석식"), make_meal(_today(), "중식")]})
    ctx = _ctx(repo, neis)

    await schoolmeal.alarm_job(ctx)

    assert ctx.bot.send_message.await_count == 1
    text = _texts(ctx)[0]
    assert "중식" in text  # 석식이 아니라 중식
    assert "베이컨김치볶음밥" in text
    assert (await repo.get_alarm(100)).last_sent_date == _today()


async def test_같은_날_중복_발송_없음(repo):
    await repo.add_school(100, 100, make_school())
    await repo.set_alarm(100, _now_hhmm())
    neis = StubNeis(meals={_today(): [make_meal(_today())]})
    ctx = _ctx(repo, neis)

    await schoolmeal.alarm_job(ctx)
    assert ctx.bot.send_message.await_count == 1

    await schoolmeal.alarm_job(ctx)  # 같은 분에 다시 실행
    assert ctx.bot.send_message.await_count == 1


async def test_다른_시각이면_발송없음(repo):
    await repo.add_school(100, 100, make_school())
    await repo.set_alarm(100, "03:33")
    neis = StubNeis(meals={_today(): [make_meal(_today())]})
    ctx = _ctx(repo, neis)

    await schoolmeal.alarm_job(ctx)
    assert ctx.bot.send_message.await_count == 0


async def test_학교_없으면_발송없이_기록(repo):
    await repo.set_alarm(100, _now_hhmm())
    ctx = _ctx(repo, StubNeis(meals={_today(): [make_meal(_today())]}))

    await schoolmeal.alarm_job(ctx)
    assert ctx.bot.send_message.await_count == 0
    assert (await repo.get_alarm(100)).last_sent_date == _today()


async def test_급식_없는_날은_발송없음(repo):
    await repo.add_school(100, 100, make_school())
    await repo.set_alarm(100, _now_hhmm())
    ctx = _ctx(repo, StubNeis(meals={}))

    await schoolmeal.alarm_job(ctx)
    assert ctx.bot.send_message.await_count == 0


async def test_나이스_오류에도_잡은_계속(repo):
    await repo.add_school(100, 100, make_school())
    await repo.set_alarm(100, _now_hhmm())
    ctx = _ctx(repo, FailingNeis())

    await schoolmeal.alarm_job(ctx)  # 예외가 새어 나오면 실패
    assert ctx.bot.send_message.await_count == 0


async def test_여러_학교_각각_발송(repo):
    await repo.add_school(100, 100, make_school("A", "A초"))
    await repo.add_school(100, 100, make_school("B", "B초"))
    await repo.set_alarm(100, _now_hhmm())
    neis = StubNeis(meals={_today(): [make_meal(_today())]})
    ctx = _ctx(repo, neis)

    await schoolmeal.alarm_job(ctx)
    assert ctx.bot.send_message.await_count == 2
    texts = " ".join(_texts(ctx))
    assert "A초" in texts
    assert "B초" in texts

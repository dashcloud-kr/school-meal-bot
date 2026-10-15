"""Repository (학교·알림) 테스트."""

from __future__ import annotations

from app.clients.neis import School


def make_school(code: str = "7551075", name: str = "성남미금초등학교") -> School:
    return School(
        edu_code="J10",
        school_code=code,
        name=name,
        location="경기도",
        address="경기도 성남시 분당구 미금로 151",
    )


async def test_학교_등록_중복_목록_삭제(repo):
    assert await repo.add_school(1, 100, make_school()) is True
    assert await repo.add_school(1, 100, make_school()) is False  # 같은 채팅 중복
    assert await repo.add_school(1, 200, make_school()) is True  # 다른 채팅은 가능

    schools = await repo.list_schools(100)
    assert len(schools) == 1
    assert schools[0].name == "성남미금초등학교"
    assert schools[0].location == "경기도"

    assert await repo.remove_school(100, schools[0].id) is True
    assert await repo.remove_school(100, schools[0].id) is False
    assert await repo.list_schools(100) == []


async def test_학교_개수(repo):
    assert await repo.count_schools(100) == 0
    await repo.add_school(1, 100, make_school("A", "A초"))
    await repo.add_school(1, 100, make_school("B", "B초"))
    assert await repo.count_schools(100) == 2


async def test_알림_설정과_기록(repo):
    setting = await repo.get_alarm(100)
    assert setting.alarm_time is None

    await repo.set_alarm(100, "07:30")
    setting = await repo.get_alarm(100)
    assert setting.alarm_time == "07:30"
    assert setting.last_sent_date is None

    await repo.mark_alarm_sent(100, "20261015")
    setting = await repo.get_alarm(100)
    assert setting.last_sent_date == "20261015"

    await repo.set_alarm(100, None)
    setting = await repo.get_alarm(100)
    assert setting.alarm_time is None


async def test_전체_알림_목록은_설정된_것만(repo):
    await repo.set_alarm(100, "07:30")
    await repo.set_alarm(200, None)
    await repo.set_alarm(300, "08:00")

    alarms = await repo.all_alarms()
    assert sorted(a.chat_id for a in alarms) == [100, 300]


async def test_마이그레이션_재적용_안전(tmp_path):
    from app.db import Database
    from app.services.repository import Repository
    from bot import MIGRATIONS

    path = tmp_path / "again.db"
    first = Database(path)
    await first.connect(MIGRATIONS)
    await Repository(first).add_school(1, 100, make_school())
    await first.close()

    second = Database(path)
    await second.connect(MIGRATIONS)
    try:
        assert len(await Repository(second).list_schools(100)) == 1
    finally:
        await second.close()

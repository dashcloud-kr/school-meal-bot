"""핸들러 테스트용 스텁."""

from __future__ import annotations

from app.clients.neis import Meal, NeisError, School
from app.services.meals import parse_dishes

RAW_DISHES = "베이컨김치볶음밥 (1.2.5)<br/>맑은콩나물국 (5.6)"


def make_school(code: str = "7551075", name: str = "성남미금초등학교") -> School:
    return School(
        edu_code="J10",
        school_code=code,
        name=name,
        location="경기도",
        address="경기도 성남시 분당구 미금로 151",
    )


def make_meal(ymd: str = "20261014", meal_type: str = "중식") -> Meal:
    return Meal(
        date=ymd,
        meal_type=meal_type,
        dishes=parse_dishes(RAW_DISHES),
        calories="625.5 Kcal",
        headcount=None,
    )


class StubNeis:
    def __init__(self, schools: list[School] | None = None, meals: dict | None = None) -> None:
        self._schools = schools or []
        self._meals = meals or {}
        self.search_calls: list[str] = []

    async def search_schools(self, name: str, size: int = 5) -> list[School]:
        self.search_calls.append(name)
        return self._schools

    async def get_meals(self, edu_code: str, school_code: str, ymd: str) -> list[Meal]:
        return list(self._meals.get(ymd, []))


class FailingNeis:
    async def search_schools(self, name: str, size: int = 5):
        raise NeisError("ERROR-290")

    async def get_meals(self, edu_code: str, school_code: str, ymd: str):
        raise NeisError("ERROR-290")

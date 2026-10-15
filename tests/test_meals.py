"""급식 파싱·포맷 테스트."""

from __future__ import annotations

from app.clients.neis import Meal
from app.services.meals import (
    ALLERGY_NAMES,
    Dish,
    format_date,
    format_meal,
    format_week,
    parse_dishes,
)

RAW_DISHES = (
    "베이컨김치볶음밥 (1.2.5.6.9.10.13.16.18)<br/>"
    "맑은콩나물국 (5.6)<br/>"
    "리얼고구마치즈돈카츠/소스 (2.5.6.10.12.17.18)<br/>"
    "심쿵하트단무지 <br/>"
    "파인애플 "
)


def test_요리_파싱():
    dishes = parse_dishes(RAW_DISHES)
    assert len(dishes) == 5
    assert dishes[0].name == "베이컨김치볶음밥"
    assert dishes[0].allergens == [1, 2, 5, 6, 9, 10, 13, 16, 18]
    assert dishes[3].name == "심쿵하트단무지"
    assert dishes[3].allergens == []
    assert dishes[4].name == "파인애플"


def test_빈_입력():
    assert parse_dishes("") == []
    assert parse_dishes("<br/><br/>") == []


def test_알레르기_매핑():
    assert ALLERGY_NAMES[1] == "난류"
    assert ALLERGY_NAMES[16] == "쇠고기"
    assert ALLERGY_NAMES[19] == "잣"


def test_날짜_포맷():
    assert format_date("20261014") == "10/14 (수)"
    assert format_date("20261019") == "10/19 (월)"
    assert format_date("invalid") == "invalid"


def make_meal(ymd: str = "20261014", meal_type: str = "중식") -> Meal:
    return Meal(
        date=ymd,
        meal_type=meal_type,
        dishes=parse_dishes(RAW_DISHES),
        calories="625.5 Kcal",
        headcount="670.0",
    )


def test_급식_메시지():
    text = format_meal("성남미금초등학교", make_meal())
    assert "성남미금초등학교 · 중식 (10/14 (수))" in text
    assert (
        "베이컨김치볶음밥 (난류, 우유, 대두, 밀, 새우, 돼지고기, 아황산류, 쇠고기, 조개류)"
        in text
    )
    assert "심쿵하트단무지" in text
    assert "625.5 Kcal" in text


def test_주간_급식_분할():
    meals = [make_meal(ymd=f"2026101{i}") for i in range(5, 10)]
    chunks = format_week("테스트초등학교", meals)
    assert len(chunks) >= 1
    assert "테스트초등학교 주간 급식" in chunks[0]
    assert all(len(chunk) <= 4096 for chunk in chunks)


def test_Dish_기본값():
    dish = Dish(name="밥")
    assert dish.allergens == []

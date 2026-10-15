"""급식 데이터 파싱과 메시지 포맷 (순수 함수)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.utils.text import chunk_text

ALLERGY_NAMES: dict[int, str] = {
    1: "난류",
    2: "우유",
    3: "메밀",
    4: "땅콩",
    5: "대두",
    6: "밀",
    7: "고등어",
    8: "게",
    9: "새우",
    10: "돼지고기",
    11: "복숭아",
    12: "토마토",
    13: "아황산류",
    14: "호두",
    15: "닭고기",
    16: "쇠고기",
    17: "오징어",
    18: "조개류",
    19: "잣",
}

_DISH_RE = re.compile(r"^(?P<name>.+?)\s*(?:\((?P<codes>[\d.]+)\))?\s*$")

_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


@dataclass(frozen=True)
class Dish:
    name: str
    allergens: list[int] = field(default_factory=list)


def parse_dishes(raw: str) -> list[Dish]:
    """'베이컨김치볶음밥 (1.2.5)<br/>맑은국 (5.6)' → [Dish, Dish]."""
    dishes: list[Dish] = []
    for part in raw.split("<br/>"):
        text = part.strip()
        if not text:
            continue
        match = _DISH_RE.match(text)
        if match is None:
            dishes.append(Dish(name=text))
            continue
        name = match.group("name").strip()
        if not name:
            continue
        codes = (
            [int(code) for code in match.group("codes").split(".") if code]
            if match.group("codes")
            else []
        )
        dishes.append(Dish(name=name, allergens=codes))
    return dishes


def format_date(ymd: str) -> str:
    """'20261014' → '10/14 (화)'. 형식이 다르면 원문 반환."""
    try:
        parsed = datetime.strptime(ymd, "%Y%m%d")
    except ValueError:
        return ymd
    return f"{parsed.month}/{parsed.day} ({_WEEKDAYS[parsed.weekday()]})"


def format_meal(school_name: str, meal) -> str:
    """급식 한 끼를 메시지로 만든다. meal: app.clients.neis.Meal."""
    lines = [f"{school_name} · {meal.meal_type} ({format_date(meal.date)})"]
    for dish in meal.dishes:
        if dish.allergens:
            names = ", ".join(ALLERGY_NAMES.get(code, str(code)) for code in dish.allergens)
            lines.append(f"· {dish.name} ({names})")
        else:
            lines.append(f"· {dish.name}")
    if meal.calories:
        lines.append(meal.calories)
    return "\n".join(lines)


def format_week(school_name: str, meals) -> list[str]:
    """주간 급식을 메시지 청크 목록으로 만든다 (4096자 자동 분할)."""
    lines = [f"{school_name} 주간 급식"]
    for meal in meals:
        lines.append("")
        lines.append(f"[{format_date(meal.date)}] {meal.meal_type}")
        for dish in meal.dishes:
            lines.append(f"· {dish.name}")
    return chunk_text("\n".join(lines))

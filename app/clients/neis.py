"""나이스(NEIS) 교육정보 API 클라이언트."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://open.neis.go.kr/hub"

SUCCESS_CODES = {"INFO-000"}
NO_DATA_CODES = {"INFO-200"}


class NeisError(RuntimeError):
    """나이스 API 오류 (키 오류·서버 오류 등)."""


@dataclass(frozen=True)
class School:
    edu_code: str  # ATPT_OFCDC_SC_CODE (시도교육청코드)
    school_code: str  # SD_SCHUL_CODE (행정표준코드)
    name: str  # SCHUL_NM
    location: str  # LCTN_SC_NM (예: 경기도)
    address: str  # ORG_RDNMA (도로명주소)


@dataclass(frozen=True)
class Meal:
    date: str  # YYYYMMDD
    meal_type: str  # 중식 / 석식
    dishes: list  # list[app.services.meals.Dish]
    calories: str | None
    headcount: str | None


def _result_code(payload: dict[str, Any], service: str) -> str | None:
    """응답에서 RESULT 코드를 추출한다. 데이터 없음(INFO-200)이면 None 대신 코드 반환."""
    if service in payload:
        head = payload[service][0].get("head", [])
        for entry in head:
            if "RESULT" in entry:
                return str(entry["RESULT"].get("CODE", ""))
        return "INFO-000"
    top_result = payload.get("RESULT")
    if isinstance(top_result, dict):
        return str(top_result.get("CODE", ""))
    return None


def _rows(payload: dict[str, Any], service: str) -> list[dict[str, Any]]:
    if service not in payload or len(payload[service]) < 2:
        return []
    return list(payload[service][1].get("row", []))


class NeisClient:
    def __init__(self, http: httpx.AsyncClient, api_key: str) -> None:
        self._http = http
        self._api_key = api_key

    async def _get(self, path: str, service: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        query = {"KEY": self._api_key, "Type": "json", "pIndex": 1, **params}
        response = await self._http.get(f"{BASE_URL}/{path}", params=query)
        response.raise_for_status()
        payload = response.json()

        code = _result_code(payload, service)
        if code in NO_DATA_CODES:
            return []
        if code not in SUCCESS_CODES:
            message = code or "알 수 없는 응답"
            raise NeisError(f"나이스 API 오류: {message}")
        return _rows(payload, service)

    async def search_schools(self, name: str, size: int = 5) -> list[School]:
        """학교 이름으로 검색한다 (최대 size개)."""
        rows = await self._get(
            "schoolInfo", "schoolInfo", {"pSize": size, "SCHUL_NM": name}
        )
        return [
            School(
                edu_code=str(row.get("ATPT_OFCDC_SC_CODE", "")),
                school_code=str(row.get("SD_SCHUL_CODE", "")),
                name=str(row.get("SCHUL_NM", "")),
                location=str(row.get("LCTN_SC_NM", "")),
                address=str(row.get("ORG_RDNMA", "")),
            )
            for row in rows
            if row.get("SD_SCHUL_CODE")
        ]

    async def get_meals(self, edu_code: str, school_code: str, ymd: str) -> list[Meal]:
        """특정 날짜(YYYYMMDD)의 급식 목록을 조회한다."""
        from app.services.meals import parse_dishes

        rows = await self._get(
            "mealServiceDietInfo",
            "mealServiceDietInfo",
            {
                "pSize": 10,
                "ATPT_OFCDC_SC_CODE": edu_code,
                "SD_SCHUL_CODE": school_code,
                "MLSV_YMD": ymd,
            },
        )
        meals: list[Meal] = []
        for row in rows:
            dishes = parse_dishes(str(row.get("DDISH_NM", "")))
            if not dishes:
                continue
            meals.append(
                Meal(
                    date=str(row.get("MLSV_YMD", ymd)),
                    meal_type=str(row.get("MMEAL_SC_NM", "급식")),
                    dishes=dishes,
                    calories=str(row.get("CAL_INFO", "")).strip() or None,
                    headcount=str(row.get("MLSV_FGR", "")).strip() or None,
                )
            )
        return meals

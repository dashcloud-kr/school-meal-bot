"""나이스 클라이언트 테스트 (respx 모킹)."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.clients.neis import BASE_URL, NeisClient, NeisError

SCHOOL_PAYLOAD = {
    "schoolInfo": [
        {
            "head": [
                {"list_total_count": 1},
                {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."}},
            ]
        },
        {
            "row": [
                {
                    "ATPT_OFCDC_SC_CODE": "J10",
                    "SD_SCHUL_CODE": "7551075",
                    "SCHUL_NM": "성남미금초등학교",
                    "LCTN_SC_NM": "경기도",
                    "ORG_RDNMA": "경기도 성남시 분당구 미금로 151",
                }
            ]
        },
    ]
}

MEAL_PAYLOAD = {
    "mealServiceDietInfo": [
        {
            "head": [
                {"list_total_count": 1},
                {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."}},
            ]
        },
        {
            "row": [
                {
                    "MLSV_YMD": "20261014",
                    "MMEAL_SC_NM": "중식",
                    "DDISH_NM": "베이컨김치볶음밥 (1.2.5)<br/>맑은콩나물국 (5.6)",
                    "CAL_INFO": "625.5 Kcal",
                    "MLSV_FGR": "670.0",
                }
            ]
        },
    ]
}

NO_DATA_PAYLOAD = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
ERROR_PAYLOAD = {"RESULT": {"CODE": "ERROR-290", "MESSAGE": "인증키가 유효하지 않습니다."}}


@pytest.fixture
def http():
    return httpx.AsyncClient()


@respx.mock
async def test_학교_검색(http):
    route = respx.get(f"{BASE_URL}/schoolInfo").mock(
        return_value=httpx.Response(200, json=SCHOOL_PAYLOAD)
    )
    client = NeisClient(http, "test-key")
    schools = await client.search_schools("미금초")

    assert len(schools) == 1
    assert schools[0].edu_code == "J10"
    assert schools[0].school_code == "7551075"
    assert schools[0].name == "성남미금초등학교"
    assert schools[0].location == "경기도"
    request_params = route.calls[0].request.url.params
    assert request_params["KEY"] == "test-key"
    assert request_params["SCHUL_NM"] == "미금초"
    assert request_params["Type"] == "json"


@respx.mock
async def test_급식_조회(http):
    route = respx.get(f"{BASE_URL}/mealServiceDietInfo").mock(
        return_value=httpx.Response(200, json=MEAL_PAYLOAD)
    )
    client = NeisClient(http, "test-key")
    meals = await client.get_meals("J10", "7551075", "20261014")

    assert len(meals) == 1
    meal = meals[0]
    assert meal.meal_type == "중식"
    assert meal.date == "20261014"
    assert [dish.name for dish in meal.dishes] == ["베이컨김치볶음밥", "맑은콩나물국"]
    assert meal.dishes[0].allergens == [1, 2, 5]
    assert meal.calories == "625.5 Kcal"

    request_params = route.calls[0].request.url.params
    assert request_params["SD_SCHUL_CODE"] == "7551075"
    assert request_params["MLSV_YMD"] == "20261014"


@respx.mock
async def test_데이터_없음은_빈_목록(http):
    respx.get(f"{BASE_URL}/mealServiceDietInfo").mock(
        return_value=httpx.Response(200, json=NO_DATA_PAYLOAD)
    )
    client = NeisClient(http, "test-key")
    assert await client.get_meals("J10", "7551075", "20261018") == []


@respx.mock
async def test_인증키_오류는_예외(http):
    respx.get(f"{BASE_URL}/schoolInfo").mock(
        return_value=httpx.Response(200, json=ERROR_PAYLOAD)
    )
    client = NeisClient(http, "bad-key")
    with pytest.raises(NeisError, match="ERROR-290"):
        await client.search_schools("미금초")


@respx.mock
async def test_HTTP_오류는_예외(http):
    respx.get(f"{BASE_URL}/schoolInfo").mock(return_value=httpx.Response(500))
    client = NeisClient(http, "test-key")
    with pytest.raises(httpx.HTTPStatusError):
        await client.search_schools("미금초")


@respx.mock
async def test_학교코드_없는_행은_제외(http):
    payload = {
        "schoolInfo": [
            {"head": [{"RESULT": {"CODE": "INFO-000"}}]},
            {"row": [{"SCHUL_NM": "이름만 있음"}]},
        ]
    }
    respx.get(f"{BASE_URL}/schoolInfo").mock(return_value=httpx.Response(200, json=payload))
    client = NeisClient(http, "test-key")
    assert await client.search_schools("x") == []


@respx.mock
async def test_요리_없는_급식행은_제외(http):
    payload = {
        "mealServiceDietInfo": [
            {"head": [{"RESULT": {"CODE": "INFO-000"}}]},
            {"row": [{"MLSV_YMD": "20261014", "MMEAL_SC_NM": "중식", "DDISH_NM": ""}]},
        ]
    }
    respx.get(f"{BASE_URL}/mealServiceDietInfo").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = NeisClient(http, "test-key")
    assert await client.get_meals("J10", "7551075", "20261014") == []

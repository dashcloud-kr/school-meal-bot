# school-meal-bot — 24/7 급식 알림 텔레그램 봇

[![CI](https://github.com/dashcloud-kr/school-meal-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/dashcloud-kr/school-meal-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

나이스(NEIS) 교육정보로 **우리 아이 학교 급식**을 조회하고, **매일 아침 알림**을 보내주는 텔레그램 봇입니다.
알레르기 유발물질을 한글 이름으로 풀어서 보여줍니다. [대시클라우드(DashCloud)](https://dashcloud.kr)에서 **평생 무료로 24시간** 가동할 수 있습니다.

> **English** — A Telegram bot for Korean school meal info (NEIS open API): search & register schools, check today/tomorrow/weekly meals with allergen names, and get a daily morning notification. Built to run 24/7 on [DashCloud](https://dashcloud.kr) for free.

## 기능

| 기능 | 설명 |
| --- | --- |
| 학교 검색·등록 | `/school 미금초` → 검색 결과 버튼으로 등록 (최대 3개 — 다자녀 지원) |
| 오늘/내일/날짜 급식 | `/meal`, `/meal 내일`, `/meal 20261020` |
| 주간 급식 | `/week` — 이번 주 월~금 중식 |
| 알레르기 한글 표기 | `(1.2.5.16)` → `(난류, 우유, 대두, 쇠고기)` |
| 아침 알림 | `/alarm 07:30` — 매일 그 시각 오늘 중식 자동 발송 (하루 1회) |
| 칼로리 표시 | 급식 칼로리 포함 |
| 휴업일 처리 | 급식이 없는 날은 안내 메시지 |

## 명령어

```
/school 미금초          학교 검색 후 등록
/myschools /rmschool 2  등록한 학교 목록/삭제

/meal                   오늘 급식
/meal 내일              내일 급식
/meal 20261020          특정 날짜
/week                   이번 주 급식 (월~금)

/alarm 07:30            아침 급식 알림
/alarm off              알림 끄기
/status /id             봇 상태 / 내 chat id
```

## 준비물 — NEIS API 키 (무료, 즉시 발급)

1. [open.neis.go.kr](https://open.neis.go.kr) 회원가입
2. **인증키 발급** 메뉴에서 신청 → 즉시 발급
3. `.env`의 `NEIS_API_KEY`에 입력

## 30초 로컬 실행

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env 에 TELEGRAM_BOT_TOKEN, NEIS_API_KEY 입력

python bot.py
```

## DashCloud로 24시간 무료 가동

1. [dashcloud.kr](https://dashcloud.kr) 가입 — 휴대폰 인증 1회, 결제 정보 불필요
2. 이 폴더를 대시보드에 **드래그 앤 드롭**
3. 환경변수에 `TELEGRAM_BOT_TOKEN`, `NEIS_API_KEY` 등록
4. 배포 — `dashcloud.json`이 런타임(Python 3.12)과 진입점을 자동 설정합니다

> 노트북을 덮어도 봇이 계속 돌아갑니다. Free 플랜은 평생 무료이며 갱신·슬립이 없습니다.

## 구조

```
school-meal-bot/
├── bot.py                       # 엔트리포인트 (마이그레이션·알림 잡 등록)
├── app/
│   ├── clients/neis.py          # 나이스 API (학교 검색·급식 조회)
│   ├── services/
│   │   ├── meals.py             # 요리·알레르기 파싱, 메시지 포맷 (순수 함수)
│   │   └── repository.py        # SQLite CRUD (학교·알림 설정)
│   ├── handlers/schoolmeal.py   # 명령어 + 인라인 버튼 + 아침 알림 잡
│   └── utils/                   # 메시지 분할 등 공통
└── tests/                       # 74개 (파싱·API 모킹·CRUD·잡 통합)
```

## 테스트

```bash
pip install -r requirements-dev.txt
ruff check . && pytest -q
```

## 라이선스

[MIT](LICENSE) — 자유롭게 복사·수정·배포하세요.

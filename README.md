# FinBrief

FinBrief는 Team8이 7일 안에 구현하는 개인 맞춤 AI 금융 브리핑 에이전트입니다. 매일 아침 주요 거시 금융 지표와 경제 뉴스를 수집하고, 전체 시장 리포트와 사용자 관심 토픽별 카드뉴스를 생성한 뒤 Discord 또는 Slack으로 전달하는 것을 MVP 목표로 합니다.

현재 저장소에는 FastAPI 기본 실행 환경, 설정 로더, health endpoint, 스키마 계약, 기본 토픽 fixture, in-memory repository, Supabase schema/RPC 초안, 외부 데이터 수집/RAG 기반 도구, 구독 API, repository 기반 LangGraph mock 리포트/카드 생성 파이프라인이 준비되어 있습니다.

## 현재 구현 상태

| 구분 | 상태 |
| --- | --- |
| FastAPI 앱 부팅 | 완료 |
| 환경변수 기반 설정 로더 | 완료 |
| `GET /api/v1/health` | 완료 |
| Pydantic 스키마 계약 | 완료 |
| Supabase SQL 스키마 | 완료 |
| 기본 토픽 fixture | 완료 |
| in-memory repository | 완료 |
| Supabase `match_news` RPC 스키마 | 완료 |
| FRED/yfinance/ECOS mapper | 완료 |
| RSS 뉴스 정규화/필터링/태깅 | 완료 |
| Upstage embedding 입력/검증 도구 | 완료 |
| Supabase ingestion payload adapter | 완료 |
| 기본 테스트 | 완료 |
| 구독 API | 완료 |
| LangGraph 리포트/카드 생성 파이프라인 | 완료(mock) |
| topic+date 카드 캐시 | 완료(mock) |
| report/card 조회 API | 완료(mock) |
| LiteLLM/Langfuse 실제 연동 | 예정 |
| Discord/Slack 실제 발송 | 예정 |

## MVP 범위

포함 기능:

- 사용자 관심 토픽 구독 관리
- free tier 토픽 5개 제한
- 거시 지표와 경제 뉴스 수집
- 뉴스 임베딩과 Supabase pgvector 기반 RAG 검색
- 전체 지표 리포트 생성
- 토픽별 카드뉴스 생성과 topic+date 캐시
- Discord/Slack webhook 발송
- LiteLLM retry/fallback
- Langfuse trace와 자동 평가 결과 기록
- 투자 조언 금지 및 disclaimer 검증

제외 기능:

- 카카오 알림톡 실제 발송
- 실제 결제 처리
- 급변동 심층분석 루프
- 매수/매도 추천, 자동 주문, 투자 판단 대행
- 대규모 다중 사용자 운영

## 기술 스택

| 영역 | 도구 |
| --- | --- |
| Backend | Python 3.11+, FastAPI |
| Workflow | LangGraph |
| Database/RAG | Supabase PostgreSQL + pgvector |
| LLM Gateway | LiteLLM |
| Observability | Langfuse |
| UI | Streamlit 예정 |
| Data | FRED, yfinance, ECOS, 경제 뉴스 RSS, fixture JSON |
| Delivery | Discord/Slack webhook |
| Infra | Docker, GitHub Actions, GCP Compute Engine 예정 |

## 디렉터리 구조

```text
app/
  api/            FastAPI route 모듈
  agents/         LangGraph workflow
  core/           공통 설정, 스키마, 안전 규칙, LLM gateway
  repositories/   Supabase persistence adapter
  tools/          데이터, 뉴스, 이미지, 발송 도구
  ui/             Streamlit demo UI
data/             seed 데이터와 로컬 fixture
evals/            자동 평가 스키마와 평가 데이터셋
reports/          로컬 생성 리포트 산출물
schemas/          DB와 workflow 스키마 계약
tests/            테스트 코드
project_docs/     기획서, 로드맵, 구현 기획, 운영 검증, 하네스 기록 문서
ref/              원본 참고 문서
```

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `app/main.py` | FastAPI 앱 팩토리와 루트 엔드포인트 |
| `app/api/router.py` | API v1 라우터 집계 |
| `app/api/dependencies.py` | FastAPI dependency와 repository bundle provider |
| `app/api/routes_health.py` | health endpoint |
| `app/api/routes_subscriptions.py` | 토픽 catalog·키워드 매칭(`POST /topics/match`)과 구독 추가/조회/삭제 API |
| `app/api/routes_reports.py` | 수동 mock 리포트 실행과 최신 리포트 조회 API |
| `app/api/routes_cards.py` | 사용자별 오늘의 카드 조회 API |
| `app/agents/pipeline.py` | API에서 LangGraph를 실행하는 service wrapper |
| `app/agents/graph.py`, `app/agents/nodes.py` | repository 구독 기반 mock 리포트/카드 생성 graph |
| `app/core/config.py` | `.env` 기반 설정 로더와 secret 마스킹 |
| `app/core/schemas.py` | API, agent, repository가 공유하는 Pydantic 모델 |
| `app/repositories/protocols.py` | API/LangGraph가 의존할 repository 계약 |
| `app/repositories/memory.py` | Supabase 없이 테스트 가능한 in-memory repository |
| `app/repositories/supabase.py` | Supabase table/RPC adapter |
| `app/tools/data_sources/fred.py` | FRED observations 수집/정규화 |
| `app/tools/data_sources/yfinance_source.py` | yfinance 가격 데이터 수집/정규화 |
| `app/tools/data_sources/ecos.py` | 한국은행 ECOS 통계 수집/정규화 |
| `app/tools/news/rss.py` | RSS entry 정규화, 중복 제거, 최신 뉴스 필터링 |
| `app/tools/news/tagging.py` | 토픽 `news_keywords` 기반 뉴스 태깅 |
| `app/tools/embedding/upstage.py` | passage/query embedding 입력 생성과 4096차원 검증 |
| `data/default_topics.json` | 기본 토픽 카탈로그 fixture (지표/자산/섹터/키워드 100+개) |
| `schemas/supabase.sql` | Supabase PostgreSQL + pgvector 테이블 구조 |
| `schemas/seed_topics.sql` | 기본 토픽 카탈로그 seed SQL (`data/default_topics.json`과 동기화) |
| `schemas/finbrief_state.schema.json` | LangGraph morning pipeline state 계약 |
| `evals/finbrief_eval_set.schema.json` | 자동 평가 JSONL 항목 스키마 |
| `.env.example` | 로컬/배포 환경변수 템플릿 |
| `pyproject.toml` | 패키지, 의존성, pytest 설정 |

## 로컬 실행

Windows PowerShell 기준입니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

API 서버를 실행합니다.

```powershell
python -m uvicorn app.main:app --reload
```

브라우저 또는 터미널에서 health endpoint를 확인합니다.

```powershell
curl http://127.0.0.1:8000/api/v1/health
```

기대 응답:

```json
{
  "status": "ok",
  "service": "finbrief",
  "version": "0.1.0",
  "environment": "local",
  "mock_data": true
}
```

API 문서는 서버 실행 후 다음 주소에서 확인할 수 있습니다.

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

구독과 mock 리포트/card 흐름은 다음 순서로 수동 확인할 수 있습니다.

```powershell
curl http://127.0.0.1:8000/api/v1/topics
curl -X POST http://127.0.0.1:8000/api/v1/topics/match `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"AI 반도체\",\"limit\":5}"
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/u_001/topics `
  -H "Content-Type: application/json" `
  -d "{\"topic_id\":\"topic_btc\",\"channel\":\"discord\"}"
curl http://127.0.0.1:8000/api/v1/subscriptions/u_001
curl -X POST http://127.0.0.1:8000/api/v1/reports/run `
  -H "Content-Type: application/json" `
  -d "{\"run_date\":\"2026-07-10\",\"dry_run\":true}"
curl "http://127.0.0.1:8000/api/v1/cards/today?user_id=u_001&run_date=2026-07-10"
```

## 환경변수

기본값은 `.env.example`에 정리되어 있습니다. 실제 secret은 `.env`에만 입력하고 Git에 커밋하지 않습니다.

| 변수 | 용도 |
| --- | --- |
| `APP_NAME`, `APP_VERSION`, `APP_ENV` | 서비스 이름, 버전, 실행 환경 |
| `API_V1_PREFIX` | API prefix. 기본값은 `/api/v1` |
| `ENABLE_MOCK_DATA` | fixture/mock 데이터 사용 여부 |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase 연결 정보 |
| `LITELLM_MODEL`, `LITELLM_FALLBACK_MODEL`, `UPSTAGE_API_KEY` | LLM gateway와 모델 설정 |
| `LANGFUSE_ENABLED`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | LLMOps trace 설정 |
| `FRED_API_KEY`, `ECOS_API_KEY`, `NEWS_RSS_URLS` | 지표와 뉴스 수집 설정 |
| `DISCORD_WEBHOOK_URL`, `SLACK_WEBHOOK_URL`, `DELIVERY_DRY_RUN` | 발송 채널 설정 |

실제 외부 데이터/RAG 적재를 실행하려면 사용자가 `.env`에 다음 값을 준비합니다. 키가 비어 있어도 local/test는 mock 또는 빈 결과로 동작합니다.

| 준비 항목 | 필요 시점 |
| --- | --- |
| `FRED_API_KEY` | FRED 실제 지표 수집 |
| `ECOS_API_KEY` | 한국은행 ECOS 실제 통계 수집 |
| `NEWS_RSS_URLS` | 뉴스 RSS 실제 수집. 콤마 구분 URL 목록 |
| `UPSTAGE_API_KEY` | 뉴스 passage/query embedding 실제 생성 |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase DB 적재 |

## 검증

```powershell
python -m compileall app
python -m pytest -q
```

현재 기준 검증 결과:

- `python -m compileall app`: 통과
- `python -m pytest -q`: 48 passed
- `GET /api/v1/health`: `200`, `status=ok`

## 개발 원칙

- API key, webhook URL, Langfuse secret은 코드에 직접 쓰지 않습니다.
- 생성되는 모든 리포트와 카드에는 "투자 조언이 아닌 참고용" disclaimer를 포함합니다.
- 매수/매도 추천, 수익 보장, 자동 주문 기능은 구현하지 않습니다.
- MVP는 먼저 한 개의 end-to-end 흐름을 완주시키고, 이후 범위를 넓힙니다.
- 구현 결과는 `project_docs/02_기획_로드맵/작업_계획_마일스톤.md`, `project_docs/05_운영_검증/테스트_계획_및_검증_기준.md`, `project_docs/05_운영_검증/현재_세션_상태.md` 등 하네스 문서와 동기화합니다.

## 다음 작업

1. LiteLLM 실제 분석 경로와 fallback metadata 정리
2. Langfuse trace 기록 연결
3. Discord/Slack webhook dry-run adapter와 실제 발송 로그 추가
4. 관리 챗봇 명령 parsing 연결
5. 자동 평가 scaffold와 safety 검증 연결

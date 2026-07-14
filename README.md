# FinBrief

FinBrief는 Team8이 7일 안에 구현하는 개인 맞춤 AI 금융 브리핑 에이전트입니다. 매일 아침 주요 거시 금융 지표와 경제 뉴스를 수집하고, 전체 시장 리포트와 사용자 관심 토픽별 카드뉴스를 생성한 뒤 Discord 또는 Slack으로 전달하는 것을 MVP 목표로 합니다.

현재 저장소에는 FastAPI 기본 실행 환경, 설정 로더, health endpoint, 스키마 계약, 기본 토픽 fixture, in-memory repository, Supabase schema/RPC 초안, 외부 데이터 수집/RAG 기반 도구, 구독 API, Discord 관리 챗봇, repository 기반 LangGraph mock 리포트/카드 생성 파이프라인이 준비되어 있습니다.

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
| Discord 관리 챗봇 persona/대화형 UX | 완료 |
| 선택 토픽 ingestion API | 완료 |
| 주요 지표 전체 리포트 이미지 생성 | 완료(mock) |
| LangGraph 리포트/카드 생성 파이프라인 | 완료(mock) |
| topic+date 카드 캐시 | 완료(mock) |
| report/card 조회 API | 완료(mock) |
| Docker/Compose 실행 단위 | 완료(multi-stage build) |
| GitHub Actions CI/CD workflow | 완료 |
| LiteLLM/Langfuse 관측성 연동 | 부분 완료 |
| Discord/Slack 실제 발송 | 예정 |

## MVP 범위

포함 기능:

- 사용자 관심 토픽 구독 관리
- Discord slash command 기반 자연어 구독 관리
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
| Infra | Docker, GitHub Actions, GCP Compute Engine |

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
.github/          GitHub Actions CI/CD workflow
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
| `app/api/routes_ingestion.py` | 선택 토픽 외부 데이터 수집과 Supabase 적재 API |
| `app/api/routes_reports.py` | 수동 mock 리포트 실행과 최신 리포트 조회 API |
| `app/api/routes_cards.py` | 사용자별 오늘의 카드 조회 API |
| `app/agents/pipeline.py` | API에서 LangGraph를 실행하는 service wrapper |
| `app/agents/graph.py`, `app/agents/nodes.py` | repository 구독 기반 mock 리포트/카드 생성 graph |
| `app/agents/report_catalog.py`, `app/agents/report_render.py` | 21개 주요 지표 전체 리포트 PNG 생성 |
| `app/services/topic_ingestion.py` | 선택 토픽 기준 FRED/yfinance/ECOS/RSS 수집, 뉴스 필터링, embedding 저장 service |
| `app/services/chatbot.py` | Discord 관리 챗봇 intent parsing과 구독 tool 호출 |
| `app/services/chatbot_persona.py`, `app/services/chatbot_responses.py`, `app/services/chatbot_suggestions.py` | 챗봇 persona, 안전 응답, 후보 토픽 제안 |
| `app/services/discord_bot.py` | Discord slash command 엔트리포인트 |
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
| `.github/workflows/ci.yml` | compile, pytest, Docker build 자동 검증 |
| `.github/workflows/cd.yml` | GHCR image build/push, GCE Compose 배포, health check, rollback |
| `Dockerfile` | builder/runtime multi-stage FinBrief FastAPI 컨테이너 이미지 |
| `docker-compose.yml` | 로컬/서버 공통 실행 단위 |
| `.dockerignore` | secret, cache, 문서, 생성 산출물 build context 제외 |
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
curl "http://127.0.0.1:8000/api/v1/reports/today/explanation?run_date=2026-07-10"
curl "http://127.0.0.1:8000/api/v1/cards/today?user_id=u_001&run_date=2026-07-10"
```

## Discord 관리 챗봇

Discord 챗봇은 `/finbrief` slash command로 사용자의 자연어 메시지를 받아 관심 토픽을 관리합니다. 응답 persona는 `브리핑 메이트`이며, 투자 판단이나 매수·매도 지시는 거절하고 구독 가능한 브리핑 토픽으로 안내합니다.

대표 입력:

```text
/finbrief message: 나스닥 구독해줘
/finbrief message: 내 토픽 보여줘
/finbrief message: 비트코인 취소해줘
/finbrief message: 금리 구독
/finbrief message: 처음인데 뭐 받아보면 좋아?
/finbrief message: 오늘 리포트에서 뭐 봐야 해?
```

주요 동작:

- `구독`, `추가`, `등록` 표현은 토픽 추가로 처리합니다.
- `삭제`, `취소`, `해지` 표현은 토픽 삭제로 처리합니다.
- `내 토픽`, `목록`, `조회` 표현은 현재 구독 목록을 보여줍니다.
- `오늘 리포트`, `변동 큰 지표`, `뭐 봐야 해?` 표현은 생성된 당일 지표 리포트에서 큰 변동과 RSS/RAG 근거를 설명합니다.
- `금리`, `환율`처럼 후보가 여러 개인 키워드는 바로 저장하지 않고 후보 토픽을 제시합니다.
- `사야 해?`, `매수`, `매도`, `목표가`처럼 투자 판단을 요구하는 표현은 차단하고 브리핑 구독 예시로 전환합니다.

로컬에서 Discord bot을 직접 실행할 때는 `.env`에 `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`를 설정한 뒤 실행합니다.

```powershell
python -m app.services.discord_bot
```

실제 Supabase/RAG 적재 모드에서는 `.env`에 `ENABLE_MOCK_DATA=false`, Supabase service role key,
`UPSTAGE_API_KEY`, 필요한 외부 데이터 API key/RSS URL을 설정한 뒤 선택 토픽 단위로 적재할 수 있습니다.

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/topics/topic_btc/ingest `
  -H "Content-Type: application/json" `
  -d "{\"run_date\":\"2026-07-10\",\"include_indicators\":true,\"include_news\":true,\"include_embeddings\":true}"

curl -X POST http://127.0.0.1:8000/api/v1/reports/run `
  -H "Content-Type: application/json" `
  -d "{\"run_date\":\"2026-07-10\",\"dry_run\":true,\"refresh_data\":true}"
```

## Docker 실행

Docker Desktop 또는 Docker Engine이 실행 중인 상태에서 다음 명령으로 로컬 컨테이너를 빌드하고 실행합니다.
Dockerfile은 builder stage에서 FinBrief wheel과 의존성 wheel을 생성하고, runtime stage에서 해당 wheelhouse만 설치하는 multi-stage 구조입니다. 기존 Compose 실행 방식과 GCE CD 배포 방식은 그대로 유지됩니다.

```powershell
Copy-Item .env.example .env
docker compose up -d --build
curl http://127.0.0.1:8000/api/v1/health
docker compose ps
```

종료할 때는 다음 명령을 사용합니다.

```powershell
docker compose down
```

기본 Compose 설정은 `ENABLE_MOCK_DATA=true`, `FINBRIEF_LLM_STUB=1`, `FINBRIEF_IMAGE_STUB=1`, `DELIVERY_DRY_RUN=true`를 사용하므로 외부 API key 없이 health와 mock 리포트 경로를 먼저 확인할 수 있습니다. 서비스 포트는 `.env`의 `SERVICE_PORT`로 바꿀 수 있습니다.

## CI/CD

GitHub Actions workflow는 두 단계로 구성되어 있습니다.

| Workflow | Trigger | 역할 |
| --- | --- | --- |
| `FinBrief CI` | `push`, `pull_request`, `workflow_dispatch` | Python 3.11 설치, `compileall`, 전체 pytest, Docker build |
| `FinBrief CD` | `FinBrief CI`의 main 성공 후, 또는 수동 실행 | GHCR image build/push, GCE SSH 배포, `/api/v1/health` 확인, rollback |

CI는 secret 없이 mock/stub mode로 실행됩니다. CD를 사용하려면 GitHub Settings에서 다음 Secrets를 먼저 준비합니다.

| Secret | 용도 |
| --- | --- |
| `GCE_HOST` | GCP Compute Engine 외부 IP 또는 도메인 |
| `GCE_USERNAME` | 배포 서버 Linux 사용자 |
| `GCE_SSH_KEY` | 배포 서버 접속용 private key |
| `SERVICE_PORT` | 배포 포트. 기본값 `8000` |
| `ENABLE_MOCK_DATA` | 첫 배포 권장값 `true` |
| `FINBRIEF_LLM_STUB`, `FINBRIEF_IMAGE_STUB`, `DELIVERY_DRY_RUN` | 첫 배포 권장값 `1`, `1`, `true` |

실데이터 모드로 전환할 때는 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `UPSTAGE_API_KEY`, `GEMINI_API_KEY`, `FRED_API_KEY`, `ECOS_API_KEY`, `NEWS_RSS_URLS`, `DISCORD_WEBHOOK_URL` 등을 추가하고 `ENABLE_MOCK_DATA=false`로 바꿉니다.

## 환경변수

기본값은 `.env.example`에 정리되어 있습니다. 실제 secret은 `.env`에만 입력하고 Git에 커밋하지 않습니다.

| 변수 | 용도 |
| --- | --- |
| `APP_NAME`, `APP_VERSION`, `APP_ENV` | 서비스 이름, 버전, 실행 환경 |
| `API_V1_PREFIX` | API prefix. 기본값은 `/api/v1` |
| `ENABLE_MOCK_DATA` | fixture/mock 데이터 사용 여부 |
| `SERVICE_PORT`, `APP_IMAGE` | Docker Compose 포트와 이미지 지정 |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase 연결 정보 |
| `LITELLM_MODEL`, `LITELLM_FALLBACK_MODEL`, `UPSTAGE_API_KEY`, `FINBRIEF_LLM_STUB` | LLM gateway와 모델 설정 |
| `FINBRIEF_LLM_TIMEOUT_SECONDS`, `FINBRIEF_LLM_NUM_RETRIES` | LiteLLM 호출 timeout/retry 설정 |
| `FINBRIEF_LLM_GUARDRAIL_ENABLED`, `FINBRIEF_LLM_FORBIDDEN_TERMS`, `FINBRIEF_LLM_PII_MASKING` | 앱 내부 금융 안전 guardrail과 PII masking |
| `LITELLM_PROXY_URL`, `LITELLM_MASTER_KEY`, `LITELLM_GUARDRAILS` | 선택적 LiteLLM Proxy 전환 설정 |
| `LANGFUSE_ENABLED`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | LLMOps trace 기본 설정 |
| `LANGFUSE_BASE_URL`, `LANGFUSE_OTEL_HOST`, `LANGFUSE_CAPTURE_IO`, `LANGFUSE_FLUSH_ON_SHUTDOWN` | Langfuse SDK/LiteLLM OTEL 세부 설정 |
| `FRED_API_KEY`, `ECOS_API_KEY`, `NEWS_RSS_URLS` | 지표와 뉴스 수집 설정 |
| `GEMINI_API_KEY`, `FINBRIEF_IMAGE_MODEL`, `FINBRIEF_IMAGE_STUB` | 이미지 생성 설정 |
| `FINBRIEF_FONT`, `FINBRIEF_REPORT_OUT` | 한글 폰트 경로와 전체 리포트 이미지 출력 경로 |
| `DISCORD_WEBHOOK_URL`, `SLACK_WEBHOOK_URL`, `DELIVERY_DRY_RUN` | 발송 채널 설정 |

실제 외부 데이터/RAG 적재를 실행하려면 사용자가 `.env`에 다음 값을 준비합니다. 키가 비어 있어도 local/test는 mock 또는 빈 결과로 동작합니다.

| 준비 항목 | 필요 시점 |
| --- | --- |
| `FRED_API_KEY` | FRED 실제 지표 수집 |
| `ECOS_API_KEY` | 한국은행 ECOS 실제 통계 수집 |
| `NEWS_RSS_URLS` | 뉴스 RSS 실제 수집. 콤마 구분 URL 목록 |
| `UPSTAGE_API_KEY` | 뉴스 passage/query embedding 실제 생성 |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase DB 적재 |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Langfuse 실제 trace 전송 |

`ENABLE_MOCK_DATA=false`로 두면 morning pipeline이 실데이터 모드(`live_data`)로 전환된다.
이 모드에서 `ingest_news`는 RSS→태깅→Supabase 적재를, `collect_indicators`는 토픽
`source_mapping` 기반 지표 수집을, `retrieve_evidence`는 `match_news` RPC(RAG)를 실제로 조회한다.

### LiteLLM Guardrail / Fallback

FinBrief는 MVP 기준으로 LiteLLM Python SDK 직접 호출을 사용합니다. `LITELLM_FALLBACK_MODEL`을 설정하면 `chat_json()` 호출에 LiteLLM fallback 후보가 전달되고, 모델 호출 실패나 guardrail 위반이 발생하면 카드 분석 노드는 deterministic local template로 복구합니다.

기본 guardrail은 앱 내부에서 수행됩니다.

- email/webhook/API key 형태의 민감 문자열을 LLM 입력과 출력 JSON에서 masking
- 카드 분석 결과의 필수 JSON key 확인
- `확정 수익`, `반드시 수익`, `지금 사야`, `원금 보장` 등 보장·명령형 투자 조언 표현 차단
- 차단 시 전체 pipeline 중단 대신 local card fallback 사용

LiteLLM Proxy 기반 guardrail은 선택 사항입니다. 예시 설정은 `config/litellm_config.yaml.example`에 있으며, 별도 Proxy 서비스를 운영할 때만 사용합니다.
`true`(기본값)에서는 fixture로 동작하므로 키 없이 로컬/테스트가 가능하다.

선택 토픽 적재 API는 `ENABLE_MOCK_DATA=false`에서 Supabase에 실제 upsert를 수행한다.
`ENABLE_MOCK_DATA=true`에서는 기본 dependency가 Supabase ingestion repository를 만들지 않으므로,
실제 저장 테스트는 live 설정 또는 테스트용 dependency override로 수행한다.

## 검증

```powershell
python -m compileall app
python -m pytest -p no:cacheprovider --basetemp .pytest_cache\basetemp-ci --disable-warnings
docker compose config
```

현재 기준 검증 결과:

- `python -m compileall app`: 통과
- `python -m pytest -p no:cacheprovider --basetemp .pytest_cache\basetemp-docker-multistage --disable-warnings`: 통과
- `docker compose config`: 통과
- `docker build -t finbrief:multi-stage -f Dockerfile .`: Docker Desktop Linux Engine 미실행으로 이번 작업에서 미검증
- `docker run ... finbrief:multi-stage` health smoke: Docker build 미수행으로 이번 작업에서 미검증
- `GET /api/v1/health`: 로컬 서버 미실행으로 이번 작업에서 재확인하지 않음

## 개발 원칙

- API key, webhook URL, Langfuse secret은 코드에 직접 쓰지 않습니다.
- 생성되는 모든 리포트와 카드에는 "투자 조언이 아닌 참고용" disclaimer를 포함합니다.
- 매수/매도 추천, 수익 보장, 자동 주문 기능은 구현하지 않습니다.
- MVP는 먼저 한 개의 end-to-end 흐름을 완주시키고, 이후 범위를 넓힙니다.
- 구현 결과는 `project_docs/02_기획_로드맵/작업_계획_마일스톤.md`, `project_docs/05_운영_검증/테스트_계획_및_검증_기준.md`, `project_docs/05_운영_검증/현재_세션_상태.md` 등 하네스 문서와 동기화합니다.

## 다음 작업

1. GitHub Secrets와 GCE VM을 준비한 뒤 `FinBrief CD`를 수동 실행
2. 첫 배포는 mock/stub mode로 `/api/v1/health` 확인
3. live secret을 채운 뒤 Supabase/RAG smoke test 수행
4. GCE에서 Langfuse 실제 trace smoke test 수행
5. 자동 평가 scaffold와 Langfuse score 연결

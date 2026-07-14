# FinBrief

FinBrief는 사용자가 관심 있는 금융 토픽을 구독하면, 주요 시장 지표와 경제 뉴스를 모아 아침 브리핑으로 정리해 주는 AI 금융 브리핑 서비스입니다.

Discord 챗봇 또는 API로 토픽을 구독하고, 시스템은 지표 데이터와 뉴스 RSS를 수집해 전체 시장 리포트와 토픽별 카드뉴스를 생성합니다. 결과는 웹 화면, API, Discord 알림으로 확인할 수 있습니다.

> FinBrief는 투자 조언 서비스가 아닙니다. 매수, 매도, 목표가, 수익 보장 같은 투자 판단은 제공하지 않고 참고용 정보만 제공합니다.

## 주요 기능

- 관심 토픽 구독: 비트코인, 나스닥, 환율, 금리, 반도체, AI 등 금융 토픽을 구독합니다.
- 자연어 챗봇: Discord에서 "나스닥 구독", "내 토픽 보여줘", "오늘 리포트 설명해줘"처럼 사용할 수 있습니다.
- 주요 지표 리포트: 주식 지수, 금리, 원자재, 환율 등 핵심 지표를 이미지 리포트로 생성합니다.
- 토픽별 카드뉴스: 구독한 토픽마다 요약, 근거 뉴스, 안전 문구가 포함된 카드뉴스를 만듭니다.
- RAG 기반 설명: RSS 뉴스와 Supabase pgvector 검색을 이용해 관련 근거를 찾아 리포트 설명에 반영합니다.
- 안전 장치: 투자 조언성 표현과 민감정보 노출을 줄이기 위한 guardrail을 적용합니다.
- 운영 지원: Docker, GitHub Actions CI/CD, GCE 배포, Langfuse 관측성 설정을 포함합니다.

## 사용 흐름

1. 사용자가 Discord 또는 API로 관심 토픽을 구독합니다.
2. FinBrief가 외부 데이터와 뉴스를 수집합니다.
3. LangGraph pipeline이 전체 리포트와 토픽별 카드뉴스를 생성합니다.
4. 사용자는 웹 화면, API, Discord에서 결과를 확인합니다.
5. 필요한 경우 "오늘 뭐 봐야 해?"처럼 챗봇에게 리포트 해설을 요청합니다.

## 빠른 시작

기본 실행은 mock/stub 모드입니다. 외부 API key 없이 로컬에서 먼저 앱을 확인할 수 있습니다.

### 1. 설치

Windows PowerShell 기준입니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

### 2. API 서버 실행

```powershell
python -m uvicorn app.main:app --reload
```

확인:

```powershell
curl http://127.0.0.1:8000/api/v1/health
```

브라우저에서 확인할 수 있는 주소:

- 웹 화면: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/v1/health`

## API 사용 예시

토픽 목록 조회:

```powershell
curl http://127.0.0.1:8000/api/v1/topics
```

키워드로 토픽 찾기:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/topics/match `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"비트코인\",\"limit\":5}"
```

토픽 구독:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/demo-user/topics `
  -H "Content-Type: application/json" `
  -d "{\"topic_id\":\"topic_btc\",\"channel\":\"discord\"}"
```

현재 구독 조회:

```powershell
curl http://127.0.0.1:8000/api/v1/subscriptions/demo-user
```

리포트와 카드 생성:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/reports/run `
  -H "Content-Type: application/json" `
  -d "{\"run_date\":\"2026-07-14\",\"dry_run\":true}"
```

오늘 리포트 설명:

```powershell
curl "http://127.0.0.1:8000/api/v1/reports/today/explanation?run_date=2026-07-14"
```

사용자 카드 조회:

```powershell
curl "http://127.0.0.1:8000/api/v1/cards/today?user_id=demo-user&run_date=2026-07-14"
```

## Discord 챗봇 사용

Discord bot을 연결하면 `/finbrief` 명령 또는 봇 멘션/DM으로 토픽을 관리할 수 있습니다.

대표 입력:

```text
/finbrief message: 나스닥 구독해줘
/finbrief message: 내 토픽 보여줘
/finbrief message: 비트코인 취소해줘
/finbrief message: 금리 구독
/finbrief message: 처음인데 뭐 받아보면 좋아?
/finbrief message: 오늘 리포트에서 뭐 봐야 해?
```

실행 전 `.env`에 다음 값을 설정합니다.

```text
DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=
```

로컬 실행:

```powershell
python -m app.services.discord_bot
```

기본 저장소는 memory repository입니다. Supabase 값을 설정하면 구독 정보가 DB에 저장됩니다.

## Docker 실행

Docker Desktop 또는 Docker Engine이 실행 중이어야 합니다.

```powershell
Copy-Item .env.example .env
docker compose up -d --build
curl http://127.0.0.1:8000/api/v1/health
docker compose ps
```

종료:

```powershell
docker compose down
```

Compose에는 세 가지 서비스가 포함됩니다.

| 서비스 | 역할 |
| --- | --- |
| `finbrief-api` | FastAPI API와 웹 화면 제공 |
| `finbrief-bot` | Discord 챗봇 실행 |
| `finbrief-scheduler` | 매일 아침 배치 실행 |

처음 실행할 때는 기본값 그대로 mock/stub 모드를 권장합니다.

```text
ENABLE_MOCK_DATA=true
FINBRIEF_LLM_STUB=1
FINBRIEF_IMAGE_STUB=1
DELIVERY_DRY_RUN=true
```

## 실데이터 모드

외부 데이터 수집, Supabase 저장, RAG 검색, 실제 LLM/이미지 생성을 사용하려면 `.env`에 필요한 값을 채운 뒤 `ENABLE_MOCK_DATA=false`로 바꿉니다.

주요 환경변수:

| 변수 | 용도 |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | 서버 측 DB 적재와 조회 |
| `UPSTAGE_API_KEY` | LLM 호출과 embedding 생성 |
| `GEMINI_API_KEY` | 이미지 생성 |
| `FRED_API_KEY` | FRED 경제 지표 수집 |
| `ECOS_API_KEY` | 한국은행 ECOS 지표 수집 |
| `NEWS_RSS_URLS` | 뉴스 RSS URL 목록 |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Langfuse trace 전송 |

선택 토픽 데이터 적재 예시:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/topics/topic_btc/ingest `
  -H "Content-Type: application/json" `
  -d "{\"run_date\":\"2026-07-14\",\"include_indicators\":true,\"include_news\":true,\"include_embeddings\":true,\"dry_run\":false}"
```

구독 중인 토픽 데이터를 새로 수집한 뒤 리포트를 생성하려면:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/reports/run `
  -H "Content-Type: application/json" `
  -d "{\"run_date\":\"2026-07-14\",\"dry_run\":true,\"refresh_data\":true}"
```

Supabase 테이블과 RPC는 `schemas/supabase.sql`을 Supabase SQL Editor에서 실행해 준비합니다.

## CI/CD

GitHub Actions는 테스트와 배포를 분리합니다.

| Workflow | 실행 시점 | 역할 |
| --- | --- | --- |
| `FinBrief CI` | push, pull request, 수동 실행 | Python compile, pytest, Docker build |
| `FinBrief CD` | main CI 성공 후 또는 수동 실행 | GHCR 이미지 빌드/푸시, GCE 배포, health check, rollback |

GCE 배포를 사용하려면 GitHub repository secrets에 최소한 다음 값을 등록합니다.

| Secret | 설명 |
| --- | --- |
| `GCE_HOST` | GCE VM 외부 IP 또는 도메인 |
| `GCE_USERNAME` | SSH 접속 사용자 |
| `GCE_SSH_KEY` | 배포용 private key |
| `SERVICE_PORT` | 서비스 포트. 기본값 `8000` |
| `ENABLE_MOCK_DATA` | 첫 배포 권장값 `true` |
| `FINBRIEF_LLM_STUB` | 첫 배포 권장값 `1` |
| `FINBRIEF_IMAGE_STUB` | 첫 배포 권장값 `1` |
| `DELIVERY_DRY_RUN` | 첫 배포 권장값 `true` |

실데이터 배포에서는 Supabase, Upstage, Gemini, RSS, Langfuse, Discord 관련 secret을 추가합니다.

## 기술 스택

세부 구현보다 사용 흐름을 우선하지만, 프로젝트는 다음 기술을 사용합니다.

| 영역 | 사용 기술 |
| --- | --- |
| Backend | Python 3.11, FastAPI |
| Agent workflow | LangGraph |
| LLM gateway | LiteLLM |
| Observability | Langfuse |
| Database/RAG | Supabase PostgreSQL, pgvector |
| Data sources | FRED, yfinance, ECOS, RSS |
| Image/report | Pillow, Gemini image model |
| Bot/Delivery | Discord.py |
| Infra | Docker, Docker Compose, GitHub Actions, GCE |

## 프로젝트 구조

```text
app/
  api/             FastAPI route
  agents/          LangGraph 리포트/카드 생성 pipeline
  core/            설정, schema, LLM, guardrail, observability
  repositories/    memory/Supabase 저장소
  services/        챗봇, 배치, 스케줄러, 데이터 적재 서비스
  tools/           외부 데이터, RSS, embedding, 발송 도구
frontend/          배포본에 포함되는 결과 확인 화면
schemas/           Supabase SQL과 agent state schema
tests/             자동 테스트
.github/workflows/ CI/CD workflow
```

## 검증

개발 중 기본 검증:

```powershell
python -m compileall app
python -m pytest -p no:cacheprovider --basetemp .pytest_cache\basetemp-local --disable-warnings
docker compose config
```

CI에서도 같은 방향으로 compile, pytest, Docker build를 확인합니다.

## 운영 원칙

- 실제 secret은 `.env` 또는 GitHub Secrets에만 둡니다.
- `.env`, private key, 생성 산출물은 Git에 커밋하지 않습니다.
- 첫 배포는 mock/stub mode로 health check를 통과시킨 뒤 실데이터 모드로 전환합니다.
- 모든 리포트와 카드에는 투자 조언이 아니라는 disclaimer를 유지합니다.
- 사용자 입력이 모호하면 바로 저장하지 않고 후보 토픽을 안내합니다.

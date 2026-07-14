# FinBrief

FinBrief는 사용자가 관심 있는 금융 토픽을 구독하면, 실제 시장 지표와 경제 뉴스를 수집해 아침 브리핑으로 정리하는 AI 금융 브리핑 서비스입니다.

Discord 챗봇 또는 API로 관심 토픽을 등록하면 FinBrief가 FRED, yfinance, 한국은행 ECOS, 뉴스 RSS를 수집하고, Supabase RAG 검색과 LLM 분석을 거쳐 전체 시장 리포트와 토픽별 카드뉴스를 생성합니다. 결과는 웹 화면, API, Discord 알림으로 확인할 수 있습니다.

> FinBrief는 투자 조언 서비스가 아닙니다. 매수, 매도, 목표가, 수익 보장 같은 투자 판단은 제공하지 않고 참고용 정보만 제공합니다.

## 주요 기능

- 관심 토픽 구독: 비트코인, 나스닥, 환율, 금리, 반도체, AI 등 금융 토픽을 구독합니다.
- 자연어 챗봇: Discord에서 "나스닥 구독", "내 토픽 보여줘", "오늘 리포트 설명해줘"처럼 사용할 수 있습니다.
- 실데이터 수집: FRED, yfinance, ECOS, RSS에서 지표와 뉴스를 가져옵니다.
- RAG 검색: Supabase PostgreSQL + pgvector에 저장된 뉴스 근거를 토픽별로 검색합니다.
- 주요 지표 리포트: 주식 지수, 금리, 원자재, 환율 등 핵심 지표를 이미지 리포트로 생성합니다.
- 토픽별 카드뉴스: 구독한 토픽마다 요약, 근거 뉴스, 안전 문구가 포함된 카드뉴스를 만듭니다.
- 리포트 설명: 당일 리포트에서 변동이 큰 지표와 관련 뉴스 근거를 설명합니다.
- 운영 지원: Docker, GitHub Actions CI/CD, GCE 배포, Langfuse 관측성 설정을 포함합니다.

## 사용 흐름

1. 운영자가 Supabase schema와 외부 API key를 준비합니다.
2. 사용자가 Discord 또는 API로 관심 토픽을 구독합니다.
3. FinBrief가 구독 토픽에 필요한 지표와 뉴스를 수집해 Supabase에 저장합니다.
4. LangGraph pipeline이 RAG 근거를 조회하고 전체 리포트와 카드뉴스를 생성합니다.
5. 사용자는 웹 화면, API, Discord에서 결과를 확인합니다.
6. 필요한 경우 "오늘 뭐 봐야 해?"처럼 챗봇에게 리포트 해설을 요청합니다.

## 사전 준비

실데이터 실행에는 다음 준비가 필요합니다.

| 준비 항목 | 설명 |
| --- | --- |
| Supabase project | `schemas/supabase.sql` 실행, service role key 준비 |
| Upstage API key | LLM 호출과 4096차원 embedding 생성 |
| Gemini API key | 카드/리포트 이미지 생성 |
| FRED API key | 미국 경제 지표 수집 |
| ECOS API key | 한국은행 통계 수집 |
| 뉴스 RSS URL | 경제/시장 뉴스 수집 URL 목록 |
| Discord bot token | `/finbrief` 명령과 채널 발송 |
| Langfuse key | LLM 호출과 report run 관측성 |

Supabase SQL Editor에서 먼저 실행합니다.

```sql
-- schemas/supabase.sql 전체 실행
```

토픽 seed가 필요한 경우 다음 파일도 실행합니다.

```sql
-- schemas/seed_topics.sql 전체 실행
```

## 환경변수

`.env.example`을 복사한 뒤 실데이터 값을 채웁니다. 실제 secret은 Git에 커밋하지 않습니다.

```powershell
Copy-Item .env.example .env
```

필수 운영값:

```text
APP_ENV=local
ENABLE_MOCK_DATA=false
FINBRIEF_LLM_STUB=0
FINBRIEF_IMAGE_STUB=0
DELIVERY_DRY_RUN=false

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
UPSTAGE_API_KEY=
GEMINI_API_KEY=
FRED_API_KEY=
ECOS_API_KEY=
NEWS_RSS_URLS=

DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=

LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
```

선택값:

| 변수 | 용도 |
| --- | --- |
| `SERVICE_PORT` | Docker Compose 노출 포트. 기본값 `8000` |
| `FINBRIEF_REPORT_OUT` | 리포트 이미지 출력 경로 |
| `FINBRIEF_FONT` | 한글 리포트 렌더링용 폰트 경로 |
| `LITELLM_MODEL` | 기본 LLM 모델 |
| `LITELLM_FALLBACK_MODEL` | fallback LLM 모델 |
| `FINBRIEF_BATCH_HOUR`, `FINBRIEF_BATCH_MINUTE` | 스케줄러 실행 시각 |

## 로컬 실행

Windows PowerShell 기준입니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

`.env`에 실데이터 값을 채운 뒤 API 서버를 실행합니다.

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

선택 토픽 데이터 수집과 Supabase 적재:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/topics/topic_btc/ingest `
  -H "Content-Type: application/json" `
  -d "{\"run_date\":\"2026-07-14\",\"include_indicators\":true,\"include_news\":true,\"include_embeddings\":true,\"dry_run\":false}"
```

구독 중인 토픽을 새로 수집한 뒤 리포트 생성:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/reports/run `
  -H "Content-Type: application/json" `
  -d "{\"run_date\":\"2026-07-14\",\"dry_run\":false,\"refresh_data\":true}"
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

로컬 실행:

```powershell
python -m app.services.discord_bot
```

Discord Developer Portal에서 bot token, guild id, message content intent, `applications.commands` scope를 확인합니다. Supabase 연결이 설정되어 있으면 구독 상태는 DB에 저장됩니다.

## 배치 실행

전체시장 리포트와 구독 토픽 카드 생성을 한 번 실행합니다.

```powershell
python -m app.services.batch
```

스케줄러는 매일 지정한 KST 시각에 배치를 실행합니다.

```powershell
python -m app.services.scheduler
```

관련 환경변수:

```text
FINBRIEF_BATCH_HOUR=7
FINBRIEF_BATCH_MINUTE=0
FINBRIEF_RUN_ON_START=1
```

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

컨테이너 실행 전 `.env`에는 실데이터 운영값을 반드시 채워야 합니다.

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
| `ENABLE_MOCK_DATA` | `false` |
| `FINBRIEF_LLM_STUB` | `0` |
| `FINBRIEF_IMAGE_STUB` | `0` |
| `DELIVERY_DRY_RUN` | `false` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase 연결 |
| `UPSTAGE_API_KEY`, `GEMINI_API_KEY` | LLM, embedding, 이미지 생성 |
| `FRED_API_KEY`, `ECOS_API_KEY`, `NEWS_RSS_URLS` | 외부 데이터 수집 |
| `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID` | Discord bot 실행 |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | Langfuse 관측성 |

수동 배포는 GitHub `Actions` → `FinBrief CD` → `Run workflow`에서 실행합니다.

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
  repositories/    Supabase 저장소와 개발용 memory 저장소
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

배포 후 확인:

```powershell
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/topics
```

## 운영 원칙

- 실제 secret은 `.env` 또는 GitHub Secrets에만 둡니다.
- `.env`, private key, 생성 산출물은 Git에 커밋하지 않습니다.
- Supabase schema와 외부 API key를 준비한 뒤 실행합니다.
- 모든 리포트와 카드에는 투자 조언이 아니라는 disclaimer를 유지합니다.
- 사용자 입력이 모호하면 바로 저장하지 않고 후보 토픽을 안내합니다.

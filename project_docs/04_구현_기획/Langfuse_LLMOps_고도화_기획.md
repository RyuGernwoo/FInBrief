# Langfuse LLMOps 고도화 기획

> 작성일: 2026-07-14
> 대상 세션: `S-20260714-001`
> Gate: E - P0 구현 완료 기록
> 선행 문서: `project_docs/04_구현_기획/Langfuse_LLMOps_관측성_연동_기획.md`
> 결론: 현재 FinBrief는 LiteLLM generation metadata와 report run trace id를 Langfuse에 연결하는 P0 기반을 갖췄다. 이번 고도화는 발표 전 실서버 smoke 증거를 만들고, RAG/ingestion/delivery/eval 흐름을 추적 가능한 LLMOps 단위로 확장하는 것을 목표로 한다.

## 1. 기획 배경

FinBrief는 다음 기능을 이미 갖추고 있다.

| 영역 | 현재 구현 |
| --- | --- |
| LiteLLM | `app/core/llm.py`에서 `litellm.completion()` 호출, timeout/retry/fallback, guardrail 검증 |
| Langfuse P0 | `app/core/observability.py`에서 no-op fallback, 환경변수 alias, trace id, metadata sanitize, LiteLLM `langfuse_otel` callback 설정 |
| LangGraph | `run_morning_pipeline()`이 report run 단위 `trace_id`를 state/API 응답에 연결 |
| RAG | Supabase `match_news` RPC, Upstage query embedding, `retrieve_evidence` fan-out 전 실행 |
| 리포트 설명 | 당일 지표 변동을 RSS/RAG 근거와 함께 설명 |
| Guardrail | PII/secret masking, 카드 JSON schema, 금융 조언 금칙어, local fallback |
| 저장소 | Supabase `eval_runs` 테이블 존재, 하지만 자동 저장/trace 연결은 아직 없음 |

현재 한계는 다음과 같다.

| 한계 | 영향 |
| --- | --- |
| 실제 Langfuse UI smoke 증거 부족 | 발표에서 "연동됨"을 시각적으로 입증하기 어렵다. |
| LangGraph 노드 span 세분화 부족 | RAG, ingestion, delivery 중 어디서 시간이 걸리고 실패했는지 UI에서 추적하기 어렵다. |
| eval 결과가 Langfuse score와 연결되지 않음 | guardrail/fallback이 품질 개선으로 이어졌다는 증거가 약하다. |
| prompt/output 저장 정책이 설정값 수준 | 데모에서는 편하지만 운영 전 마스킹/비저장 정책을 설명하기 어렵다. |
| Dataset/Experiment 자동화 부재 | 모델/프롬프트 변경 전후 비교를 정량적으로 보여주기 어렵다. |

## 2. 공식 문서 반영 사항

| 출처 | 반영 내용 |
| --- | --- |
| Langfuse Overview: https://langfuse.com/docs | Langfuse는 trace, prompt management, evaluation을 묶어 LLM 앱을 디버깅·분석·개선하는 AI engineering platform이다. Observability는 LLM 호출뿐 아니라 retrieval, embedding, API call, agent graph까지 trace할 수 있다. |
| LiteLLM Proxy Integration: https://langfuse.com/integrations/gateways/litellm | LiteLLM은 Proxy 또는 SDK 경로로 Langfuse에 LLM call을 기록할 수 있으며, callback으로 token/cost/latency를 수집할 수 있다. 현재 FinBrief는 SDK 직접 호출이므로 Proxy 전환은 P2로 둔다. |
| Evaluation Overview: https://langfuse.com/docs/evaluation/overview | 평가는 live trace, dataset, experiment, score와 연결되며 production trace와 offline test 모두에 사용할 수 있다. |
| Datasets: https://langfuse.com/docs/evaluation/experiments/datasets | Dataset은 input/expected output의 묶음으로, production trace에서 test case를 만들고 SDK/UI experiment에 사용할 수 있다. |
| Prompt Management: https://langfuse.com/docs/prompt-management/overview | Prompt를 코드에서 분리해 Langfuse에서 버전·label로 관리할 수 있고, trace와 prompt version을 연결할 수 있다. |

## 3. 목표와 범위

### 3.1 목표

이번 작업의 목표는 "FinBrief의 한 번의 실데이터 브리핑 실행을 Langfuse UI에서 원인, 근거, 품질, 비용 관점으로 추적할 수 있게 만드는 것"이다.

```text
Discord/REST trigger
  -> topic matching
  -> selected topic ingestion
  -> Supabase RAG retrieval
  -> report/card LLM generation
  -> guardrail/fallback/eval
  -> image/report generation
  -> Discord delivery
  -> Langfuse trace + score + smoke evidence
```

### 3.2 포함 범위

| 우선순위 | 포함 범위 | 설명 |
| --- | --- | --- |
| P0 | 실서버 Langfuse smoke 경로 | GCE 배포본에서 trace가 실제 생성되는지 확인 가능한 endpoint/명령/문서 |
| P0 | trace metadata 표준화 | `run_id`, `run_date`, `topic_id`, `node`, `channel`, `mock/live`, `app_env` 키 통일 |
| P0 | RAG/ingestion/delivery span | LLM이 아닌 핵심 노드도 span 또는 observation metadata로 기록 |
| P0 | deterministic eval score | guardrail, disclaimer, evidence coverage, numeric consistency 결과를 Langfuse score와 Supabase `eval_runs`에 저장 |
| P1 | prompt/output capture policy | `LANGFUSE_CAPTURE_IO`에 따라 input/output 저장 범위 제어 |
| P1 | dataset seed/export | `evals/finbrief_eval_set.jsonl`을 Langfuse dataset으로 업로드하는 스크립트 |
| P1 | experiment runner | 동일 dataset으로 prompt/model 변경 전후를 비교하는 수동 실행 스크립트 |
| P2 | prompt management | 카드 분석/리포트 설명 prompt를 Langfuse prompt로 이전하고 label 기반 배포 |
| P2 | LiteLLM Proxy | SDK 직접 호출에서 proxy 운영으로 확장할지 검토 |

### 3.3 제외 범위

| 제외 항목 | 이유 |
| --- | --- |
| Langfuse self-hosting | GCE 한 대 운영 범위를 넘고, 발표 목적에는 Cloud/managed project가 충분하다. |
| 전체 사용자 행동 분석 | MVP 핵심은 report/card 생성 품질 추적이다. 클릭/체류/전환 분석은 제외한다. |
| 모든 prompt를 즉시 Langfuse 관리로 이전 | 현재 prompt는 코드와 테스트가 강하게 결합되어 있어, 발표 전에는 분석/설명 prompt 1~2개만 후보로 둔다. |
| LLM-as-a-Judge 필수화 | deterministic 평가를 우선하고, judge 평가는 네트워크/비용/변동성 때문에 선택 기능으로 둔다. |
| CI에서 실제 Langfuse 호출 | CI는 외부 서비스 없이 통과해야 하므로 fake/no-op contract test만 둔다. |

## 4. 현재 코드 기준 설계

### 4.1 관측성 레이어

현재 `app/core/observability.py`는 다음 역할을 한다.

- `langfuse_ready(settings)`: Langfuse 활성 여부와 key 존재 확인
- `configure_langfuse_environment(settings)`: `LANGFUSE_HOST`를 `LANGFUSE_BASE_URL`, `LANGFUSE_OTEL_HOST`로 매핑
- `configure_litellm_callbacks(litellm_module)`: `langfuse_otel` callback 활성화
- `trace_id_for_run(run_id)`: run id 기반 trace id 생성, 실패 시 local trace 반환
- `build_llm_metadata(...)`: LiteLLM metadata 생성
- `span(...)`, `report_trace(...)`: Langfuse observation 또는 no-op context manager
- `sanitize_metadata(...)`: key 이름 기반 secret redaction

고도화는 이 파일을 중심으로 하되, 기능이 커지면 아래처럼 분리한다.

| 파일 | 역할 |
| --- | --- |
| `app/core/observability.py` | 기존 no-op, env mapping, span/report trace, metadata sanitize 유지 |
| `app/core/evaluations.py` | deterministic eval 계산: safety, evidence, disclaimer, numeric consistency |
| `app/core/langfuse_scores.py` | Langfuse score 전송 wrapper. disabled/no-key면 no-op |
| `app/services/langfuse_smoke.py` | 실서버 smoke payload 생성과 결과 확인용 helper |
| `scripts/langfuse_dataset_sync.py` | `evals/finbrief_eval_set.jsonl` -> Langfuse dataset 업로드 |
| `scripts/langfuse_experiment_run.py` | dataset 기반 prompt/model 비교 실험 실행 |

### 4.2 Trace 계층 구조

권장 trace 구조는 다음과 같다.

```text
trace: finbrief.report.run
  span: subscriptions.collect
  span: ingestion.selected_topics
    span: ingestion.indicators
    span: ingestion.news
    span: ingestion.embeddings
  span: indicators.collect
  span: rag.retrieve_evidence
  span: report.render_image
  span: card.build
    generation: card.analyze
    generation: card.image_prompt
  span: report.explain
    generation: report.explanation
  span: delivery.discord
  score: safety.disclaimer
  score: safety.forbidden_terms
  score: rag.evidence_coverage
  score: data.numeric_consistency
```

### 4.3 표준 metadata 키

| 키 | 예시 | 용도 |
| --- | --- | --- |
| `run_id` | `batch_20260714` | 실행 단위 검색 |
| `run_date` | `2026-07-14` | 날짜별 비교 |
| `trace_id` | Langfuse trace id | API 응답과 UI 연결 |
| `topic_id` | `topic_btc` | 카드/토픽 필터 |
| `topic_name` | `비트코인` | UI 검색 가독성 |
| `node` | `retrieve_evidence` | 병목/오류 위치 |
| `app_env` | `prod` | 환경 분리 |
| `data_mode` | `live` 또는 `mock` | 실데이터/테스트 구분 |
| `llm_stub` | `false` | 실제 LLM 여부 |
| `source_counts` | `{fred:1, rss:8}` | 수집 결과 |
| `evidence_count` | `3` | RAG 근거 수 |
| `delivery_status_counts` | `{sent:2, skipped:0}` | 발송 결과 |
| `guardrail_profile` | `card` | 안전성 정책 |
| `fallback_used` | `true/false` | fallback 사용 여부 |

민감정보 키는 `api_key`, `secret`, `token`, `webhook`, `password`, `credential`, `service_role` 패턴으로 계속 redaction한다.

## 5. 구현 단계

### 5.1 Phase 1 - 실서버 smoke 우선 고정

목표: "Langfuse가 실제로 찍힌다"를 가장 먼저 증명한다.

변경 대상:

- `project_docs/05_운영_검증/테스트_계획_및_검증_기준.md`
- `project_docs/05_운영_검증/GitHub_설정.md`
- `README.md`
- 필요 시 `app/api/routes_health.py`

작업:

1. health 응답 또는 별도 debug endpoint에 secret 없이 `langfuse_enabled`, `langfuse_ready`, `langfuse_host_region` 표시 여부를 결정한다.
2. GCE에서 실행할 smoke 명령을 문서화한다.
3. `/api/v1/reports/run` 실행 후 Langfuse UI에서 `run_id`로 검색하는 절차를 고정한다.
4. 실패 시 확인 순서를 정한다.
   - `LANGFUSE_ENABLED=true`
   - `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
   - `LANGFUSE_HOST`, `LANGFUSE_BASE_URL`, `LANGFUSE_OTEL_HOST`
   - `FINBRIEF_LLM_STUB=0`
   - GCE outbound HTTPS

수용 기준:

- GCE에서 report run 실행 후 Langfuse Trace Table에서 `run_id` 검색이 가능하다.
- trace가 없어도 API 자체는 실패하지 않는다.

### 5.2 Phase 2 - RAG/ingestion/delivery span 세분화

목표: LLM 호출 외의 핵심 workflow를 Langfuse에서 추적한다.

변경 대상:

- `app/services/topic_ingestion.py`
- `app/agents/nodes.py`
- `app/services/report_explainer.py`
- `app/services/notifier.py`
- `tests/test_observability.py`
- `tests/test_topic_ingestion.py`
- `tests/test_report_explainer.py`

작업:

1. `observability.span()`을 `ingest_topics()`의 indicator/news/embedding 단계에 적용한다.
2. `retrieve_evidence`에서 topic별 evidence count, top similarity, source diversity count를 metadata로 기록한다.
3. `report_explainer._llm_summary()`는 이미 metadata를 만들고 있으므로, fallback 발생 여부와 evidence count를 추가한다.
4. `notifier` 또는 `nodes.deliver`에서 channel별 sent/skipped/failed count를 root trace output에 반영한다.
5. no-op 상태에서는 기존 테스트가 동일하게 통과해야 한다.

수용 기준:

- Langfuse trace timeline에서 ingestion, RAG, delivery 단계가 LLM generation과 구분되어 보인다.
- metadata에 `evidence_count`, `source_counts`, `delivery_status_counts`가 남는다.

### 5.3 Phase 3 - deterministic eval score 연결

목표: FinBrief가 안전하고 근거 기반이라는 증거를 trace와 DB에 남긴다.

변경 대상:

- 신규 `app/core/evaluations.py`
- 신규 `app/core/langfuse_scores.py`
- `app/agents/pipeline.py`
- `app/repositories/protocols.py`
- `app/repositories/memory.py`
- `app/repositories/supabase.py`
- `schemas/supabase.sql`
- `tests/test_llm_guardrails.py`
- 신규 `tests/test_evaluations.py`

평가 항목:

| 평가명 | 방식 | 통과 기준 |
| --- | --- | --- |
| `safety.disclaimer` | report/card disclaimer 포함 여부 | 모든 산출물 포함 |
| `safety.forbidden_terms` | 금칙어 phrase 검사 | 위반 0건 |
| `rag.evidence_coverage` | 카드별 evidence 수 | topic card당 1개 이상 권장, 없으면 warning |
| `data.numeric_consistency` | indicator value/change가 finite인지 검사 | NaN/inf 없음 |
| `format.card_schema` | headline/lead/body/source 존재 | 필수 key 충족 |

Supabase `eval_runs` 보강 제안:

```sql
alter table eval_runs add column if not exists trace_id text;
alter table eval_runs add column if not exists run_date date;
alter table eval_runs add column if not exists topic_id text;
create index if not exists idx_eval_runs_trace_id on eval_runs(trace_id);
```

Langfuse score 전송 정책:

- `LANGFUSE_ENABLED=false`: score 전송 no-op, DB/memory eval만 기록
- `LANGFUSE_ENABLED=true`: `trace_id`, `name`, `value`, `comment`, `metadata`를 score로 전송
- 전송 실패: warning만 기록하고 pipeline 성공/실패 판정에는 영향 없음

수용 기준:

- `/reports/run` 결과가 eval summary를 포함하거나, 별도 eval 저장 결과가 조회 가능하다.
- Langfuse UI에서 trace에 score가 연결된다.
- Supabase `eval_runs`에서 `run_id`, `trace_id`, `eval_name`, `score`, `passed`를 확인할 수 있다.

### 5.4 Phase 4 - prompt/output capture policy

목표: 데모와 운영 전환 사이에서 prompt/output 저장 범위를 명확히 제어한다.

변경 대상:

- `app/core/observability.py`
- `app/core/llm.py`
- `app/core/llm_guardrails.py`
- `.env.example`
- `README.md`

정책:

| 변수 | 값 | 동작 |
| --- | --- | --- |
| `LANGFUSE_CAPTURE_IO=true` | 데모 권장 | sanitized prompt/output을 Langfuse에 저장 |
| `LANGFUSE_CAPTURE_IO=false` | 운영 보수 모드 | trace metadata만 저장, prompt/output은 저장하지 않음 |

세부 규칙:

- prompt/output 저장 전 `mask_sensitive_text()`와 `sanitize_metadata()`를 통과시킨다.
- 뉴스 기사 원문 전체가 아니라 title/summary/snippet 중심으로 저장한다.
- Discord channel id, webhook URL, bot token, Supabase key는 절대 저장하지 않는다.

수용 기준:

- `LANGFUSE_CAPTURE_IO=false` 테스트에서 LiteLLM metadata는 남지만 prompt/output 원문은 전달하지 않는다.
- `true`에서도 email/webhook/API key 패턴이 masking된다.

### 5.5 Phase 5 - dataset/experiment 최소 자동화

목표: 발표 이후 확장 가능성을 보여주되, MVP 데모를 흔들지 않는 수준으로만 구현한다.

변경 대상:

- `evals/finbrief_eval_set.jsonl`
- 신규 `scripts/langfuse_dataset_sync.py`
- 신규 `scripts/langfuse_experiment_run.py`
- 신규 `tests/test_langfuse_dataset_scripts.py`

Dataset item 구조:

```json
{
  "input": {
    "topic_id": "topic_btc",
    "indicator": {"value": 65000, "unit": "달러"},
    "evidence": [{"title": "비트코인 ETF 자금 유입", "source": "예시뉴스"}]
  },
  "expected_output": {
    "must_include_disclaimer": true,
    "forbidden_terms": ["매수 추천", "수익 보장"],
    "min_evidence_count": 1
  },
  "metadata": {
    "category": "asset",
    "case_type": "safety_rag"
  }
}
```

수용 기준:

- dry-run에서 dataset payload 개수와 필수 key를 검증한다.
- 실제 Langfuse 업로드는 수동 명령으로만 수행한다.

### 5.6 Phase 6 - prompt management 검토

목표: 코드 배포 없이 prompt를 조정할 수 있는 구조를 후속으로 열어둔다.

우선 후보 prompt:

- `llm.SYSTEM_ANALYZE`: 카드뉴스 분석 prompt
- `REPORT_EXPLAIN_SYSTEM`: 당일 리포트 설명 prompt

도입 방식:

1. 기본값은 코드 내 prompt를 사용한다.
2. `LANGFUSE_PROMPT_ENABLED=true`일 때만 Langfuse prompt를 조회한다.
3. Langfuse prompt 조회 실패 시 코드 내 prompt로 fallback한다.
4. prompt version/label은 LLM metadata에 기록한다.

수용 기준:

- prompt 관리가 실패해도 report/card 생성은 실패하지 않는다.
- trace에서 prompt version 또는 label을 확인할 수 있다.

## 6. 사용자 결정 및 준비 사항

| 항목 | 결정/준비 | 권장 |
| --- | --- | --- |
| Langfuse region | 현재 `.env` 기준 Japan host 사용 여부 확정 | 기존 `https://jp.cloud.langfuse.com` 유지 |
| Prompt/output 저장 | 데모에서 prompt/output 원문 저장 허용 여부 | 데모는 `true`, 제출 전 `false` 검토 |
| Score 전송 | deterministic eval을 Langfuse score로 보낼지 | P0 고도화에 포함 |
| Supabase schema 변경 | `eval_runs.trace_id`, `run_date`, `topic_id` 추가 여부 | 포함 권장 |
| Dataset 자동 업로드 | 발표 전 실제 업로드까지 할지 | 스크립트 dry-run 우선, 업로드는 선택 |
| Prompt management | 발표 전 적용할지 | P2, 시간 남을 때만 |

## 7. 구현 순서 제안

| 순서 | 작업 | 예상 산출물 | 검증 |
| --- | --- | --- | --- |
| 1 | 실서버 smoke 절차 문서화 및 health/debug 상태 확인 | 운영 문서, README 보강 | GCE curl + Langfuse UI 검색 |
| 2 | span metadata 표준화 | `observability` helper 확장 | `tests/test_observability.py` |
| 3 | ingestion/RAG/delivery span 추가 | 노드별 metadata | 관련 단위 테스트 |
| 4 | deterministic eval 모듈 작성 | `app/core/evaluations.py` | `tests/test_evaluations.py` |
| 5 | Supabase eval_runs trace 연결 | SQL, repository | repository tests |
| 6 | Langfuse score 전송 wrapper | `app/core/langfuse_scores.py` | no-op/fake client test |
| 7 | prompt/output capture policy 적용 | 설정, LLM wrapper | guardrail/observability tests |
| 8 | dataset dry-run 스크립트 | scripts + tests | script dry-run |
| 9 | GCE 실서버 E2E smoke | 운영 검증 기록 | Langfuse screenshot/trace id |

## 8. 수용 기준

- [ ] GCE 배포 환경에서 `/api/v1/reports/run` 실행 후 Langfuse UI에서 `run_id`로 trace를 찾을 수 있다.
- [x] trace timeline에서 LLM generation 외에 RAG retrieval, delivery 단계가 구분된다.
- [x] trace metadata에 `run_id`, `run_date`, `topic_id`, `node`, `evidence_count`, `delivery_status_counts` 계열 정보가 남는다.
- [x] guardrail/evidence/disclaimer/numeric consistency 평가가 repository 경유로 Supabase `eval_runs`에 저장 가능하다.
- [x] Langfuse score 전송이 enabled 환경에서 동작하고, disabled/no-key 환경에서는 no-op으로 통과한다.
- [ ] `LANGFUSE_CAPTURE_IO=false`에서 prompt/output 원문이 Langfuse 전송 payload에 포함되지 않는다.
- [x] API key, Discord token, webhook URL, Supabase service role key가 trace/score metadata에 노출되지 않도록 redaction한다.
- [x] 전체 테스트가 mock/test 환경에서 통과한다.

## 9. 검증 계획

### 9.1 로컬 자동 검증

```powershell
python -m compileall app
$env:APP_ENV='local'
$env:ENABLE_MOCK_DATA='true'
$env:FINBRIEF_LLM_STUB='1'
$env:FINBRIEF_IMAGE_STUB='1'
$env:DELIVERY_DRY_RUN='true'
$env:LANGFUSE_ENABLED='false'
python -m pytest -p no:cacheprovider --basetemp .pytest_cache\basetemp-langfuse-advanced --disable-warnings
```

### 9.2 Langfuse enabled contract test

실제 네트워크 호출 없이 fake/no-op client로 검증한다.

```powershell
python -m pytest tests\test_observability.py tests\test_llm_guardrails.py tests\test_reports_cards_api.py -q
```

### 9.3 GCE 수동 smoke

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health

curl -X POST http://127.0.0.1:8000/api/v1/reports/run \
  -H "Content-Type: application/json" \
  -d '{"run_date":"2026-07-14","dry_run":true,"refresh_data":true}'
```

확인:

1. 응답의 `trace_id`, `run_id`, `report_url` 기록
2. Langfuse UI Trace Table에서 `run_id` 검색
3. generation model/latency/token 사용량 확인
4. RAG evidence count와 delivery count 확인
5. score 탭 또는 metadata에서 safety/evidence 평가 확인

## 10. 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| Langfuse 네트워크/인증 실패 | trace 미생성 | report/card 생성은 계속 성공, smoke 문서에 key/host 점검 순서 명시 |
| prompt/output 민감정보 노출 | 보안 리스크 | capture policy, PII/secret masking, metadata redaction test 추가 |
| span 과다 추가 | 구현 복잡도 증가 | P0는 ingestion/RAG/delivery count 중심, 세부 payload는 P1로 제한 |
| score API 버전 차이 | 전송 실패 | wrapper를 no-op/fail-open으로 구현하고 DB eval 저장을 1차 증거로 유지 |
| eval 기준 과도 엄격 | 카드뉴스 생성 실패 증가 | eval은 관측/점수화로 시작하고 blocking gate는 금칙어/PII만 유지 |
| CI 외부 의존 | CI 불안정 | CI에서는 Langfuse 전송 금지, fake client 테스트만 수행 |

## 11. 발표 시연 포인트

1. Discord에서 관심 토픽을 구독한다.
2. `/reports/run refresh_data=true`로 실데이터 수집과 report/card 생성을 실행한다.
3. API 응답의 `trace_id`를 보여준다.
4. Langfuse UI에서 `run_id`로 trace를 검색한다.
5. trace timeline에서 RAG, LLM generation, delivery 흐름을 설명한다.
6. score/eval 결과로 "투자 조언 금지, disclaimer 포함, 근거 포함"을 보여준다.
7. prompt/output capture policy와 secret redaction을 설명한다.

## 12. 다음 구현 단위

이번 세션에서 완료한 P0 구현 단위는 다음이다.

1. `app/core/evaluations.py`에 deterministic 평가 함수 추가
2. `app/core/langfuse_scores.py`에 fail-open score 전송 wrapper 추가
3. `run_morning_pipeline()` 종료 시 eval summary 생성, `eval_runs` 저장, Langfuse score 전송 연결
4. `tests/test_evaluations.py`, `tests/test_langfuse_scores.py`로 no-op/metadata 계약 검증
5. RAG retrieval, delivery span metadata 보강

남은 후속 구현 단위는 다음이다.

1. GCE에서 Langfuse UI smoke 수행 후 `project_docs/05_운영_검증/테스트_계획_및_검증_기준.md`에 trace/score 증거 기록
2. `LANGFUSE_CAPTURE_IO=false`일 때 prompt/output 원문 미전송 정책을 `chat_json()` 경로에 명시적으로 반영
3. `evals/finbrief_eval_set.jsonl` 기반 dataset dry-run 스크립트 작성
4. Langfuse prompt management는 발표 이후 P2로 검토

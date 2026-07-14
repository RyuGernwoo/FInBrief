# Discord 챗봇 Langfuse 대화 추적 기획

> 작성일: 2026-07-14
> 대상 범위: Discord 챗봇 입력, intent 분류, 토픽 매칭, 구독 tool action, 리포트 설명 요청을 Langfuse trace/span으로 추적
> 선행 문서: `project_docs/04_구현_기획/Langfuse_LLMOps_고도화_기획.md`, `project_docs/04_구현_기획/Discord_챗봇_페르소나_대화형_UX_강화_기획.md`
> 결론: 현재 Langfuse는 report run 중심으로 연결되어 있고, Discord 챗봇 대화 turn은 명시적으로 추적하지 않는다. 이번 기획은 챗봇 turn 단위 trace를 추가해 "사용자 발화 -> intent -> tool action -> reply -> 후속 report trace"를 관측 가능하게 만드는 것을 목표로 한다.

## 1. 현재 상태 요약

현재 챗봇 흐름은 다음과 같다.

```text
Discord slash command / mention / DM
  -> app.services.discord_bot.finbrief() 또는 on_message()
  -> app.services.chatbot.handle()
  -> parse_intent()
  -> SubscriptionService
  -> chatbot_responses formatter
  -> Discord reply
```

현재 Langfuse로 추적되는 범위:

| 영역 | 현재 상태 |
| --- | --- |
| Report run | `run_morning_pipeline()`의 `finbrief.report.run` trace |
| 카드 분석 LLM | LiteLLM metadata 기반 generation |
| 이미지 프롬프트 LLM | LiteLLM metadata 기반 generation |
| RAG retrieval | `finbrief.rag.retrieve_evidence` span |
| Delivery | `finbrief.delivery.dispatch` span |
| 자동 평가 | Langfuse score 및 Supabase `eval_runs` 저장 |

현재 챗봇에서 Langfuse 추적이 부족한 부분:

| 항목 | 현재 상태 | 문제 |
| --- | --- | --- |
| Discord 사용자 입력 | 미추적 | 어떤 요청이 실패/성공했는지 UI에서 확인하기 어렵다. |
| intent 분류 | LLM 호출은 조건부 발생하지만 trace/session metadata 없음 | 챗봇 LLM generation이 report trace와 분리되어 의미를 파악하기 어렵다. |
| 토픽 매칭 | rule/helper 내부에서만 처리 | 모호한 키워드, 후보 제시 이유를 추적하기 어렵다. |
| 구독 tool action | `SubscriptionService` 호출 결과만 reply에 반영 | add/delete/list/tier 성공률과 오류를 관측하기 어렵다. |
| 투자 판단 차단 | 응답은 차단하지만 score/metadata 없음 | guardrail이 실제 동작했다는 증거가 약하다. |
| 리포트 설명 intent | `build_report_explanation()` 호출 | 챗봇 turn과 report explanation LLM trace의 연결이 약하다. |

## 2. 목표

챗봇 대화 추적의 목표는 "Discord에서 사용자가 어떤 발화를 했고, FinBrief가 어떤 intent/tool/reply로 처리했는지 Langfuse에서 확인할 수 있게 하는 것"이다.

핵심 목표:

1. 챗봇 메시지 1개를 Langfuse trace 1개로 기록한다.
2. intent parsing, topic matching, subscription tool action, reply formatting을 span으로 구분한다.
3. LLM intent/recommend 호출에는 `trace_id`, `session_id`, `generation_name`, `node`, `tags` metadata를 전달한다.
4. Discord user id, channel id, 원문 메시지는 기본적으로 저장하지 않거나 hash/masking한다.
5. report run trace와 연결 가능한 `linked_run_id`, `linked_trace_id` metadata를 남긴다.
6. Langfuse가 꺼져 있거나 실패해도 챗봇 응답은 계속 동작한다.

## 3. 포함 범위와 제외 범위

### 3.1 포함 범위

| 우선순위 | 범위 | 설명 |
| --- | --- | --- |
| P0 | 챗봇 turn trace | `finbrief.chatbot.turn` trace 또는 root span 생성 |
| P0 | intent/tool span | `parse_intent`, `topic_match`, `subscription_action`, `reply_format` 단계 span |
| P0 | LLM metadata 연결 | `parse_intent()`, `recommend_topics()`, `recommend_from_subs()`의 `llm.chat_json()`에 metadata 전달 |
| P0 | 개인정보 최소화 | Discord raw id는 hash, 원문 메시지는 capture 정책에 따라 masked 또는 미저장 |
| P0 | guardrail score | 투자 판단 요청 차단, unknown fallback, tool success를 score/metadata로 기록 |
| P1 | report explanation trace 연결 | 챗봇의 `explain_report` intent와 report explanation LLM trace 연결 |
| P1 | Supabase chat eval 저장 | 필요 시 `eval_runs`에 `chatbot.*` eval도 저장 |
| P2 | 대화 세션 추적 | 같은 사용자/채널의 여러 turn을 session으로 묶어 흐름 분석 |
| P2 | Langfuse dataset | 실패한 챗봇 intent를 dataset으로 export해 prompt/rule 개선 |

### 3.2 제외 범위

| 제외 항목 | 이유 |
| --- | --- |
| Discord 원문 전체 장기 저장 | 개인정보와 민감 발화 노출 리스크가 크다. |
| Discord 메시지 로그 DB 테이블 신설 | MVP에는 Langfuse trace와 기존 eval 저장으로 충분하다. |
| 버튼/select menu UI 추적 | 아직 UI 자체가 구현되어 있지 않으므로 후속으로 둔다. |
| LLM-as-a-Judge 대화 평가 | 비용과 변동성이 커서 deterministic score를 우선한다. |
| 모든 Discord 이벤트 추적 | guild join, typing, slash sync 같은 운영 이벤트는 P0에서 제외한다. |

## 4. 권장 접근안

### 4.1 접근안 A - `chatbot.handle()` 내부에서 trace 생성

`chatbot.handle()` 시작 시 `observability.chatbot_trace()` 또는 `observability.span()`을 열고, 내부 단계마다 span을 만든다.

장점:

- slash command, mention, DM이 모두 같은 경로로 추적된다.
- 테스트하기 쉽다.
- Discord SDK와 observability 코드가 섞이지 않는다.

단점:

- Discord interaction id 같은 플랫폼 metadata를 넘기려면 `handle()` 인자가 조금 늘어난다.

### 4.2 접근안 B - `discord_bot.py` entrypoint에서 trace 생성

Discord 이벤트 핸들러에서 trace를 만들고 `handle()`에는 `trace_id`만 넘긴다.

장점:

- interaction id, guild id, channel id를 바로 접근할 수 있다.
- Discord별 metadata를 풍부하게 남길 수 있다.

단점:

- slash command와 on_message 양쪽에 중복 코드가 생긴다.
- 향후 FastAPI chatbot route가 생기면 추적 로직을 재사용하기 어렵다.

### 4.3 추천안

P0는 **접근안 A**를 권장한다.

`chatbot.handle()`은 이미 모든 챗봇 대화가 통과하는 단일 경로다. 따라서 이 함수 안에서 turn trace를 만들고, `discord_bot.py`는 `channel_id`와 선택적 `platform_context`만 전달하는 얇은 entrypoint로 유지한다. 플랫폼별 raw id는 `chatbot_observability.py`에서 hash 처리해 metadata로 넣는다.

## 5. 목표 trace 구조

```text
trace/span: finbrief.chatbot.turn
  metadata:
    channel: discord
    user_hash: usr_xxx
    channel_hash: ch_xxx
    message_hash: msg_xxx
    capture_io: true/false
    app_env: prod
  span: chatbot.intent.parse
    generation: chatbot.intent.parse_llm       # LLM 사용 시
    output: {intent, topic_id, parser: llm|rule}
  span: chatbot.topic.match
    output: {topic_id, suggestion_count, clarify_required}
  span: chatbot.guardrail
    output: {investment_advice_blocked: true/false}
  span: chatbot.subscription.action
    output: {action, status, topic_id, used, max_topics}
  span: chatbot.report.explain                 # explain_report intent일 때
    generation: report.explanation             # 기존 report_explainer LLM metadata와 연결
  span: chatbot.reply.format
    output: {intent, status, reply_length, emoji_used}
  score: chatbot.tool_success
  score: chatbot.safety.blocked_advice
  score: chatbot.intent_resolved
```

## 6. 개인정보와 원문 저장 정책

### 6.1 기본 원칙

Discord 챗봇 trace는 사용자 발화가 포함될 수 있으므로 report/card trace보다 더 보수적으로 다룬다.

| 데이터 | 기본 정책 |
| --- | --- |
| Discord user id | 원문 저장 금지, salted hash만 metadata 저장 |
| Discord channel id | 원문 저장 금지, salted hash만 metadata 저장 |
| Discord guild id | 선택 저장. 데모에서는 hash 권장 |
| 사용자 메시지 원문 | `LANGFUSE_CAPTURE_IO=false`면 저장 금지 |
| 사용자 메시지 hash | 중복/재현 확인용으로 저장 가능 |
| 챗봇 reply 원문 | 기본은 길이/상태만 저장, 데모 필요 시 masking 후 저장 |
| API key/webhook/token | 항상 redaction |

### 6.2 Capture mode

| 설정 | 동작 |
| --- | --- |
| `LANGFUSE_CAPTURE_IO=false` | input/output 원문을 Langfuse에 보내지 않고 intent, topic_id, status, length만 기록 |
| `LANGFUSE_CAPTURE_IO=true` | `llm_guardrails.mask_sensitive_text()` 적용 후 masked input/output만 저장 |

### 6.3 Hash salt

신규 환경변수 후보:

```text
FINBRIEF_TRACE_SALT=
```

salt가 없으면 `app_name` 또는 고정 fallback을 쓰되, 운영에서는 별도 secret으로 설정한다. salt 자체는 Langfuse metadata에 넣지 않는다.

## 7. 파일별 설계

| 파일 | 변경 방향 |
| --- | --- |
| `app/services/chatbot_observability.py` | 신규. 챗봇 trace id, hash, metadata, span helper, capture policy 담당 |
| `app/services/chatbot.py` | `handle()`에서 turn trace 열기, intent/tool/reply span 연결, LLM metadata 전달 |
| `app/services/discord_bot.py` | interaction/message context를 `handle()`에 전달. observability 직접 의존은 최소화 |
| `app/core/llm.py` | 기존 `metadata` 인자 유지. 챗봇 호출부에서 metadata를 넘기는 방식으로 사용 |
| `app/core/observability.py` | 필요 시 `trace_context` 재사용 helper만 소폭 추가 |
| `app/core/schemas.py` | 필요 시 `AdminCommandResponse`에 `trace_id` 추가 검토 |
| `tests/test_chatbot_observability.py` | hash/redaction/capture policy 테스트 |
| `tests/test_chatbot.py` | handle 응답이 trace_id를 포함하거나 기존 응답이 깨지지 않는지 테스트 |
| `tests/test_analyze_llm.py` 또는 신규 테스트 | 챗봇 LLM 호출 metadata 전달 검증 |

## 8. 세부 구현 계획

### Phase 1 - 챗봇 observability helper 추가

목표: 개인정보를 보호하면서 trace metadata를 안정적으로 만들 수 있게 한다.

작업:

1. `app/services/chatbot_observability.py` 생성
2. `hash_identifier(value, salt)` 구현
3. `build_turn_metadata(channel, ext_user_id, channel_id, message, settings)` 구현
4. `capture_text(text, settings)` 구현
5. `chatbot_turn_trace(...)` context manager 구현

수용 기준:

- raw Discord user/channel id가 metadata에 남지 않는다.
- message 원문은 capture 정책에 따라 masked 또는 제외된다.
- Langfuse disabled 상태에서 no-op으로 통과한다.

### Phase 2 - `chatbot.handle()` turn trace 연결

목표: 챗봇 요청 1개를 trace 1개로 볼 수 있게 한다.

작업:

1. `handle(..., trace_context: dict | None = None)` 인자 추가
2. handle 시작 시 `finbrief.chatbot.turn` span 생성
3. 최종 응답에 `trace_id`를 선택적으로 포함할지 결정
4. root output에 `intent`, `status`, `topic_id`, `reply_length` 기록

수용 기준:

- slash command와 mention/DM 모두 같은 trace 구조를 사용한다.
- 기존 `AdminCommandResponse` 계약을 깨지 않는다.
- Langfuse 실패 시 Discord 응답이 실패하지 않는다.

### Phase 3 - intent parsing과 LLM metadata 연결

목표: 챗봇 LLM 호출이 Langfuse에서 어떤 대화 turn에 속하는지 알 수 있게 한다.

작업:

1. `parse_intent(message, catalog, trace_id=None, turn_id=None)` 인자 추가
2. `recommend_topics()`, `recommend_from_subs()`에 metadata 인자 추가
3. `llm.chat_json()` 호출 시 `observability.build_llm_metadata()` 사용
4. metadata tags에 `finbrief`, `chatbot`, `intent` 또는 `recommendation` 추가

수용 기준:

- Langfuse generation name이 `chatbot.intent_parse`, `chatbot.topic_recommend`로 구분된다.
- metadata에 raw message 대신 message hash 또는 masked message만 남는다.

### Phase 4 - tool action span 추가

목표: 구독 추가/삭제/조회가 어느 단계에서 막혔는지 보이게 한다.

대상 action:

| intent | span name | output |
| --- | --- | --- |
| `add_topic` | `chatbot.subscription.add` | `topic_id`, `status`, `used`, `max_topics`, `error_code` |
| `delete_topic` | `chatbot.subscription.delete` | `topic_id`, `status` |
| `list_topics` | `chatbot.subscription.list` | `used`, `max_topics`, `catalog_count` |
| `tier_status` | `chatbot.subscription.tier` | `tier`, `used`, `max_topics` |
| `recommend_topics` | `chatbot.topic.recommend` | `suggestion_count`, `suggested_topic_ids` |
| `clarify_topic` | `chatbot.topic.clarify` | `suggestion_count`, `selected_topic_id=null` |
| `explain_report` | `chatbot.report.explain` | `focus_count`, `evidence_count`, `status` |

수용 기준:

- 실패한 add/delete 요청의 원인이 Langfuse에서 보인다.
- 모호한 토픽 요청은 clarify span으로 확인된다.

### Phase 5 - 챗봇 deterministic score 추가

목표: 대화 품질과 safety를 숫자로 확인한다.

평가 항목:

| score | 기준 |
| --- | --- |
| `chatbot.intent_resolved` | `intent != unknown`이면 1.0, unknown이면 0.0 |
| `chatbot.tool_success` | status가 completed이면 1.0, blocked/failed이면 0.0 |
| `chatbot.safety.blocked_advice` | 투자 판단 요청을 차단했으면 1.0 |
| `chatbot.reply_format` | reply가 비어 있지 않고 길이가 Discord 사용에 적절하면 1.0 |

수용 기준:

- Langfuse score가 report score와 이름 충돌 없이 `chatbot.*` prefix로 기록된다.
- score 전송 실패는 챗봇 응답에 영향을 주지 않는다.

### Phase 6 - report trace 연결

목표: 챗봇으로 "오늘 리포트 설명"을 요청했을 때 관련 report result와 연결한다.

작업:

1. `explain_report` intent에서 `get_latest_result()`의 `run_id`, `trace_id`, `run_date`를 turn metadata에 추가
2. `build_report_explanation()` 내부 LLM metadata에 `parent_chat_trace_id` 또는 `chat_turn_id` 추가
3. Langfuse UI에서 chatbot turn과 report run을 `linked_run_id`, `linked_trace_id`로 검색 가능하게 한다.

수용 기준:

- "오늘 리포트에서 뭐 봐야 해?" 요청이 어떤 report run을 설명했는지 추적 가능하다.

## 9. API/응답 계약 검토

현재 `chatbot.handle()`은 dict를 반환한다.

```python
{
    "intent": intent,
    "status": status,
    "reply": reply,
    "topic": topic,
}
```

추가 후보:

```python
{
    "trace_id": "chat_trace_...",
    "turn_id": "turn_...",
}
```

권장:

- P0에서는 내부 trace만 기록하고 Discord reply에는 trace id를 노출하지 않는다.
- FastAPI admin chatbot route가 생기면 응답에 `trace_id`를 포함한다.
- 디버깅이 필요할 때만 `FINBRIEF_CHATBOT_DEBUG_TRACE=true`로 reply 하단에 trace id를 붙인다.

## 10. 테스트 계획

| 테스트 파일 | 검증 내용 |
| --- | --- |
| `tests/test_chatbot_observability.py` | hash, redaction, capture policy, no-op context |
| `tests/test_chatbot.py` | 기존 add/list/delete/help/recommend/explain_report 응답 회귀 |
| `tests/test_chatbot_persona.py` | 투자 판단 차단과 후보 제시 응답 유지 |
| `tests/test_analyze_llm.py` 또는 신규 `tests/test_chatbot_llm_metadata.py` | 챗봇 LLM 호출 metadata 전달 |
| `tests/test_ci_cd_contracts.py` | 필요 시 `.env.example`에 `FINBRIEF_TRACE_SALT`, `FINBRIEF_CHATBOT_TRACE_ENABLED` 문서화 |

핵심 검증 명령:

```powershell
python -m compileall app
python -m pytest -p no:cacheprovider --basetemp .pytest_cache\basetemp-chatbot-langfuse tests\test_chatbot.py tests\test_chatbot_persona.py tests\test_chatbot_observability.py -q
$env:ENABLE_MOCK_DATA='true'; $env:LANGFUSE_ENABLED='false'; $env:FINBRIEF_LLM_STUB='1'; python -m pytest -p no:cacheprovider --basetemp .pytest_cache\basetemp-chatbot-langfuse-full --disable-warnings
```

## 11. 사용자 결정 및 준비 사항

| 항목 | 결정/준비 | 권장 |
| --- | --- | --- |
| 챗봇 원문 저장 여부 | Langfuse에 masked message/reply를 저장할지 | 데모는 `LANGFUSE_CAPTURE_IO=false` 기본, 필요 시 true |
| Discord ID 처리 | raw id 저장 여부 | raw 저장 금지, salted hash |
| `FINBRIEF_TRACE_SALT` | user/channel hash용 salt | 운영/배포 Secrets에 등록 |
| reply에 trace id 표시 | 사용자에게 trace id를 보여줄지 | 기본 비표시 |
| Langfuse score 범위 | chatbot score를 `eval_runs`에도 저장할지 | P0는 Langfuse score만, P1에서 DB 저장 |
| report trace 연결 | explain_report 요청을 report run과 연결할지 | P1에 포함 권장 |

## 12. 수용 기준

- [ ] Discord `/finbrief message: 나스닥 구독` 실행 시 Langfuse에 `finbrief.chatbot.turn` trace/span이 생성된다.
- [ ] trace metadata에 raw Discord user id/channel id가 남지 않는다.
- [ ] `add_topic`, `list_topics`, `delete_topic`, `recommend_topics`, `explain_report`, `unknown` intent가 span output으로 구분된다.
- [ ] LLM intent/recommend 호출이 발생하면 generation metadata에 `trace_id`, `session_id`, `node`, `tags`가 포함된다.
- [ ] 투자 판단 요청은 `chatbot.safety.blocked_advice` score로 확인 가능하다.
- [ ] Langfuse disabled/no-key 상태에서도 챗봇 응답이 정상 동작한다.
- [ ] 전체 테스트가 mock/stub 환경에서 통과한다.

## 13. 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| 사용자 메시지에 개인정보 포함 | Langfuse UI 노출 위험 | capture off 기본, masking 후 저장, raw id 금지 |
| Langfuse 지연/장애 | Discord 응답 지연 가능 | no-op/fail-open, span 전송 실패 무시 |
| trace 과다 생성 | Langfuse noise 증가 | P0는 command/mention/DM user turn만 추적, 내부 Discord 이벤트 제외 |
| LLM stub 상태 | generation trace가 비어 보일 수 있음 | tool/action span과 score를 함께 기록 |
| response 계약 변경 | 기존 테스트/Discord bot 깨짐 | trace_id는 내부 metadata로 시작, reply 노출은 debug 옵션 |

## 14. 발표 시연 포인트

1. Discord에서 `/finbrief message: 금리 구독` 실행
2. 후보 제시 reply 확인
3. Langfuse에서 `finbrief.chatbot.turn` 검색
4. intent parse, topic clarify span 확인
5. `/finbrief message: 미국 기준금리 구독` 실행
6. subscription add span과 tool success score 확인
7. `/finbrief message: 오늘 리포트에서 뭐 봐야 해?` 실행
8. chatbot turn trace와 report run trace의 `linked_run_id`, `linked_trace_id` 연결 설명

## 15. 구현 우선순위

7일 프로젝트 안정화 관점에서 권장 순서는 다음과 같다.

1. `chatbot_observability.py` helper와 tests
2. `handle()` turn trace와 tool action span
3. 챗봇 LLM 호출 metadata 연결
4. safety/tool score 전송
5. `explain_report`와 report run trace 연결
6. capture policy와 README/운영 문서 반영

첫 구현 단위는 1~3번까지만 묶는 것이 좋다. 이 범위만으로도 "챗봇 대화까지 Langfuse에서 보인다"는 데모가 가능하고, 개인정보 저장 정책을 무리하게 넓히지 않는다.

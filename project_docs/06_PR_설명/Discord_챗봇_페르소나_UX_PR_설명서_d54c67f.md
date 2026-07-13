# Discord 챗봇 페르소나 및 대화형 UX 강화 PR 설명서

> 대상 커밋: `d54c67fee7f08ba705d980944cff6ab983d7bd47`
> Short SHA: `d54c67f`
> 작성일: 2026-07-13
> 대상 브랜치: `feat/#n`
> 관련 기획서: `project_docs/04_구현_기획/Discord_챗봇_페르소나_대화형_UX_강화_기획.md`

## 1. PR 개요

이번 PR은 Discord 관리 챗봇을 단순 명령 응답에서 `브리핑 메이트` persona 기반의 대화형 UX로 강화한다.

기존 챗봇은 `구독 완료`, `현재 구독`, `티어`처럼 기능 결과만 짧게 반환했다. 이번 변경으로 사용자는 `/finbrief`에서 자연어로 토픽을 추가·조회·삭제할 수 있고, 모호한 키워드는 후보를 확인한 뒤 다시 선택할 수 있으며, 투자 판단 요청은 안전하게 차단된다.

## 2. 주요 변경 사항

### 2.1 챗봇 persona 정책 추가

신규 파일 `app/services/chatbot_persona.py`를 추가했다.

주요 내용:

- 챗봇 이름: `FinBrief Mate` / `브리핑 메이트`
- 도움말 예시 문장 관리
- 초보 사용자 추천 토픽 id 관리
- 투자 판단 요청 탐지 키워드 관리

### 2.2 응답 formatter 분리

신규 파일 `app/services/chatbot_responses.py`를 추가했다.

주요 응답:

- 도움말
- 토픽 추가 성공
- 토픽 목록 조회
- 티어 상태
- 토픽 삭제 성공
- 모호한 토픽 후보 제시
- 추천 토픽 안내
- 투자 판단 요청 차단
- 알 수 없는 요청 안내

### 2.3 후보 토픽 제안 로직 추가

신규 파일 `app/services/chatbot_suggestions.py`를 추가했다.

사용자 메시지에서 `구독`, `삭제`, `추천` 같은 action word를 제거한 뒤 토픽 이름, normalized name, source query, news keyword를 기준으로 후보를 점수화한다.

특히 `금리 구독`처럼 여러 토픽으로 해석될 수 있는 입력은 즉시 저장하지 않고 다음과 같은 후보를 먼저 제시한다.

- 미국 10년물 금리
- 미국 기준금리
- 한국 기준금리
- 금리인하

또한 `금리`가 단일 글자 토픽 `금`으로 오매칭되지 않도록, 한 글자 토픽은 독립 토큰으로 입력된 경우에만 매칭한다.

### 2.4 chatbot handler intent 확장

`app/services/chatbot.py`를 확장했다.

추가 intent:

- `help`
- `recommend_topics`
- `clarify_topic`

핵심 동작:

- `뭐 할 수 있어?`, `도움말` → 도움말 응답
- `처음인데 뭐 받아보면 좋아?`, `추천해줘` → 초보자용 추천 토픽 응답
- `금리 구독` → 후보 토픽 제시
- `오늘 비트코인 사야 해?` → 투자 판단 차단
- `나스닥 구독해줘` → 기존 구독 tool 호출
- `내 토픽 보여줘` → 구독 목록 조회

### 2.5 Discord slash command 문구 개선

`app/services/discord_bot.py`의 slash command 설명과 입력 예시를 사용자 친화적으로 수정했다.

변경 후:

- command 설명: `브리핑 메이트에게 관심 금융 토픽을 자연어로 관리합니다.`
- 예시: `나스닥 구독`, `내 토픽 보여줘`, `비트코인 취소`, `추천해줘`

### 2.6 스키마 계약 확장

`app/core/schemas.py`의 `AdminCommandResponse.intent` literal에 다음 값을 추가했다.

- `help`
- `recommend_topics`
- `clarify_topic`

### 2.7 README 업데이트

`README.md`에 Discord 관리 챗봇 상태, 주요 파일, 사용 예시, 실행 방법을 추가했다.

## 3. 테스트 추가 및 변경

### 3.1 신규 테스트

`tests/test_chatbot_persona.py`

검증 항목:

- 도움말 응답이 `브리핑 메이트` persona와 예시를 포함하는지
- 투자 판단 요청을 차단하고 브리핑 구독으로 유도하는지
- `금리` 키워드가 후보 토픽을 반환하고 `금` 토픽으로 오매칭되지 않는지
- 도움말 intent가 persona 응답을 사용하는지
- 추천 intent가 초보자용 추천 토픽을 반환하는지
- `금리 구독`이 바로 저장되지 않고 `clarify_topic`으로 처리되는지

### 3.2 기존 테스트 확장

`tests/test_chatbot.py`

- 기존 `나스닥 구독해줘` 경로가 새 persona 응답에서도 구독 성공과 channel id 저장을 유지하는지 검증했다.

## 4. 검증 결과

이번 커밋 전 아래 검증을 수행했다.

| 검증 항목 | 명령 | 결과 |
| --- | --- | --- |
| 챗봇 단위 테스트 | `python -m pytest -p no:cacheprovider --basetemp .pytest_cache\basetemp-chatbot-persona-green2 tests\test_chatbot.py tests\test_chatbot_persona.py -q` | `10 passed` |
| Python compile | `python -m compileall app` | 통과 |
| 전체 테스트 | `python -m pytest -p no:cacheprovider --basetemp .pytest_cache\basetemp-chatbot-persona-full --disable-warnings` | `119 passed, 1 warning` |
| whitespace 검사 | `git diff --check`, `git diff --cached --check` | 통과 |

## 5. 아직 구현하지 못한 부분

| 항목 | 설명 |
| --- | --- |
| 실제 Discord 서버에서 slash command smoke | 로컬 단위 테스트는 통과했지만, 실제 Discord guild에서 `/finbrief` 명령 sync와 응답 표시 확인은 별도 필요 |
| 장기 대화 메모리 | 현재는 단일 메시지 기반 intent 처리이며, 이전 대화 맥락을 기억하는 multi-turn state는 없음 |
| 버튼/셀렉트 UI | 후보 토픽은 텍스트 목록으로 제시하며 Discord select menu나 버튼 interaction은 아직 미구현 |
| FastAPI admin chatbot route | 현재 구현은 Discord bot entrypoint 중심이며 `/api/v1/chat/admin` route는 제공하지 않음 |
| Langfuse conversation trace 세분화 | 챗봇 intent parsing과 tool call을 Langfuse span으로 세분화하는 작업은 후속 범위 |

## 6. 사용자가 직접 준비해야 하는 작업

### 6.1 Discord bot 실행 환경

실제 Discord에서 확인하려면 `.env` 또는 배포 환경에 다음 값이 필요하다.

| 변수 | 설명 |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Discord bot token |
| `DISCORD_GUILD_ID` | slash command를 sync할 Discord guild id |

실행:

```powershell
python -m app.services.discord_bot
```

### 6.2 Discord 권한 확인

Discord Developer Portal과 서버에서 다음을 확인한다.

- Bot이 대상 서버에 초대되어 있는지
- `applications.commands` scope가 포함되어 있는지
- slash command 사용 권한이 있는지
- 봇이 응답할 채널에 접근 가능한지

### 6.3 Supabase 영속 저장 확인

로컬 memory repository는 프로세스 재시작 시 구독 상태가 초기화된다. 실제 구독 상태를 유지하려면 다음 값이 필요하다.

| 변수 | 설명 |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | 서버 측 service role key |

`SUPABASE_URL`이 설정되면 `app/services/discord_bot.py`는 Supabase repository를 사용한다.

## 7. 리뷰 포인트

- `브리핑 메이트` persona가 너무 장황하지 않고 Discord ephemeral reply에 적합한가
- `금리`, `환율` 같은 모호한 키워드에서 후보 제시가 자연스러운가
- 투자 판단 차단 문구가 과도하게 딱딱하지 않은가
- 한 글자 토픽 `금`과 `금리` 키워드가 서로 오매칭되지 않는가
- FastAPI admin chatbot route가 발표 시나리오에 필요한지 여부

## 8. 기대 효과

이번 변경으로 사용자는 명령어 문법을 외우지 않아도 Discord에서 자연어로 구독 기능을 사용할 수 있다.

발표 시에는 다음 시나리오를 더 자연스럽게 시연할 수 있다.

1. `/finbrief message: 처음인데 뭐 받아보면 좋아?`
2. `/finbrief message: 나스닥 구독해줘`
3. `/finbrief message: 금리 구독`
4. `/finbrief message: 미국 기준금리 구독`
5. `/finbrief message: 내 토픽 보여줘`
6. `/finbrief message: 오늘 비트코인 사야 해?`

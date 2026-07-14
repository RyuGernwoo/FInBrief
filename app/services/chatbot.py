"""관리 챗봇 핸들러 — 메시지 → 의도(LLM/규칙) → SubscriptionService → 응답.
   LLM은 '의도 파악'에만. 검증·저장은 서비스."""
from __future__ import annotations

import json
import re

from app.core import llm
from app.services import chatbot_responses as replies
from app.services.chatbot_persona import is_investment_advice_request
from app.services.chatbot_suggestions import suggest_topics, starter_topics
from app.services.subscription_service import SubscriptionService, TopicNotAllowed, MaxTopicsExceeded

INTENT_SYSTEM = (
    "너는 금융 카드뉴스 구독 관리 봇의 의도 분류기다. 사용자 메시지를 아래 JSON으로만 답한다. "
    '{"intent": "add_topic|list_topics|delete_topic|tier_status|help|recommend_topics|unknown", '
    '"topic": "<카탈로그 토픽명 또는 null>"}'
    " topic은 반드시 주어진 카탈로그 중 하나로 매핑하고, 없으면 null."
)

RECOMMEND_SYSTEM = (
    "너는 금융 구독 봇의 토픽 추천기다. 사용자 관심사에 맞는 토픽을 카탈로그에서 "
    '최대 5개 골라 JSON {"topics": ["정확한 카탈로그명", ...]} 로만 답한다. 카탈로그 밖 이름 금지.'
)

_TYPE_LABEL = {"indicator": "지표", "asset": "자산", "sector": "섹터", "keyword": "키워드"}
_TYPE_ORDER = ["indicator", "asset", "sector", "keyword"]


def _category_summary(catalog: list, per: int = 3) -> str:
    """카테고리(type)별 대표 per개씩 + 총 개수. 전량 나열(117개) 대신 요약."""
    from collections import defaultdict

    buckets: dict = defaultdict(list)
    for t in catalog:
        buckets[str(getattr(t, "type", "기타"))].append(t.name)
    keys = [k for k in _TYPE_ORDER if k in buckets] + [k for k in buckets if k not in _TYPE_ORDER]
    parts = [f"{_TYPE_LABEL.get(k, k)}: {', '.join(buckets[k][:per])}" for k in keys]
    return " / ".join(parts) + f" … (총 {len(catalog)}개)"


def _table_cell(value: object) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


def _type_label(topic_type: object) -> str:
    return _TYPE_LABEL.get(str(topic_type), str(topic_type or "-"))


def _subscription_table(current: list, catalog: list) -> str:
    topics_by_id = {t.topic_id: t for t in catalog}
    rows = ["| 번호 | 현재 구독 토픽 | 유형 |", "| ---: | --- | --- |"]
    if not current:
        rows.append("| - | 없음 | - |")
        return "\n".join(rows)

    for index, subscription in enumerate(current, start=1):
        topic = topics_by_id.get(subscription.topic_id)
        name = topic.name if topic else subscription.topic_id
        topic_type = topic.type if topic else "-"
        rows.append(f"| {index} | {_table_cell(name)} | {_table_cell(_type_label(topic_type))} |")
    return "\n".join(rows)


def _catalog_table(catalog: list) -> str:
    from collections import defaultdict

    buckets: dict = defaultdict(list)
    for topic in catalog:
        buckets[str(getattr(topic, "type", "기타"))].append(topic.name)
    keys = [key for key in _TYPE_ORDER if key in buckets] + [
        key for key in buckets if key not in _TYPE_ORDER
    ]

    rows = ["| 유형 | 구독 가능 토픽 |", "| --- | --- |"]
    for key in keys:
        names = ", ".join(_table_cell(name) for name in buckets[key])
        rows.append(f"| {_table_cell(_type_label(key))} | {names} |")
    return "\n".join(rows)


def _format_list_topics_reply(current: list, catalog: list, tier: dict) -> str:
    return (
        f"📋 **현재 구독** ({tier['used']}/{tier['max_topics']})\n"
        f"{_subscription_table(current, catalog)}\n\n"
        f"🗂️ **전체 구독 가능 토픽** (총 {len(catalog)}개)\n"
        f"{_catalog_table(catalog)}"
    )


def recommend_topics(message: str, catalog: list, k: int = 5) -> list[str]:
    """자연어 관심사 → 카탈로그 토픽 추천(정확명). LLM 결과는 카탈로그로 검증, 키 없으면 대표 토픽."""
    names = [t.name for t in catalog]
    if not llm.use_llm():
        return names[:k]                                      # 폴백: 대표 토픽 상위 N
    try:
        raw = llm.chat_json(RECOMMEND_SYSTEM + "\n카탈로그: " + ", ".join(names), message)
        return [n for n in raw.get("topics", []) if n in names][:k]   # ★ 카탈로그 검증
    except Exception:
        return names[:k]


def recommend_from_subs(cur: list, catalog: list, k: int = 3) -> list[str]:
    """현재 구독을 컨텍스트로 보완/유사 토픽 추천(카탈로그 검증). 구독 없으면 대표 토픽."""
    names = [t.name for t in catalog]
    names_by_id = {t.topic_id: t.name for t in catalog}
    cur_names = [names_by_id.get(s.topic_id, s.topic_id) for s in cur]
    rest = [n for n in names if n not in cur_names]
    if not llm.use_llm():
        return rest[:k]
    try:
        ctx = ("현재 구독: " + (", ".join(cur_names) or "없음")
               + "\n이 사용자에게 보완/유사한 토픽을 추천해줘.")
        raw = llm.chat_json(RECOMMEND_SYSTEM + "\n카탈로그: " + ", ".join(names), ctx)
        picks = [n for n in raw.get("topics", []) if n in names and n not in cur_names]
        return picks[:k]
    except Exception:
        return rest[:k]


def welcome_text(service: "SubscriptionService") -> str:
    """봇 초대/도움말 온보딩 문구. 추천만 LLM, 본문은 비용·지연 안전하게 고정 텍스트."""
    cats = _category_summary(service.catalog())
    return ("👋 **FinBrief** 구독 봇이에요! 관심 지표를 고르면 매일 아침 7시에 카드뉴스로 브리핑해드려요.\n"
            "• 구독:  `나스닥 구독해줘`  또는  `/finbrief 나스닥 구독`  (저를 @멘션해도 돼요)\n"
            "• 조회:  `내 토픽 목록`   • 취소:  `나스닥 빼줘`   • 등급:  `내 등급`\n"
            f"• 구독 가능(예시): {cats}\n"
            "관심사만 편하게 말해도 알맞은 토픽을 추천해드려요. 예) `반도체랑 AI 소식 받고 싶어`")


def _message_tokens(message: str) -> set[str]:
    return {token for token in re.split(r"[\s,./|:;!?()\[\]{}\"']+", message) if token}


def _topic_matches(message: str, lowered_message: str, topic_id: str, topic_name: str) -> bool:
    if topic_id and topic_id in lowered_message:
        return True

    name = str(topic_name).strip()
    if not name:
        return False
    if len(name) == 1:
        return name in _message_tokens(message)
    return name in message


def _should_clarify_selected_topic(
    message: str,
    names: dict,
    topic_id: str | None,
    suggestions: list,
) -> bool:
    if not topic_id or len(suggestions) <= 1:
        return False
    topic_name = names.get(topic_id)
    if not topic_name:
        return False
    if _topic_matches(message, message.lower(), topic_id, topic_name):
        return False
    return True


def _rule_intent(message: str, names: dict) -> tuple[str, str | None]:
    m = message.lower()
    topic = next(
        (tid for tid, nm in names.items() if _topic_matches(message, m, tid, nm)),
        None,
    )
    if any(k in message for k in ("도움말", "사용법", "뭐 할 수", "뭘 할 수")) or "help" in m:
        return "help", None
    if any(k in message for k in ("추천", "뭐 받아", "인기", "처음")):
        return "recommend_topics", None
    if any(k in message for k in ("추가", "구독", "등록")) or "add" in m:
        return "add_topic", topic
    if any(k in message for k in ("삭제", "제거", "취소", "해지", "빼", "지워")) or any(k in m for k in ("remove", "delete")):
        return "delete_topic", topic
    if any(k in message for k in ("목록", "내 토픽", "내토픽", "조회", "리스트")) or "list" in m:
        return "list_topics", None
    if any(k in message for k in ("티어", "등급", "요금", "개수")):
        return "tier_status", None
    return "unknown", topic


def parse_intent(message: str, catalog: list) -> tuple[str, str | None]:
    names = {t.topic_id: t.name for t in catalog}
    if llm.use_llm():
        try:
            sys = INTENT_SYSTEM + "\n카탈로그: " + json.dumps(names, ensure_ascii=False)
            raw = llm.chat_json(sys, message)
            intent = raw.get("intent", "unknown")
            topic = raw.get("topic")
            if topic and topic not in names:
                topic = next((tid for tid, nm in names.items() if nm == topic), None)
            return intent, topic
        except Exception:
            pass
    return _rule_intent(message, names)


def _resp(intent, status, reply, topic=None):
    return {"intent": intent, "status": status, "reply": reply, "topic": topic}


def handle(service: SubscriptionService, channel: str, ext_user_id: str, message: str,
           channel_id: str | None = None) -> dict:
    catalog = service.catalog()
    names = {t.topic_id: t.name for t in catalog}
    intent, topic = parse_intent(message, catalog)
    suggestions = suggest_topics(message, catalog, limit=5)
    cats = _category_summary(catalog)

    if is_investment_advice_request(message):
        return _resp("unknown", "blocked", replies.format_investment_advice_reply(), topic)

    if intent == "help":
        return _resp(intent, "completed", replies.format_help_reply())
    if intent == "recommend_topics":
        return _resp(intent, "completed", replies.format_recommend_topics(starter_topics(catalog, limit=5)))

    if intent == "list_topics":
        cur = service.list(channel, ext_user_id)
        tier = service.tier(channel, ext_user_id)
        return _resp(intent, "completed", _format_list_topics_reply(cur, catalog, tier))
    if intent == "tier_status":
        t = service.tier(channel, ext_user_id)
        return _resp(intent, "completed", replies.format_tier_status(t["tier"], t["used"], t["max_topics"]))
    if intent == "add_topic":
        if _should_clarify_selected_topic(message, names, topic, suggestions):
            return _resp("clarify_topic", "blocked", replies.format_clarify_topic_reply(suggestions))
        if not topic:
            if suggestions:
                return _resp("clarify_topic", "blocked", replies.format_clarify_topic_reply(suggestions))
            reco = recommend_topics(message, catalog)
            hint = f" 혹시 이런 토픽 어때요? {', '.join(reco)}" if reco else f" 가능(예시): {cats}"
            return _resp(intent, "blocked", f"어떤 토픽을 구독할까요?{hint}")
        try:
            cur = service.add(channel, ext_user_id, topic, channel_id)
            tier = service.tier(channel, ext_user_id)
            return _resp(
                intent,
                "completed",
                replies.format_add_success(names.get(topic, topic), len(cur), tier["max_topics"]),
                topic,
            )
        except TopicNotAllowed:
            reply = replies.format_topic_not_allowed(topic, suggestions)
            if not suggestions:
                reply += f"\n구독 가능 예시: {cats}"
            return _resp(intent, "blocked", reply)
        except MaxTopicsExceeded as e:
            return _resp(intent, "blocked", replies.format_topic_limit(int(e.args[0])))
    if intent == "delete_topic":
        # 삭제는 '구독 중인 토픽' 범위로 좁혀 매칭한다. 전체 카탈로그로 보면 "환율" 같은
        # 부분어가 여러 후보(EUR/USD·USD/KRW…)와 모호해지지만, 구독한 게 하나면 바로 제거.
        cur = service.list(channel, ext_user_id)
        sub_ids = {s.topic_id for s in cur}
        if topic not in sub_ids:
            sub_topics = [t for t in catalog if t.topic_id in sub_ids]
            sub_sugg = suggest_topics(message, sub_topics, limit=5)
            if len(sub_sugg) == 1:
                topic = sub_sugg[0].topic_id
            elif len(sub_sugg) > 1:
                return _resp("clarify_topic", "blocked", replies.format_clarify_topic_reply(sub_sugg))
        if topic and topic in sub_ids:
            service.remove(channel, ext_user_id, topic)
            return _resp(intent, "completed", replies.format_delete_success(names.get(topic, topic)), topic)
        if not topic:
            return _resp(intent, "blocked", replies.format_delete_needs_topic())
        subscribed = ", ".join(names.get(t, t) for t in sub_ids) or "없음"
        return _resp(intent, "blocked",
                     f"'{names.get(topic, topic)}'는 현재 구독 목록에 없어요. 현재 구독: {subscribed}")

    reco = recommend_topics(message, catalog)
    reply = f"{replies.format_unknown_reply()}\n🗂️ 구독 가능 예시: {cats}"
    if reco:
        reply += f"\n💡 관심사에 맞춰 추천: {', '.join(reco)}"
    return _resp("unknown", "blocked", reply)

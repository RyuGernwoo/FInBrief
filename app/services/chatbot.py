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
    if any(k in message for k in ("삭제", "취소", "해지", "빼")) or any(k in m for k in ("remove", "delete")):
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

    if is_investment_advice_request(message):
        return _resp("unknown", "blocked", replies.format_investment_advice_reply(), topic)

    if intent == "help":
        return _resp(intent, "completed", replies.format_help_reply())
    if intent == "recommend_topics":
        return _resp(intent, "completed", replies.format_recommend_topics(starter_topics(catalog, limit=5)))

    if intent == "list_topics":
        cur = service.list(channel, ext_user_id)
        subscribed = [names.get(s.topic_id, s.topic_id) for s in cur]
        return _resp(intent, "completed", replies.format_list_topics(subscribed))
    if intent == "tier_status":
        t = service.tier(channel, ext_user_id)
        return _resp(intent, "completed", replies.format_tier_status(t["tier"], t["used"], t["max_topics"]))
    if intent == "add_topic":
        if _should_clarify_selected_topic(message, names, topic, suggestions):
            return _resp("clarify_topic", "blocked", replies.format_clarify_topic_reply(suggestions))
        if not topic:
            if suggestions:
                return _resp("clarify_topic", "blocked", replies.format_clarify_topic_reply(suggestions))
            return _resp(intent, "blocked", replies.format_add_needs_topic([]))
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
            return _resp(intent, "blocked", replies.format_topic_not_allowed(topic, suggestions))
        except MaxTopicsExceeded as e:
            return _resp(intent, "blocked", replies.format_topic_limit(int(e.args[0])))
    if intent == "delete_topic":
        if _should_clarify_selected_topic(message, names, topic, suggestions):
            return _resp("clarify_topic", "blocked", replies.format_clarify_topic_reply(suggestions))
        if not topic:
            if suggestions:
                return _resp("clarify_topic", "blocked", replies.format_clarify_topic_reply(suggestions))
            return _resp(intent, "blocked", replies.format_delete_needs_topic())
        service.remove(channel, ext_user_id, topic)
        return _resp(intent, "completed", replies.format_delete_success(names.get(topic, topic)), topic)
    return _resp("unknown", "blocked", replies.format_unknown_reply())

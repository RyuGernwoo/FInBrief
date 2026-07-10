"""관리 챗봇 핸들러 — 메시지 → 의도(LLM/규칙) → SubscriptionService → 응답.
   LLM은 '의도 파악'에만. 검증·저장은 서비스."""
from __future__ import annotations

import json

from app.core import llm
from app.services.subscription_service import SubscriptionService, TopicNotAllowed, MaxTopicsExceeded

INTENT_SYSTEM = (
    "너는 금융 카드뉴스 구독 관리 봇의 의도 분류기다. 사용자 메시지를 아래 JSON으로만 답한다. "
    '{"intent": "add_topic|list_topics|delete_topic|tier_status|unknown", "topic": "<카탈로그 토픽명 또는 null>"}'
    " topic은 반드시 주어진 카탈로그 중 하나로 매핑하고, 없으면 null."
)


def _rule_intent(message: str, names: dict) -> tuple[str, str | None]:
    m = message.lower()
    topic = next((tid for tid, nm in names.items() if nm in message or tid in m), None)
    if any(k in message for k in ("추가", "구독", "등록")) or "add" in m:
        return "add_topic", topic
    if any(k in message for k in ("삭제", "취소", "해지", "빼")) or any(k in m for k in ("remove", "delete")):
        return "delete_topic", topic
    if any(k in message for k in ("목록", "내 토픽", "내토픽", "조회", "리스트")) or "list" in m:
        return "list_topics", None
    if any(k in message for k in ("티어", "등급", "요금", "개수")):
        return "tier_status", None
    return "unknown", topic


def parse_intent(message: str, catalog: list[dict]) -> tuple[str, str | None]:
    names = {t["topic_id"]: t["name"] for t in catalog}
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


def handle(service: SubscriptionService, channel: str, ext_user_id: str, message: str) -> dict:
    catalog = service.catalog()
    names = {t["topic_id"]: t["name"] for t in catalog}
    intent, topic = parse_intent(message, catalog)
    catalog_str = ", ".join(names.values())

    if intent == "list_topics":
        cur = service.list(channel, ext_user_id)
        return _resp(intent, "completed", f"현재 구독: {', '.join(names.get(t, t) for t in cur) or '없음'}")
    if intent == "tier_status":
        t = service.tier(channel, ext_user_id)
        return _resp(intent, "completed", f"티어: {t['tier']} · 토픽 {t['used']}/{t['max_topics']}")
    if intent == "add_topic":
        if not topic:
            return _resp(intent, "blocked", f"어떤 토픽을 구독할까요? 가능: {catalog_str}")
        try:
            cur = service.add(channel, ext_user_id, topic)
            return _resp(intent, "completed", f"'{names[topic]}' 구독 완료 ✅ (현재 {len(cur)}개)", topic)
        except TopicNotAllowed:
            return _resp(intent, "blocked", f"'{topic}'는 지원하지 않는 토픽이에요. 가능: {catalog_str}")
        except MaxTopicsExceeded as e:
            return _resp(intent, "blocked", f"토픽은 최대 {e.args[0]}개까지예요. 하나 취소 후 추가하세요.")
    if intent == "delete_topic":
        if not topic:
            return _resp(intent, "blocked", "어떤 토픽을 취소할까요?")
        service.remove(channel, ext_user_id, topic)
        return _resp(intent, "completed", f"'{names.get(topic, topic)}' 구독 취소했어요.", topic)
    return _resp("unknown", "blocked", f"구독/조회/취소를 도와드려요. 가능 토픽: {catalog_str}")

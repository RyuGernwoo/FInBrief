from app.services import chatbot
from app.services.subscription_service import SubscriptionService
from app.repositories.memory import create_memory_repositories


def _svc():
    return SubscriptionService(create_memory_repositories())


def test_rule_intent_persists_channel_id(monkeypatch):
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    s = _svc()
    topic = s.catalog()[0]
    r = chatbot.handle(s, "discord", "u1", f"{topic.name} 구독해줘", "12345")
    assert r["intent"] == "add_topic" and r["status"] == "completed" and r["topic"] == topic.topic_id
    assert "아침 브리핑" in r["reply"]
    assert "현재" in r["reply"]
    # 저장에 channel_id 반영
    subs = s.list("discord", "u1")
    assert any(x.topic_id == topic.topic_id and x.discord_channel_id == "12345" for x in subs)


def test_rule_intent_unknown_topic_blocked(monkeypatch):
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    r = chatbot.handle(_svc(), "discord", "u1", "존재하지않는토픽 구독")
    assert r["status"] == "blocked"


def test_llm_intent(monkeypatch):
    import app.core.llm as core_llm
    s = _svc()
    topic = s.catalog()[0]
    monkeypatch.setenv("UPSTAGE_API_KEY", "test")
    monkeypatch.delenv("FINBRIEF_LLM_STUB", raising=False)
    monkeypatch.setattr(core_llm, "chat_json", lambda sys, msg: {"intent": "add_topic", "topic": topic.name})
    r = chatbot.handle(s, "discord", "u2", "구독하고 싶어", "777")
    assert r["topic"] == topic.topic_id and r["status"] == "completed"

from app.services import chatbot
from app.services.subscription_service import SubscriptionService
from app.services._repo_stub import StubTopics, StubUsers, StubSubs

CATALOG = [{"topic_id": "nasdaq", "name": "나스닥"}, {"topic_id": "btc", "name": "비트코인"}]


def _svc():
    return SubscriptionService(StubUsers(), StubSubs(), StubTopics(CATALOG))


def test_rule_intent(monkeypatch):
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    s = _svc()
    r = chatbot.handle(s, "discord", "u1", "나스닥 구독해줘")
    assert r["intent"] == "add_topic" and r["status"] == "completed" and r["topic"] == "nasdaq"
    assert chatbot.handle(s, "discord", "u1", "금 구독")["status"] == "blocked"


def test_llm_intent(monkeypatch):
    import app.core.llm as core_llm
    monkeypatch.setenv("UPSTAGE_API_KEY", "test")
    monkeypatch.delenv("FINBRIEF_LLM_STUB", raising=False)
    monkeypatch.setattr(core_llm, "chat_json", lambda sys, msg: {"intent": "add_topic", "topic": "비트코인"})
    r = chatbot.handle(_svc(), "discord", "u2", "비트코인 소식 받고 싶어")
    assert r["topic"] == "btc" and r["status"] == "completed"

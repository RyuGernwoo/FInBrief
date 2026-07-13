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


def test_recommend_topics_filters_out_of_catalog(monkeypatch):
    """LLM이 카탈로그 밖 이름을 섞어 반환해도 검증으로 걸러진다."""
    import app.core.llm as core_llm
    catalog = _svc().catalog()
    real = catalog[0].name
    monkeypatch.setenv("UPSTAGE_API_KEY", "test")
    monkeypatch.delenv("FINBRIEF_LLM_STUB", raising=False)
    monkeypatch.setattr(core_llm, "chat_json",
                        lambda sys, msg: {"topics": [real, "존재하지않는가짜토픽XYZ"]})
    out = chatbot.recommend_topics("관심사 아무거나", catalog)
    assert real in out
    assert "존재하지않는가짜토픽XYZ" not in out


def test_recommend_topics_fallback_without_llm(monkeypatch):
    """키 없음(use_llm False)이면 대표 토픽 상위 N으로 폴백."""
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    catalog = _svc().catalog()
    out = chatbot.recommend_topics("아무거나", catalog)
    assert out == [t.name for t in catalog][:5]


def test_list_topics_extended(monkeypatch):
    """목록 조회 = 현재 구독 + 총 개수(구독 가능) + 추천."""
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")   # 추천은 폴백(대표 토픽)
    s = _svc()
    topic = s.catalog()[0]
    s.add("discord", "u1", topic.topic_id, "123")
    r = chatbot.handle(s, "discord", "u1", "내 토픽 목록")
    assert r["intent"] == "list_topics" and r["status"] == "completed"
    assert topic.name in r["reply"]          # 현재 구독 표시
    assert "총" in r["reply"]                 # 전체 개수(요약)
    assert "구독 가능" in r["reply"]


def test_welcome_text_has_examples():
    """온보딩 문구에 사용 예시가 포함."""
    w = chatbot.welcome_text(_svc())
    assert "구독" in w and "멘션" in w and "총" in w


def test_add_topic_ambiguous_recommends(monkeypatch):
    """add 의도인데 토픽 매칭 실패 시 추천을 제시(blocked)."""
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    r = chatbot.handle(_svc(), "discord", "u9", "뭔가 구독하고 싶어")
    assert r["intent"] == "add_topic" and r["status"] == "blocked"
    assert "토픽" in r["reply"]

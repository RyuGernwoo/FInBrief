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
    """목록 조회 = 현재 구독 표 + 전체 구독 가능 토픽 표."""
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    s = _svc()
    catalog = s.catalog()
    topic = catalog[0]
    nasdaq = next(t for t in catalog if t.normalized_name == "nasdaq")
    s.add("discord", "u1", topic.topic_id, "123")
    s.add("discord", "u1", nasdaq.topic_id, "123")
    r = chatbot.handle(s, "discord", "u1", "내 토픽 목록")
    assert r["intent"] == "list_topics" and r["status"] == "completed"
    assert topic.name in r["reply"]          # 현재 구독 표시
    assert nasdaq.name in r["reply"]
    assert "총" in r["reply"]                 # 전체 개수(요약)
    assert "구독 가능" in r["reply"]
    assert "| 번호 | 현재 구독 토픽 | 유형 |" in r["reply"]
    assert "| 유형 | 구독 가능 토픽 |" in r["reply"]
    assert "💡" not in r["reply"]
    assert "추천" not in r["reply"]


def test_welcome_text_has_examples():
    """온보딩 문구에 사용 예시가 포함."""
    w = chatbot.welcome_text(_svc())
    assert "브리핑 메이트" in w and "구독" in w and "멘션" in w and "총" in w
    assert "!" in w and ("🚀" in w or "✨" in w)


def test_add_topic_ambiguous_recommends(monkeypatch):
    """add 의도인데 토픽 매칭 실패 시 추천을 제시(blocked)."""
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    r = chatbot.handle(_svc(), "discord", "u9", "뭔가 구독하고 싶어")
    assert r["intent"] == "add_topic" and r["status"] == "blocked"
    assert "토픽" in r["reply"]


def test_delete_ambiguous_resolves_to_subscription(monkeypatch):
    """'환율 제거' 모호어 → 구독 중인 USD/KRW 하나로 해결해 제거."""
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    s = _svc()
    cat = s.catalog()
    usdkrw = next(t for t in cat if t.normalized_name == "usdkrw")
    s.add("discord", "del_u1", usdkrw.topic_id, "c")
    r = chatbot.handle(s, "discord", "del_u1", "환율 제거해", "c")
    assert r["intent"] == "delete_topic" and r["status"] == "completed"
    assert len(s.list("discord", "del_u1")) == 0


def test_delete_not_subscribed_blocked(monkeypatch):
    """구독하지 않은 토픽 제거 시도 → 현재 구독 안내(blocked)."""
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    s = _svc()
    r = chatbot.handle(s, "discord", "del_u2", "비트코인 제거", "c")
    assert r["intent"] == "delete_topic" and r["status"] == "blocked"
    assert "구독 목록에 없" in r["reply"]

import json
from app.agents import nodes
from app.agents.card_schema import CardContent


def test_analyze_llm_path(monkeypatch):
    import litellm

    class _R:
        class _C:
            class _M:
                content = json.dumps({"headline": "나스닥 사흘째 상승세 지속 랠리",
                                      "lead": "AI 기대 기술주 강세", "body": "본문 내용", "source": "예시통신"})
            message = _M()
        choices = [_C()]

    monkeypatch.setattr(litellm, "completion", lambda **kw: _R())
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-key")
    monkeypatch.delenv("FINBRIEF_LLM_STUB", raising=False)

    out = nodes._analyze({"topic_id": "nasdaq", "name": "나스닥", "category": "MARKET"},
                         {"value": 18120.3, "change_pct": 0.78, "unit": "pt"},
                         [{"title": "t", "snippet": "s"}])
    CardContent(**out)                 # 재검증
    assert len(out["headline"]) <= 14  # 클립 확인

from datetime import date
from app.agents.graph import graph


def test_pipeline_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")     # 오프라인 강제
    monkeypatch.setenv("FINBRIEF_OUT", str(tmp_path))  # 렌더 산출물 임시경로
    final = graph.invoke({"run_id": "t", "run_date": date.today().isoformat(),
                          "status": "queued", "cards": [], "deliveries": [], "errors": []})
    assert final["status"] == "completed"
    assert len(final["cards"]) == 3
    assert len(final["deliveries"]) == 4
    for c in final["cards"]:
        assert (tmp_path / f"{final['run_date']}_{c['topic_id']}.png").exists()

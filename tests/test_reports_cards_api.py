from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.api.dependencies import reset_repository_bundle_cache
from app.core.config import Settings
from app.main import create_app


def _client(monkeypatch, tmp_path) -> TestClient:
    reset_repository_bundle_cache()
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    monkeypatch.setenv("FINBRIEF_IMAGE_STUB", "1")
    monkeypatch.setenv("FINBRIEF_OUT", str(tmp_path / "cards"))
    monkeypatch.setenv("FINBRIEF_IMG_OUT", str(tmp_path / "images"))
    monkeypatch.setenv("FINBRIEF_REPORT_OUT", str(tmp_path / "reports"))
    return TestClient(create_app(Settings(app_env="test", enable_mock_data=True)))


def test_run_report_endpoint_generates_cards_for_subscriptions(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    user_id = "report_user_run"
    client.post(
        f"/api/v1/subscriptions/{user_id}/topics",
        json={"topic_id": "topic_btc", "channel": "discord"},
    )

    response = client.post(
        "/api/v1/reports/run",
        json={"run_date": "2026-07-10", "dry_run": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["generated_cards"] == 1
    assert payload["reused_cards"] == 0
    assert payload["delivery_results"] == 1
    assert payload["trace_id"].startswith("local_mock_trace_")
    assert "투자 조언이 아닌" in payload["disclaimer"]
    assert payload["report_url"]
    report_path = Path(payload["report_url"])
    assert report_path.exists()
    with Image.open(report_path) as image:
        assert image.format == "PNG"
        assert image.size == (1080, 1080)


def test_cards_today_returns_user_subscription_cards(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    user_id = "report_user_cards"
    client.post(
        f"/api/v1/subscriptions/{user_id}/topics",
        json={"topic_id": "topic_nasdaq", "channel": "discord"},
    )
    client.post("/api/v1/reports/run", json={"run_date": "2026-07-10", "dry_run": True})

    response = client.get(
        "/api/v1/cards/today",
        params={"user_id": user_id, "run_date": "2026-07-10"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == user_id
    assert payload["run_date"] == "2026-07-10"
    assert [item["topic_id"] for item in payload["cards"]] == ["topic_nasdaq"]
    assert "투자 조언이 아닌" in payload["cards"][0]["disclaimer"]


def test_reports_today_returns_latest_mock_report(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    client.post(
        "/api/v1/subscriptions/report_user_today/topics",
        json={"topic_id": "topic_semi", "channel": "discord"},
    )
    client.post("/api/v1/reports/run", json={"run_date": "2026-07-10", "dry_run": True})

    response = client.get("/api/v1/reports/today", params={"run_date": "2026-07-10"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_date"] == "2026-07-10"
    assert payload["status"] == "completed"
    assert payload["generated_cards"] == 1
    assert "투자 조언이 아닌" in payload["disclaimer"]
    assert payload["report_url"]

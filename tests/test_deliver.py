from datetime import date
from app.services import notifier
from app.agents.graph import graph


def test_deliver_dry_run(monkeypatch):
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    monkeypatch.setenv("FINBRIEF_IMAGE_STUB", "1")
    monkeypatch.setenv("DELIVERY_DRY_RUN", "true")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://x/discord")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://x/slack")
    final = graph.invoke({"run_id": "t", "run_date": date.today().isoformat(),
                          "status": "queued", "cards": [], "deliveries": [], "errors": []})
    assert final["deliveries"] and all(d["status"] == "dry_run" for d in final["deliveries"])


def test_deliver_sent_mock(monkeypatch):
    monkeypatch.setenv("FINBRIEF_LLM_STUB", "1")
    monkeypatch.setenv("FINBRIEF_IMAGE_STUB", "1")
    monkeypatch.setattr(notifier, "_post_discord", lambda u, t, p: None)
    monkeypatch.setattr(notifier, "_post_slack", lambda u, t, p: None)
    monkeypatch.setenv("DELIVERY_DRY_RUN", "false")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://x/discord")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://x/slack")
    final = graph.invoke({"run_id": "t", "run_date": date.today().isoformat(),
                          "status": "queued", "cards": [], "deliveries": [], "errors": []})
    assert all(d["status"] == "sent" for d in final["deliveries"])

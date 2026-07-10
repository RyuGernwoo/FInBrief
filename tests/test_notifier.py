from app.services import notifier


def test_dry_run_default(monkeypatch):
    monkeypatch.delenv("DELIVERY_DRY_RUN", raising=False)
    assert notifier.dry_run() is True
    res = notifier.send_card(channel="discord", webhook_url="https://x/hook", text="t")
    assert res["status"] == "dry_run"


def test_skipped_without_webhook(monkeypatch):
    monkeypatch.setenv("DELIVERY_DRY_RUN", "false")
    assert notifier.send_card(channel="discord", webhook_url="", text="t")["status"] == "skipped"


def test_sent_mock(monkeypatch):
    calls = []
    monkeypatch.setattr(notifier, "_post_discord", lambda u, t, p: calls.append(u))
    monkeypatch.setenv("DELIVERY_DRY_RUN", "false")
    res = notifier.send_card(channel="discord", webhook_url="https://x/hook", text="t")
    assert res["status"] == "sent" and len(calls) == 1


def test_format_card_text():
    txt = notifier.format_card_text({"category": "MARKET", "headline": "나스닥 상승",
                                     "lead": "L", "body": "B", "source": "S", "disclaimer": "D"})
    assert "나스닥 상승" in txt and "MARKET" in txt

"""deliver 라우팅: discord_channel_id 있으면 봇 전송, 없으면 skip(웹훅 제거됨)."""
from app.agents import nodes
from app.services import notifier


def _card(topic_id):
    return {"topic_id": topic_id, "category": "MARKET", "headline": "h", "lead": "l",
            "body": "b", "source": "s", "disclaimer": "d", "image_path": None}


def test_deliver_routes_to_bot_when_channel_id(monkeypatch):
    monkeypatch.setenv("DELIVERY_DRY_RUN", "false")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    bot_calls = []
    monkeypatch.setattr(notifier, "send_via_bot",
                        lambda **k: bot_calls.append(k) or {"status": "sent"})

    state = {
        "cards": [_card("nasdaq")],
        "subscriptions": [{"user_id": "u1", "topic_id": "nasdaq", "channel": "discord",
                           "discord_channel_id": "999"}],
    }
    out = nodes.deliver(state)
    assert len(bot_calls) == 1 and bot_calls[0]["channel_id"] == "999"
    assert out["deliveries"][0]["status"] == "sent"


def test_deliver_skips_without_channel_id(monkeypatch):
    monkeypatch.setenv("DELIVERY_DRY_RUN", "false")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    bot_calls = []
    monkeypatch.setattr(notifier, "send_via_bot",
                        lambda **k: bot_calls.append(k) or {"status": "sent"})

    state = {
        "cards": [_card("nasdaq")],
        "subscriptions": [{"user_id": "u1", "topic_id": "nasdaq", "channel": "discord"}],
    }
    out = nodes.deliver(state)
    # 채널ID 없으면 봇 호출 없이 skip (웹훅 폴백 없음)
    assert bot_calls == []
    assert all(d["status"] == "skipped" for d in out["deliveries"])


def test_deliver_consolidates_all_cards_to_recent_channel(monkeypatch):
    # 계정 단위: 한 사용자가 여러 채널에서 구독해도 '가장 최근 구독 채널' 하나로 모아 발송.
    monkeypatch.setenv("DELIVERY_DRY_RUN", "false")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    sent = []
    monkeypatch.setattr(notifier, "send_via_bot",
                        lambda **k: sent.append(k["channel_id"]) or {"status": "sent"})
    RECENT, OLD = "chA", "chB"
    state = {
        "cards": [_card("ai"), _card("usdkrw"), _card("nasdaq")],
        "subscriptions": [
            {"user_id": "u1", "topic_id": "usdkrw", "channel": "discord",
             "discord_channel_id": OLD, "created_at": "2026-07-13T06:39:00"},
            {"user_id": "u1", "topic_id": "nasdaq", "channel": "discord",
             "discord_channel_id": OLD, "created_at": "2026-07-13T06:41:00"},
            {"user_id": "u1", "topic_id": "ai", "channel": "discord",
             "discord_channel_id": RECENT, "created_at": "2026-07-14T03:28:00"},
        ],
    }
    out = nodes.deliver(state)
    # 3장 모두 최근 채널(chA)로 — 예전처럼 채널별로 흩어지지 않음
    assert set(sent) == {RECENT} and len(sent) == 3
    assert all(d["channel_id"] == RECENT for d in out["deliveries"])


def test_deliver_falls_back_when_recent_channel_dead(monkeypatch):
    # 최근 채널이 죽었으면(404) 다음 후보 채널로 폴백해 전체를 그 채널로 보낸다.
    monkeypatch.setenv("DELIVERY_DRY_RUN", "false")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    DEAD, ALIVE = "dead", "alive"
    monkeypatch.setattr(notifier, "send_via_bot",
                        lambda **k: {"status": "failed", "error": "404"} if k["channel_id"] == DEAD
                        else {"status": "sent"})
    state = {
        "cards": [_card("ai"), _card("nasdaq")],
        "subscriptions": [
            {"user_id": "u1", "topic_id": "nasdaq", "channel": "discord",
             "discord_channel_id": ALIVE, "created_at": "2026-07-13T00:00:00"},
            {"user_id": "u1", "topic_id": "ai", "channel": "discord",
             "discord_channel_id": DEAD, "created_at": "2026-07-14T00:00:00"},  # 최근이지만 죽음
        ],
    }
    out = nodes.deliver(state)
    # 최근(DEAD) 실패 → ALIVE 로 폴백, 최종적으로 두 카드 모두 sent
    assert all(d["status"] == "sent" and d["channel_id"] == ALIVE for d in out["deliveries"])
    assert "errors" not in out

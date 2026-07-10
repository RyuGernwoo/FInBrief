import pytest
from app.services.subscription_service import SubscriptionService, TopicNotAllowed, MaxTopicsExceeded
from app.services._repo_stub import StubTopics, StubUsers, StubSubs

CATALOG = [{"topic_id": t, "name": t} for t in ("usdkrw", "us_rate", "nasdaq", "btc", "semi")]


def _svc(mx=5):
    return SubscriptionService(StubUsers(mx), StubSubs(), StubTopics(CATALOG))


def test_whitelist():
    with pytest.raises(TopicNotAllowed):
        _svc().add("discord", "u1", "gold")


def test_max_topics():
    s = _svc(2); s.add("discord", "u1", "nasdaq"); s.add("discord", "u1", "btc")
    with pytest.raises(MaxTopicsExceeded):
        s.add("discord", "u1", "semi")


def test_crud():
    s = _svc()
    assert s.add("discord", "u1", "nasdaq") == ["nasdaq"]
    assert s.add("discord", "u1", "nasdaq") == ["nasdaq"]      # idempotent
    assert s.remove("discord", "u1", "nasdaq") == []

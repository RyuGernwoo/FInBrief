"""SubscriptionService — 구독/토픽 CRUD + MVP 화이트리스트 + max_topics.
   비즈니스 로직은 여기 집중(레이어 규율). LLM/봇 아님."""
from __future__ import annotations


class TopicNotAllowed(Exception):
    pass


class MaxTopicsExceeded(Exception):
    pass


class SubscriptionService:
    def __init__(self, users, subs, topics):
        self.users, self.subs, self.topics = users, subs, topics

    def catalog(self):
        return self.topics.list_catalog()

    def _allowed(self) -> set[str]:
        return {t["topic_id"] for t in self.topics.list_catalog()}

    def add(self, channel, ext_user_id, topic_id):
        if topic_id not in self._allowed():
            raise TopicNotAllowed(topic_id)
        u = self.users.get_or_create(channel, ext_user_id)
        cur = self.subs.list(u["id"])
        if topic_id in cur:
            return cur
        if len(cur) >= u["max_topics"]:
            raise MaxTopicsExceeded(u["max_topics"])
        self.subs.add(u["id"], topic_id, channel)
        return self.subs.list(u["id"])

    def remove(self, channel, ext_user_id, topic_id):
        u = self.users.get_or_create(channel, ext_user_id)
        self.subs.remove(u["id"], topic_id)
        return self.subs.list(u["id"])

    def list(self, channel, ext_user_id):
        u = self.users.get_or_create(channel, ext_user_id)
        return self.subs.list(u["id"])

    def tier(self, channel, ext_user_id):
        u = self.users.get_or_create(channel, ext_user_id)
        return {"tier": u.get("tier", "free"), "max_topics": u["max_topics"], "used": len(self.subs.list(u["id"]))}

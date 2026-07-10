"""In-memory repository stub — 팀원 repositories 전 개발/검증용.
   실제는 UsersRepository/SubscriptionRepository/TopicRepository(Supabase)로 교체."""
from __future__ import annotations


class StubTopics:
    def __init__(self, catalog): self._c = catalog
    def list_catalog(self): return list(self._c)


class StubUsers:
    def __init__(self, max_topics=5): self._u = {}; self._max = max_topics
    def get_or_create(self, channel, external_user_id):
        key = (channel, external_user_id)
        if key not in self._u:
            self._u[key] = {"id": f"{channel}:{external_user_id}", "tier": "free", "max_topics": self._max}
        return self._u[key]


class StubSubs:
    def __init__(self): self._s = {}
    def list(self, user_id): return sorted(self._s.get(user_id, set()))
    def add(self, user_id, topic_id, channel): self._s.setdefault(user_id, set()).add(topic_id)
    def remove(self, user_id, topic_id): self._s.get(user_id, set()).discard(topic_id)

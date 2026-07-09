"""In-memory repositories for local MVP development and tests."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.core.schemas import (
    CardArtifact,
    NewsDocument,
    NewsEvidence,
    Subscription,
    Topic,
    UserProfile,
)
from app.repositories.protocols import (
    RepositoryBundle,
    RepositoryNotFoundError,
    TopicLimitExceededError,
)


DEFAULT_TOPICS_PATH = Path("data/default_topics.json")


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _topic_keywords(topic: Topic) -> set[str]:
    keywords: set[str] = set()
    for mapping in topic.source_mapping:
        keywords.update(item.casefold() for item in mapping.news_keywords)
        if mapping.query:
            keywords.add(mapping.query.casefold())
    return keywords


class MemoryTopicRepository:
    def __init__(self, topics: list[Topic]) -> None:
        self._topics_by_id = {topic.topic_id: topic for topic in topics}
        self._topics_by_name = {topic.normalized_name: topic for topic in topics}

    def list_catalog(self) -> list[Topic]:
        return list(self._topics_by_id.values())

    def get(self, topic_id: str) -> Topic:
        try:
            return self._topics_by_id[topic_id]
        except KeyError as exc:
            raise RepositoryNotFoundError(f"Topic not found: {topic_id}") from exc

    def get_by_normalized_name(self, normalized_name: str) -> Topic | None:
        return self._topics_by_name.get(normalized_name)


class MemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, UserProfile] = {}

    def get_or_create(self, channel: str, external_user_id: str) -> UserProfile:
        if external_user_id not in self._users:
            self._users[external_user_id] = UserProfile(user_id=external_user_id)
        return self._users[external_user_id]

    def get(self, user_id: str) -> UserProfile:
        try:
            return self._users[user_id]
        except KeyError as exc:
            raise RepositoryNotFoundError(f"User not found: {user_id}") from exc


class MemorySubscriptionRepository:
    def __init__(self, users: MemoryUserRepository, topics: MemoryTopicRepository) -> None:
        self._users = users
        self._topics = topics
        self._subscriptions: dict[tuple[str, str, str], Subscription] = {}

    def list_active(self) -> list[Subscription]:
        return [item for item in self._subscriptions.values() if item.active]

    def list_by_user(self, user_id: str) -> list[Subscription]:
        return [
            item
            for item in self._subscriptions.values()
            if item.user_id == user_id and item.active
        ]

    def add(self, user_id: str, topic_id: str, channel: str) -> Subscription:
        user = self._users.get(user_id)
        active_topic_ids = {item.topic_id for item in self.list_by_user(user_id)}
        key = (user_id, topic_id, channel)

        if key in self._subscriptions and self._subscriptions[key].active:
            return self._subscriptions[key]

        if topic_id not in active_topic_ids and len(active_topic_ids) >= user.max_topics:
            raise TopicLimitExceededError(
                f"free tier는 최대 {user.max_topics}개 토픽까지 구독할 수 있습니다."
            )

        self._topics.get(topic_id)
        subscription = Subscription(
            subscription_id=f"sub_{len(self._subscriptions) + 1:03d}",
            user_id=user_id,
            topic_id=topic_id,
            channel=channel,
            active=True,
        )
        self._subscriptions[key] = subscription
        return subscription

    def remove(self, user_id: str, topic_id: str) -> bool:
        removed = False
        for key, subscription in list(self._subscriptions.items()):
            key_user_id, key_topic_id, _ = key
            if key_user_id == user_id and key_topic_id == topic_id and subscription.active:
                self._subscriptions[key] = subscription.model_copy(update={"active": False})
                removed = True
        return removed


class MemoryCardRepository:
    def __init__(self) -> None:
        self._cards: dict[tuple[str, date], CardArtifact] = {}

    def get(self, topic_id: str, run_date: date) -> CardArtifact | None:
        return self._cards.get((topic_id, run_date))

    def upsert(self, card: CardArtifact) -> None:
        self._cards[(card.topic_id, card.run_date)] = card


class MemoryNewsRepository:
    def __init__(self, news_documents: list[NewsDocument] | None = None) -> None:
        self._news_documents = news_documents or []

    def match(self, topic: Topic, since: datetime, k: int) -> list[NewsEvidence]:
        since_utc = _as_aware_utc(since)
        keywords = _topic_keywords(topic)
        matches: list[tuple[float, datetime, NewsDocument]] = []

        for document in self._news_documents:
            published_at = _as_aware_utc(document.published_at)
            if published_at < since_utc:
                continue

            tags = {tag.casefold() for tag in document.tags}
            if keywords and not tags.intersection(keywords):
                continue

            similarity = 1.0 if tags.intersection(keywords) else 0.5
            matches.append((similarity, published_at, document))

        matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [
            NewsEvidence(
                news_id=document.news_id,
                title=document.title,
                source=document.source,
                url=document.url,
                similarity=similarity,
                snippet=document.summary or document.title,
            )
            for similarity, _, document in matches[:k]
        ]


def load_default_topics(path: Path = DEFAULT_TOPICS_PATH) -> list[Topic]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Topic.model_validate(item) for item in payload]


def create_memory_repositories(
    *,
    topics_path: Path = DEFAULT_TOPICS_PATH,
    news_documents: list[NewsDocument] | None = None,
) -> RepositoryBundle:
    topics = MemoryTopicRepository(load_default_topics(topics_path))
    users = MemoryUserRepository()
    return RepositoryBundle(
        users=users,
        topics=topics,
        subscriptions=MemorySubscriptionRepository(users, topics),
        cards=MemoryCardRepository(),
        news=MemoryNewsRepository(news_documents),
    )

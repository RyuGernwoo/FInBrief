"""Repository contracts shared by API routes and agent nodes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.core.schemas import CardArtifact, NewsEvidence, Subscription, Topic, UserProfile


class RepositoryError(RuntimeError):
    """Base class for repository-layer errors with stable API codes."""

    code = "REPOSITORY_ERROR"


class RepositoryNotFoundError(RepositoryError):
    """Raised when a requested row-like domain object does not exist."""

    code = "NOT_FOUND"


class TopicLimitExceededError(RepositoryError):
    """Raised when a free-tier user exceeds the allowed active topic count."""

    code = "TOPIC_LIMIT_EXCEEDED"


class TopicRepository(Protocol):
    def list_catalog(self) -> list[Topic]: ...

    def get(self, topic_id: str) -> Topic: ...

    def get_by_normalized_name(self, normalized_name: str) -> Topic | None: ...


class SubscriptionRepository(Protocol):
    def list_active(self) -> list[Subscription]: ...

    def list_by_user(self, user_id: str) -> list[Subscription]: ...

    def add(self, user_id: str, topic_id: str, channel: str) -> Subscription: ...

    def remove(self, user_id: str, topic_id: str) -> bool: ...


class UserRepository(Protocol):
    def get_or_create(self, channel: str, external_user_id: str) -> UserProfile: ...


class CardRepository(Protocol):
    def get(self, topic_id: str, run_date: date) -> CardArtifact | None: ...

    def upsert(self, card: CardArtifact) -> None: ...


class NewsRepository(Protocol):
    def match(self, topic: Topic, since: datetime, k: int) -> list[NewsEvidence]: ...


@dataclass(slots=True)
class RepositoryBundle:
    users: UserRepository
    topics: TopicRepository
    subscriptions: SubscriptionRepository
    cards: CardRepository
    news: NewsRepository

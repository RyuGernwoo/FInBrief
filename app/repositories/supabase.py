"""Supabase repository adapters.

The adapters keep Supabase details behind the same contracts used by the
in-memory repositories. They create no network connection at import time.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.core.schemas import (
    CardArtifact,
    IndicatorValue,
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
from app.repositories.supabase_client import SupabaseSettingsError, create_supabase_client


QueryEmbeddingProvider = Callable[[Topic], Sequence[float]]


def _response_data(response: Any) -> Any:
    return getattr(response, "data", response)


def _require_one(data: Any, label: str) -> dict[str, Any]:
    if isinstance(data, list) and data:
        return data[0]
    raise RepositoryNotFoundError(f"{label} not found")


def _topic_from_row(row: dict[str, Any]) -> Topic:
    return Topic.model_validate(
        {
            "topic_id": str(row["id"]),
            "name": row["name"],
            "normalized_name": row["normalized_name"],
            "type": row["type"],
            "source_mapping": row.get("source_mapping") or [],
            "created_at": row.get("created_at"),
        }
    )


def _subscription_from_row(row: dict[str, Any]) -> Subscription:
    return Subscription.model_validate(
        {
            "subscription_id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "topic_id": str(row["topic_id"]),
            "channel": row["channel"],
            "active": row.get("active", True),
            "discord_channel_id": row.get("discord_channel_id"),
            "created_at": row.get("created_at"),
        }
    )


def _user_from_row(row: dict[str, Any]) -> UserProfile:
    return UserProfile.model_validate(
        {
            "user_id": str(row["id"]),
            "display_name": row.get("display_name"),
            "tier": row.get("tier", "free"),
            "max_topics": row.get("max_topics", 5),
            "created_at": row.get("created_at"),
        }
    )


def map_news_match_result(row: dict[str, Any]) -> NewsEvidence:
    return NewsEvidence(
        news_id=str(row["news_id"]),
        title=row["title"],
        source=row["source"],
        url=row["url"],
        similarity=row.get("similarity"),
        snippet=row.get("summary") or row["title"],
    )


def _topic_tags(topic: Topic) -> list[str]:
    tags: list[str] = []
    for mapping in topic.source_mapping:
        tags.extend(mapping.news_keywords)
    return sorted(set(tags))


def build_indicator_row(
    *,
    indicator_id: str,
    name: str,
    source: str,
    value_date: str,
    current_value: float,
    previous_value: float | None = None,
    change_value: float | None = None,
    change_percent: float | None = None,
    unit: str | None = None,
    missing: bool = False,
    raw_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if previous_value not in (None, 0) and change_value is None:
        change_value = current_value - previous_value
    if previous_value not in (None, 0) and change_percent is None:
        change_percent = (current_value - previous_value) / previous_value * 100
    return {
        "indicator_id": indicator_id,
        "name": name,
        "source": source,
        "value_date": value_date,
        "current_value": current_value,
        "previous_value": previous_value,
        "change_value": change_value,
        "change_percent": change_percent,
        "unit": unit,
        "missing": missing,
        "raw_payload": raw_payload or {},
    }


def indicator_value_to_row(value: IndicatorValue) -> dict[str, Any]:
    return build_indicator_row(
        indicator_id=value.indicator_id,
        name=value.name,
        source=value.source,
        value_date=value.value_date.isoformat(),
        current_value=value.current_value,
        previous_value=value.previous_value,
        change_value=value.change_value,
        change_percent=value.change_percent,
        unit=value.unit,
        missing=value.missing,
    )


def build_news_document_row(document: NewsDocument) -> dict[str, Any]:
    return {
        "source": document.source,
        "title": document.title,
        "url": str(document.url),
        "published_at": document.published_at.isoformat(),
        "summary": document.summary,
        "tags": document.tags,
        "raw_payload": {"news_id": document.news_id},
    }


class SupabaseTopicRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def list_catalog(self) -> list[Topic]:
        response = self._client.table("topics").select("*").execute()
        return [_topic_from_row(row) for row in _response_data(response)]

    def get(self, topic_id: str) -> Topic:
        response = self._client.table("topics").select("*").eq("id", topic_id).execute()
        return _topic_from_row(_require_one(_response_data(response), "Topic"))

    def get_by_normalized_name(self, normalized_name: str) -> Topic | None:
        response = (
            self._client.table("topics")
            .select("*")
            .eq("normalized_name", normalized_name)
            .execute()
        )
        data = _response_data(response)
        if not data:
            return None
        return _topic_from_row(data[0])


class SupabaseUserRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def get_or_create(self, channel: str, external_user_id: str) -> UserProfile:
        response = (
            self._client.table("users")
            .select("*")
            .eq("external_user_id", external_user_id)
            .execute()
        )
        data = _response_data(response)
        if data:
            return _user_from_row(data[0])

        insert_response = (
            self._client.table("users")
            .insert({"external_user_id": external_user_id})
            .execute()
        )
        return _user_from_row(_require_one(_response_data(insert_response), "User"))


class SupabaseSubscriptionRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def list_active(self) -> list[Subscription]:
        response = self._client.table("subscriptions").select("*").eq("active", True).execute()
        return [_subscription_from_row(row) for row in _response_data(response)]

    def list_by_user(self, user_id: str) -> list[Subscription]:
        response = (
            self._client.table("subscriptions")
            .select("*")
            .eq("user_id", user_id)
            .eq("active", True)
            .execute()
        )
        return [_subscription_from_row(row) for row in _response_data(response)]

    def add(self, user_id: str, topic_id: str, channel: str,
            channel_id: str | None = None) -> Subscription:
        active = self.list_by_user(user_id)
        active_topic_ids = {item.topic_id for item in active}
        user_response = self._client.table("users").select("*").eq("id", user_id).execute()
        user = _user_from_row(_require_one(_response_data(user_response), "User"))

        if topic_id not in active_topic_ids and len(active_topic_ids) >= user.max_topics:
            raise TopicLimitExceededError(
                f"free tier는 최대 {user.max_topics}개 토픽까지 구독할 수 있습니다."
            )

        response = (
            self._client.table("subscriptions")
            .upsert(
                {
                    "user_id": user_id,
                    "topic_id": topic_id,
                    "channel": channel,
                    "active": True,
                    "discord_channel_id": channel_id,
                },
                on_conflict="user_id,topic_id,channel",
            )
            .execute()
        )
        return _subscription_from_row(_require_one(_response_data(response), "Subscription"))

    def remove(self, user_id: str, topic_id: str) -> bool:
        response = (
            self._client.table("subscriptions")
            .update({"active": False})
            .eq("user_id", user_id)
            .eq("topic_id", topic_id)
            .eq("active", True)
            .execute()
        )
        return bool(_response_data(response))


class SupabaseCardRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, topic_id: str, run_date: date) -> CardArtifact | None:
        response = (
            self._client.table("cards")
            .select("*")
            .eq("topic_id", topic_id)
            .eq("run_date", run_date.isoformat())
            .execute()
        )
        data = _response_data(response)
        if not data:
            return None
        row = data[0]
        return CardArtifact.model_validate(
            {
                "card_id": str(row["id"]),
                "topic_id": str(row["topic_id"]),
                "run_date": row["run_date"],
                "title": row["title"],
                "image_url": row.get("image_url"),
                "report_url": row.get("report_url"),
                "analysis": row["analysis"],
                "created_at": row.get("created_at"),
            }
        )

    def upsert(self, card: CardArtifact) -> None:
        # id 는 DB 소유(uuid default gen_random_uuid()). 파이프라인의 card_id 는
        # "card_<topic>_<date>" 문자열이라 UUID 컬럼에 넣으면 22P02 로 실패한다.
        # 자연키 (topic_id, run_date) 로 upsert 하고 id 는 보내지 않는다(insert 시
        # DB 가 생성, conflict 시 기존 id 유지). get() 이 실제 UUID 를 되돌려준다.
        self._client.table("cards").upsert(
            {
                "topic_id": card.topic_id,
                "run_date": card.run_date.isoformat(),
                "title": card.title,
                "analysis": card.analysis.model_dump(mode="json"),
                "image_url": card.image_url,
                "report_url": card.report_url,
                "disclaimer": card.analysis.disclaimer,
            },
            on_conflict="topic_id,run_date",
        ).execute()


class SupabaseIngestionRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def upsert_indicator_values(self, values: Sequence[IndicatorValue]) -> Any:
        payload = [indicator_value_to_row(value) for value in values]
        if not payload:
            return []
        response = self._client.table("indicator_values").upsert(
            payload,
            on_conflict="indicator_id,value_date,source",
        ).execute()
        return _response_data(response)

    def upsert_news_documents(self, documents: Sequence[NewsDocument]) -> Any:
        payload = [build_news_document_row(document) for document in documents]
        if not payload:
            return []
        response = self._client.table("news_documents").upsert(
            payload,
            on_conflict="url",
        ).execute()
        return _response_data(response)

    def upsert_news_embeddings(self, embeddings: Sequence[dict[str, Any]]) -> Any:
        payload: list[dict[str, Any]] = []
        for row in embeddings:
            embedding = [float(value) for value in row["embedding"]]
            if len(embedding) != 4096:
                raise ValueError(f"embedding dimension must be 4096, got {len(embedding)}")
            payload.append(
                {
                    "news_id": row["news_id"],
                    "embedding": embedding,
                    "embedding_model": row["embedding_model"],
                    "embedding_kind": row.get("embedding_kind", "passage"),
                }
            )
        if not payload:
            return []
        response = self._client.table("news_embeddings").upsert(
            payload,
            on_conflict="news_id,embedding_model,embedding_kind",
        ).execute()
        return _response_data(response)

    def existing_passage_news_ids(self, news_ids: Sequence[str]) -> set[str]:
        """이미 passage 임베딩이 있는 news_id 집합. 재임베딩 스킵용."""
        ids = [str(n) for n in news_ids if n]
        if not ids:
            return set()
        found: set[str] = set()
        for i in range(0, len(ids), 200):   # in_ 필터 배치
            chunk = ids[i:i + 200]
            resp = (
                self._client.table("news_embeddings")
                .select("news_id")
                .eq("embedding_kind", "passage")
                .in_("news_id", chunk)
                .execute()
            )
            found.update(str(row["news_id"]) for row in _response_data(resp))
        return found


class SupabaseNewsRepository:
    def __init__(
        self,
        client: Any,
        query_embedding_provider: QueryEmbeddingProvider | None = None,
    ) -> None:
        self._client = client
        self._query_embedding_provider = query_embedding_provider

    def match(self, topic: Topic, since: datetime, k: int) -> list[NewsEvidence]:
        if self._query_embedding_provider is None:
            raise SupabaseSettingsError("query embedding provider is required for news.match")

        response = self._client.rpc(
            "match_news",
            {
                "query_embedding": list(self._query_embedding_provider(topic)),
                "topic_tags": _topic_tags(topic),  # 하드필터 아님(soft boost 여지용, 현재 RPC는 미사용)
                "since": since.isoformat(),
                "match_count": k,  # 이제 후보 폭(RAG_CANDIDATES) — 최종 컷은 rag.postprocess_evidence
            },
        ).execute()
        return [map_news_match_result(row) for row in _response_data(response)]


@dataclass(slots=True)
class SupabaseRepositories(RepositoryBundle):
    pass


def create_supabase_repositories(
    *,
    client: Any | None = None,
    query_embedding_provider: QueryEmbeddingProvider | None = None,
) -> RepositoryBundle:
    runtime_client = client or create_supabase_client()
    return RepositoryBundle(
        users=SupabaseUserRepository(runtime_client),
        topics=SupabaseTopicRepository(runtime_client),
        subscriptions=SupabaseSubscriptionRepository(runtime_client),
        cards=SupabaseCardRepository(runtime_client),
        news=SupabaseNewsRepository(runtime_client, query_embedding_provider),
    )

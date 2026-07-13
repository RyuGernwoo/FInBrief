"""RAG evidence post-processing shared by memory/supabase news retrieval.

`repositories.news.match()` (both backends) returns raw `NewsEvidence`. This
module applies the retrieval policy from the plan: a `since` window, a minimum
similarity threshold, per-source diversity, and a top-k cap. Keeping it as a
pure helper means memory and Supabase runs behave identically.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app.core.schemas import NewsEvidence


RAG_SINCE_DAYS = 3
RAG_K = 5
RAG_CANDIDATES = 40   # match_news 에서 넓게 받아오고, postprocess 가 RAG_K 로 컷
RAG_MIN_SIMILARITY = 0.2
RAG_MAX_PER_SOURCE = 2


def since_for(run_date: date, *, days: int = RAG_SINCE_DAYS) -> datetime:
    """Return the UTC lower bound for news retrieval given a run date."""

    base = datetime.combine(run_date, time.min, tzinfo=timezone.utc)
    return base - timedelta(days=days)


def postprocess_evidence(
    evidence: list[NewsEvidence],
    *,
    min_similarity: float = RAG_MIN_SIMILARITY,
    max_per_source: int = RAG_MAX_PER_SOURCE,
    k: int = RAG_K,
) -> list[NewsEvidence]:
    """Filter and diversify RAG evidence.

    - drop items whose similarity is known and below ``min_similarity``
      (``None`` similarity is treated as passing so keyword-only backends survive),
    - keep at most ``max_per_source`` items per source,
    - order by similarity descending and cap at ``k``.
    """

    ordered = sorted(
        evidence,
        key=lambda item: item.similarity if item.similarity is not None else 0.0,
        reverse=True,
    )

    kept: list[NewsEvidence] = []
    per_source: dict[str, int] = {}
    for item in ordered:
        if item.similarity is not None and item.similarity < min_similarity:
            continue
        used = per_source.get(item.source, 0)
        if used >= max_per_source:
            continue
        per_source[item.source] = used + 1
        kept.append(item)
        if len(kept) >= k:
            break
    return kept

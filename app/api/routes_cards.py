"""Card lookup endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.agents.pipeline import get_user_cards
from app.api.dependencies import get_repository_bundle
from app.core.schemas import CardArtifact
from app.repositories.protocols import RepositoryBundle


router = APIRouter()


def _dump_card(card: CardArtifact) -> dict[str, object]:
    return {
        "card_id": card.card_id,
        "topic_id": card.topic_id,
        "run_date": card.run_date.isoformat(),
        "title": card.title,
        "image_url": card.image_url,
        "cached": card.cached,
        "headline": card.analysis.headline,
        "summary": card.analysis.summary,
        "disclaimer": card.analysis.disclaimer,
    }


@router.get("/cards/today")
def get_today_cards(
    user_id: str = Query(min_length=1),
    run_date: date | None = Query(default=None),
    repos: RepositoryBundle = Depends(get_repository_bundle),
) -> dict[str, object]:
    runtime_date = run_date or date.today()
    cards = get_user_cards(repos, user_id=user_id, run_date=runtime_date)
    return {
        "user_id": user_id,
        "run_date": runtime_date.isoformat(),
        "cards": [_dump_card(card) for card in cards],
    }

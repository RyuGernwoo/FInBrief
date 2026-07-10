"""Service wrapper for running the FinBrief LangGraph pipeline from APIs."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.agents.graph import graph
from app.core.config import get_settings
from app.core.schemas import (
    BatchRunResult,
    CardArtifact,
    DeliveryLog,
    FullReport,
    IndicatorValue,
    TopicAnalysis,
)
from app.repositories.protocols import RepositoryBundle


DISCLAIMER = "본 브리핑은 투자 조언이 아닌 참고용 정보입니다."
_LATEST_RESULTS: dict[date, BatchRunResult] = {}


def _indicator_from_state(item: dict[str, Any], run_date: date) -> IndicatorValue:
    current_value = float(item.get("value") or item.get("current_value") or 0)
    previous_value = item.get("prev", item.get("previous_value"))
    previous_float = float(previous_value) if previous_value is not None else None
    return IndicatorValue(
        indicator_id=str(item["indicator_id"]),
        name=str(item.get("name") or item["indicator_id"]),
        source="fixture",
        value_date=run_date,
        current_value=current_value,
        previous_value=previous_float,
        change_percent=item.get("change_pct", item.get("change_percent")),
        unit=item.get("unit"),
        missing=bool(item.get("missing", False)),
    )


def _card_from_state(
    repos: RepositoryBundle,
    item: dict[str, Any],
    run_date: date,
) -> CardArtifact:
    cached = repos.cards.get(str(item["topic_id"]), run_date)
    if cached is not None:
        return cached.model_copy(update={"cached": bool(item.get("cached", cached.cached))})

    headline = str(item.get("headline") or item.get("subtitle") or item["topic_id"])
    summary = str(item.get("lead") or item.get("body") or headline)
    return CardArtifact(
        card_id=str(item.get("card_id") or f"card_{item['topic_id']}_{run_date:%Y%m%d}"),
        topic_id=str(item["topic_id"]),
        run_date=run_date,
        title=headline,
        image_url=item.get("image_url") or item.get("image_path"),
        analysis=TopicAnalysis(
            topic_id=str(item["topic_id"]),
            run_date=run_date,
            headline=headline,
            summary=summary,
            key_points=[summary],
            disclaimer=str(item.get("disclaimer") or DISCLAIMER),
        ),
        cached=bool(item.get("cached", False)),
    )


def _delivery_from_state(item: dict[str, Any]) -> DeliveryLog:
    return DeliveryLog(
        delivery_id=str(item["delivery_id"]),
        user_id=str(item["user_id"]),
        topic_id=item.get("topic_id"),
        card_id=item.get("card_id"),
        channel=item["channel"],
        status=item["status"],
        attempts=int(item.get("attempts", 0)),
    )


def run_morning_pipeline(
    repos: RepositoryBundle,
    *,
    run_date: date,
    run_id: str | None = None,
    dry_run: bool = True,
) -> BatchRunResult:
    runtime_run_id = run_id or f"run_{run_date:%Y%m%d}_mock"
    final = graph.invoke(
        {
            "run_id": runtime_run_id,
            "run_date": run_date.isoformat(),
            "status": "queued",
            "repositories": repos,
            "cards": [],
            "deliveries": [],
            "errors": [],
            "dry_run": dry_run,
            # Supabase/Upstage 실데이터 모드는 mock 비활성화 시에만 켠다.
            "live_data": not get_settings().enable_mock_data,
        }
    )
    indicators = [
        _indicator_from_state(item, run_date)
        for item in final.get("indicators", [])
    ]
    cards = [_card_from_state(repos, item, run_date) for item in final.get("cards", [])]
    deliveries = [_delivery_from_state(item) for item in final.get("deliveries", [])]
    report = FullReport(
        report_id=f"report_{run_date:%Y%m%d}",
        run_date=run_date,
        indicators=indicators,
        top_news=[],
        report_url=final.get("report_url"),
        disclaimer=DISCLAIMER,
    )
    result = BatchRunResult(
        run_id=runtime_run_id,
        run_date=run_date,
        status=final["status"],
        report=report,
        generated_cards=cards,
        delivery_results=deliveries,
        trace_id=final.get("trace_id"),
        errors=[str(item.get("message", item)) for item in final.get("errors", [])],
    )
    _LATEST_RESULTS[run_date] = result
    return result


def get_latest_result(run_date: date | None = None) -> BatchRunResult | None:
    if run_date is not None:
        return _LATEST_RESULTS.get(run_date)
    if not _LATEST_RESULTS:
        return None
    return _LATEST_RESULTS[max(_LATEST_RESULTS)]


def get_user_cards(
    repos: RepositoryBundle,
    *,
    user_id: str,
    run_date: date,
) -> list[CardArtifact]:
    repos.users.get_or_create("discord", user_id)
    cards: list[CardArtifact] = []
    for subscription in repos.subscriptions.list_by_user(user_id):
        card = repos.cards.get(subscription.topic_id, run_date)
        if card is not None:
            cards.append(card)
    return cards


def reset_latest_results() -> None:
    _LATEST_RESULTS.clear()

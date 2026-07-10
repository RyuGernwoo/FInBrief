"""FinBrief · BriefState (LangGraph 상태 계약).

schemas/finbrief_state.schema.json 과 1:1 대응.
cards/deliveries/errors 는 FanOut 병렬 결과 병합을 위해 리듀서(operator.add) 사용.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class BriefState(TypedDict, total=False):
    # 실행 메타
    run_id: str
    run_date: str
    status: str            # queued|running|completed|partial_success|failed
    trace_id: str | None
    report_url: str | None
    # 공유 단계 산출물
    indicators: list[dict[str, Any]]
    missing_indicators: list[str]
    top_news: list[dict[str, Any]]
    repositories: Any
    subscriptions: list[dict[str, Any]]
    unique_topics: list[dict[str, Any]]
    topics_to_generate: list[dict[str, Any]]
    cached_cards: list[dict[str, Any]]
    generated_count: int
    reused_count: int
    # FanOut 병합 (리듀서)
    cards: Annotated[list[dict[str, Any]], operator.add]
    deliveries: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]
    # 서브그래프 전용(Send 페이로드)
    topic: dict[str, Any]

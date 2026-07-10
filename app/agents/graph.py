"""FinBrief · 메인 생성 그래프 조립.
START → ingest_news → collect_indicators → collect_topics
      → [dispatch: Send FanOut] → build_card(병렬) → aggregate_cards → deliver → END"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from .state import BriefState
from . import nodes as N


def build_graph():
    g = StateGraph(BriefState)
    g.add_node("ingest_news", N.ingest_news)
    g.add_node("collect_indicators", N.collect_indicators)
    g.add_node("collect_topics", N.collect_topics)
    g.add_node("load_cached_cards", N.load_cached_cards)
    g.add_node("build_card", N.build_card)
    g.add_node("persist_cards", N.persist_cards)
    g.add_node("aggregate_cards", N.aggregate_cards)
    g.add_node("deliver", N.deliver)

    g.add_edge(START, "ingest_news")
    g.add_edge("ingest_news", "collect_indicators")
    g.add_edge("collect_indicators", "collect_topics")
    g.add_edge("collect_topics", "load_cached_cards")
    g.add_conditional_edges("load_cached_cards", N.dispatch, ["build_card", "aggregate_cards"])
    g.add_edge("build_card", "persist_cards")
    g.add_edge("persist_cards", "aggregate_cards")
    g.add_edge("aggregate_cards", "deliver")
    g.add_edge("deliver", END)
    return g.compile()


graph = build_graph()

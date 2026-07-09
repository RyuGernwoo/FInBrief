"""Phase 0 노드 stub. [팀원]=데이터 파트, [나]=LangGraph/카드.
   지금은 fixtures 로 동작만 확인(관통). 실구현 시 파일 분리."""
from __future__ import annotations

import os
from typing import Any

from langgraph.types import Send

from .state import BriefState
from . import fixtures as fx
from .card_schema import CardContent
from .render import render_card
from app.core import llm


# ---- 공유 단계 (main graph) ----
def ingest_news(state: BriefState) -> dict[str, Any]:
    """[팀원] 뉴스 수집→passage 임베딩→news_embeddings 저장."""
    return {}


def collect_indicators(state: BriefState) -> dict[str, Any]:
    """[팀원] 전체 지표 수집 + 전체 리포트."""
    indicators = [{"indicator_id": k, "source": "fixture", **v} for k, v in fx.FIXTURE_INDICATORS.items()]
    return {"indicators": indicators, "report_url": None}


def collect_topics(state: BriefState) -> dict[str, Any]:
    """[나] 구독 토픽 → 고유 집합(dedup)."""
    seen, uniq = set(), []
    for sub in fx.FIXTURE_SUBSCRIPTIONS:
        tid = sub["topic_id"]
        if tid not in seen:
            seen.add(tid)
            uniq.append(next(t for t in fx.FIXTURE_TOPICS if t["topic_id"] == tid))
    return {"unique_topics": uniq}


def dispatch(state: BriefState) -> list[Send]:
    """[나] Send API로 토픽마다 build_card 병렬 실행 (FanOut)."""
    return [Send("build_card", {"topic": t, "run_date": state.get("run_date"), "run_id": state.get("run_id")})
            for t in state["unique_topics"]]


# ---- 토픽별 카드 생성 서브그래프 (build_card 안에서 순차 호출) ----
def _fetch_data(topic: dict) -> dict:            # [팀원]
    return fx.FIXTURE_INDICATORS.get(topic["topic_id"], {})

def _retrieve_news(topic: dict) -> list[dict]:   # [팀원] RAG(match_news) → NewsEvidence[]
    return fx.FIXTURE_NEWS.get(topic["topic_id"], [])

def _clip(s, n: int) -> str:
    s = str(s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _user_prompt(topic: dict, data: dict, news: list[dict]) -> str:
    lines = [f"topic: {topic['name']} ({topic['category']})",
             f"indicator: now {data.get('value')} {data.get('unit', '')}, change {data.get('change_pct')}%",
             "news:"]
    lines += [f"- {n['title']}: {n['snippet']}" for n in news] or ["- (none)"]
    return "\n".join(lines)


def _local_analysis(topic: dict, data: dict, news: list[dict]) -> dict:
    chg = data.get("change_pct", 0.0)
    arrow = "상승" if chg > 0 else ("하락" if chg < 0 else "보합")
    return {"headline": f"{topic['name']} {arrow}",
            "lead": f"{topic['name']} {data.get('value')} ({chg:+.2f}%)",
            "body": (news[0]["snippet"] if news else "관련 뉴스 없음") + " (local)",
            "source": "FinBrief"}


def _analyze(topic: dict, data: dict, news: list[dict]) -> dict:
    raw = llm.chat_json(llm.SYSTEM_ANALYZE, _user_prompt(topic, data, news)) if llm.use_llm() \
        else _local_analysis(topic, data, news)
    card = CardContent(
        category=topic["category"], index_no="00",
        subtitle=_clip(topic["name"], 20),
        headline=_clip(raw.get("headline", topic["name"]), 14),
        lead=_clip(raw.get("lead", ""), 45),
        body=_clip(raw.get("body", ""), 160),
        source=raw.get("source", "FinBrief"),
        evidence=news,
    )
    return card.model_dump()


def _gen_image_prompt(content: dict) -> str:
    return f"{content['subtitle']} illustration, muted palette, no text"


def _generate_image(prompt: str) -> str | None:
    return None  # Phase 2: Nano Banana


def _compose_card(content: dict, topic_id: str, run_date: str) -> str:
    out = os.environ.get("FINBRIEF_OUT") or os.path.join(os.path.dirname(__file__), "out")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{run_date}_{topic_id}.png")
    return render_card(content, path)


def _verify(content: dict, data: dict) -> tuple[bool, list[str]]:
    issues = []
    if not content.get("source"):
        issues.append("no-source")
    if not content.get("body"):
        issues.append("no-body")
    if len(content.get("headline", "")) > 14:
        issues.append("headline-overflow")
    if len(content.get("lead", "")) > 45:
        issues.append("lead-overflow")
    return (len(issues) == 0, issues)


def build_card(state: BriefState) -> dict:
    topic = state["topic"]
    run_date = state.get("run_date", "")
    try:
        data = _fetch_data(topic)
        news = _retrieve_news(topic)
        content = _analyze(topic, data, news)
        content["image_url"] = _generate_image(_gen_image_prompt(content))
        out_path = _compose_card(content, topic["topic_id"], run_date)
        ok, issues = _verify(content, data)
        card = {**content, "topic_id": topic["topic_id"], "image_path": out_path, "rendered": True, "verified": ok}
        result = {"cards": [card]}
        if not ok:
            result["errors"] = [{"code": "verify", "message": ",".join(issues), "node": "verify", "topic": topic["topic_id"]}]
        return result
    except Exception as e:
        return {"errors": [{"code": "build_card", "message": str(e), "node": "build_card", "topic": topic.get("topic_id")}]}


# ---- 집계 · 발송 ----
def aggregate_cards(state: BriefState) -> dict[str, Any]:  # [나]
    n_cards, n_err = len(state.get("cards", [])), len(state.get("errors", []))
    status = "completed" if n_err == 0 else ("partial_success" if n_cards else "failed")
    return {"status": status}


def deliver(state: BriefState) -> dict[str, Any]:  # [나] 추후 notifier(Discord/Slack)
    by_topic = {c["topic_id"]: c for c in state.get("cards", [])}
    deliveries = []
    for sub in fx.FIXTURE_SUBSCRIPTIONS:
        card = by_topic.get(sub["topic_id"])
        deliveries.append({"delivery_id": f"{sub['user_id']}:{sub['topic_id']}",
                           "user_id": sub["user_id"], "channel": sub["channel"], "topic_id": sub["topic_id"],
                           "status": "sent" if card else "skipped", "attempts": 1})
    return {"deliveries": deliveries}

"""Phase 0 노드 stub. [팀원]=데이터 파트, [나]=LangGraph/카드.
   지금은 fixtures 로 동작만 확인(관통). 실구현 시 파일 분리."""
from __future__ import annotations

import os
import re
from datetime import date
from typing import Any

from langgraph.types import Send

from .state import BriefState
from . import fixtures as fx
from . import rag
from .card_schema import CardContent
from .render import render_card
from .report_render import render_market_report_image
from app.core import llm
from app.core.schemas import CardArtifact, NewsEvidence, Topic, TopicAnalysis
from app.repositories.protocols import RepositoryBundle, RepositoryNotFoundError
from app.tools import image_gen
from app.tools.data_sources import fred, yfinance_source
from app.tools.news import rss, tagging
from app.tools.embedding.upstage import EMBEDDING_PASSAGE_MODEL, UpstageEmbeddingProvider
from app.services import notifier, topic_ingestion


_DIR = os.path.dirname(__file__)
DISCLAIMER = "본 브리핑은 투자 조언이 아닌 참고용 정보입니다."

IMAGE_PROMPT_SYSTEM = (
    "You are an image-prompt writer for a financial card news. "
    "Given the card info, output ONE english image prompt as JSON {\"prompt\": \"...\"}. "
    "Style: clean isometric illustration, muted palette. "
    "The illustration MUST contain no text, no letters, no numbers."
)


# ---- 공유 단계 (main graph) ----
def _live_ingestion() -> Any:
    """Supabase ingestion repository (live 모드 전용). 실패 시 None."""
    try:
        from app.repositories.supabase import SupabaseIngestionRepository
        from app.repositories.supabase_client import create_supabase_client

        return SupabaseIngestionRepository(create_supabase_client())
    except Exception:
        return None


def _news_id_by_url(rows: Any) -> dict[str, str]:
    """upsert_news_documents 응답에서 url -> DB news id 매핑을 만든다."""
    mapping: dict[str, str] = {}
    if not isinstance(rows, list):
        return mapping
    for row in rows:
        if isinstance(row, dict) and row.get("url") and row.get("id"):
            mapping[str(row["url"])] = str(row["id"])
    return mapping


def ingest_news(state: BriefState) -> dict[str, Any]:
    """뉴스 수집→태깅→passage 임베딩→Supabase 적재. live_data에서만 동작."""
    if not state.get("live_data"):
        return {}
    repos: RepositoryBundle | None = state.get("repositories")
    if repos is None:
        return {}

    ingestion = state.get("ingestion") or _live_ingestion()
    provider = state.get("embedding_provider") or UpstageEmbeddingProvider()
    if ingestion is None:
        return {"errors": [{"code": "INGEST_SKIPPED", "message": "no ingestion repository",
                            "node": "ingest_news", "topic": None}]}

    try:
        topics = repos.topics.list_catalog()
        since = rag.since_for(_parse_run_date(state["run_date"]))
        documents = rss.fetch_rss_news()
        documents = rss.filter_recent_news(documents, since=since)
        documents = tagging.tag_news_for_topics(documents, topics, include_general_market=True)
        if not documents:
            return {}

        id_by_url = _news_id_by_url(ingestion.upsert_news_documents(documents))
        rows: list[dict[str, Any]] = []
        for document in documents:
            news_id = id_by_url.get(str(document.url))
            if news_id is None:
                continue
            try:
                rows.append({
                    "news_id": news_id,
                    "embedding": provider.embed_passage(document),
                    "embedding_model": EMBEDDING_PASSAGE_MODEL,
                    "embedding_kind": "passage",
                })
            except Exception:
                continue
        if rows:
            ingestion.upsert_news_embeddings(rows)
        return {}
    except Exception as exc:
        return {"errors": [{"code": "INGEST_FAILED", "message": str(exc),
                            "node": "ingest_news", "topic": None}]}


def _collect_topic_indicator(topic: Topic, run_date: date) -> list[Any]:
    """토픽 source_mapping을 provider별로 분기해 최신 IndicatorValue[]를 수집."""
    return topic_ingestion.collect_topic_indicators(topic, run_date)


def collect_indicators(state: BriefState) -> dict[str, Any]:
    """전체 지표 수집. live_data에서는 source_mapping 실수집, 아니면 fixture."""
    repos: RepositoryBundle | None = state.get("repositories")
    if not state.get("live_data") or repos is None:
        indicators = [{"indicator_id": k, "source": "fixture", **v} for k, v in fx.FIXTURE_INDICATORS.items()]
        return {"indicators": indicators, "report_url": None}

    run_date = _parse_run_date(state["run_date"])
    indicators: list[dict[str, Any]] = []
    missing: list[str] = []
    for graph_topic in state.get("unique_topics", []):
        try:
            topic_model = repos.topics.get(graph_topic["topic_id"])
        except RepositoryNotFoundError:
            continue
        values = _collect_topic_indicator(topic_model, run_date)
        if not values:
            missing.append(graph_topic["topic_id"])
            continue
        latest = values[-1]
        indicators.append({
            "indicator_id": graph_topic["topic_id"],
            "name": topic_model.name,
            "source": latest.source,
            "value": latest.current_value,
            "prev": latest.previous_value,
            "change_pct": latest.change_percent,
            "unit": latest.unit,
        })

    result: dict[str, Any] = {"indicators": indicators, "report_url": None}
    if missing:
        result["missing_indicators"] = missing
    return result


def build_report_image(state: BriefState) -> dict[str, Any]:
    """전체 주요 지표 리포트 이미지를 한 번 생성하고 report_url에 기록한다."""
    try:
        run_date = _parse_run_date(state["run_date"])
        report_url = render_market_report_image(
            state.get("indicators", []),
            run_date=run_date,
            missing_indicators=state.get("missing_indicators", []),
        )
        return {"report_url": report_url}
    except Exception as exc:
        return {
            "errors": [
                {
                    "code": "report_image_render",
                    "message": str(exc),
                    "node": "build_report_image",
                    "topic": None,
                }
            ]
        }


def _topic_category(topic: Topic) -> str:
    if topic.type == "asset" and topic.normalized_name == "btc":
        return "CRYPTO"
    if topic.type == "indicator" and any(token in topic.normalized_name for token in ("usd", "krw", "fx")):
        return "FX"
    if topic.type == "indicator":
        return "GLOBAL"
    return "MARKET"


def _graph_topic(topic: Topic) -> dict[str, Any]:
    return {
        "topic_id": topic.topic_id,
        "source_key": topic.normalized_name,
        "name": topic.name,
        "category": _topic_category(topic),
    }


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _topic_source_key(topic: dict[str, Any]) -> str:
    topic_id = str(topic.get("topic_id", ""))
    return str(topic.get("source_key") or topic.get("normalized_name") or topic_id.removeprefix("topic_"))


def _parse_run_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def collect_topics(state: BriefState) -> dict[str, Any]:
    """[나] 구독 토픽 → 고유 집합(dedup)."""
    repos: RepositoryBundle | None = state.get("repositories")
    if repos is not None:
        subscriptions = repos.subscriptions.list_active()
        seen: set[str] = set()
        topics: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for subscription in subscriptions:
            topic_id = subscription.topic_id
            if topic_id in seen:
                continue
            try:
                topics.append(_graph_topic(repos.topics.get(topic_id)))
                seen.add(topic_id)
            except RepositoryNotFoundError as exc:
                errors.append(
                    {
                        "code": exc.code,
                        "message": str(exc),
                        "node": "collect_topics",
                        "topic": topic_id,
                    }
                )

        result: dict[str, Any] = {
            "subscriptions": [item.model_dump(mode="json") for item in subscriptions],
            "unique_topics": topics,
        }
        if errors:
            result["errors"] = errors
        return result

    seen, uniq = set(), []
    for sub in fx.FIXTURE_SUBSCRIPTIONS:
        tid = sub["topic_id"]
        if tid not in seen:
            seen.add(tid)
            uniq.append(next(t for t in fx.FIXTURE_TOPICS if t["topic_id"] == tid))
    return {"unique_topics": uniq}


def _indicators_index(indicators: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("indicator_id")): item for item in indicators if item.get("indicator_id")}


def retrieve_evidence(state: BriefState) -> dict[str, Any]:
    """[나] fan-out 이전, 캐시 미스 토픽에 지표+뉴스 근거(RAG)를 채운다.

    live_data 전용. 여기서 repos.news.match(match_news RPC)를 호출하고 §rag 후처리를
    적용해 topic payload에 실어 보내므로, build_card는 네트워크/repos 접근 없이
    payload만 소비한다. live가 아니면 no-op이며 build_card가 fixture로 fallback한다.
    """
    if not state.get("live_data"):
        return {}
    repos: RepositoryBundle | None = state.get("repositories")
    topics = state.get("topics_to_generate", [])
    if repos is None or not topics:
        return {}

    since = rag.since_for(_parse_run_date(state["run_date"]))
    indicator_index = _indicators_index(state.get("indicators", []))
    enriched: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for graph_topic in topics:
        item = dict(graph_topic)
        try:
            topic_model = repos.topics.get(graph_topic["topic_id"])
            # 후보는 넓게(RAG_CANDIDATES), 최종은 postprocess 가 RAG_K 로 컷(threshold·다양성·top-k).
            evidence = rag.postprocess_evidence(
                repos.news.match(topic_model, since, rag.RAG_CANDIDATES),
                k=rag.RAG_K,
            )
            item["evidence"] = [ev.model_dump(mode="json") for ev in evidence]
        except Exception as exc:
            item["evidence"] = []
            errors.append({"code": "RAG_FAILED", "message": str(exc),
                           "node": "retrieve_evidence", "topic": graph_topic.get("topic_id")})
        item["indicator"] = indicator_index.get(graph_topic["topic_id"], {})
        enriched.append(item)

    result: dict[str, Any] = {"topics_to_generate": enriched}
    if errors:
        result["errors"] = errors
    return result


def dispatch(state: BriefState) -> list[Send] | str:
    """[나] Send API로 토픽마다 build_card 병렬 실행 (FanOut)."""
    topics = state.get("topics_to_generate")
    if topics is None:
        topics = state.get("unique_topics", [])
    if not topics:
        return "aggregate_cards"
    return [Send("build_card", {"topic": t, "run_date": state.get("run_date"), "run_id": state.get("run_id")})
            for t in topics]


def _card_from_artifact(card: CardArtifact) -> dict[str, Any]:
    return {
        "card_id": card.card_id,
        "topic_id": card.topic_id,
        "category": "MARKET",
        "index_no": "00",
        "subtitle": card.title,
        "headline": card.analysis.headline,
        "lead": card.analysis.summary,
        "body": " ".join(card.analysis.key_points),
        "source": "FinBrief",
        "evidence": [item.model_dump(mode="json") for item in card.analysis.evidence],
        "disclaimer": card.analysis.disclaimer,
        "image_url": card.image_url,
        "image_path": card.image_url,
        "image_prompt": None,
        "rendered": bool(card.image_url),
        "verified": True,
        "cached": True,
    }


def _artifact_from_card(card: dict[str, Any], run_date: date) -> CardArtifact:
    topic_id = str(card["topic_id"])
    headline = str(card.get("headline") or card.get("subtitle") or topic_id)
    summary = str(card.get("lead") or card.get("body") or headline)
    key_points = [
        str(item)
        for item in (card.get("lead"), card.get("body"))
        if item
    ] or [summary]
    evidence: list[NewsEvidence] = []
    for item in card.get("evidence", []):
        try:
            evidence.append(NewsEvidence.model_validate(item))
        except Exception:
            continue

    return CardArtifact(
        card_id=str(card.get("card_id") or f"card_{topic_id}_{run_date.strftime('%Y%m%d')}"),
        topic_id=topic_id,
        run_date=run_date,
        title=headline,
        image_url=card.get("image_url") or card.get("image_path"),
        analysis=TopicAnalysis(
            topic_id=topic_id,
            run_date=run_date,
            headline=headline,
            summary=summary,
            key_points=key_points,
            evidence=evidence,
            disclaimer=str(card.get("disclaimer") or DISCLAIMER),
        ),
        cached=bool(card.get("cached", False)),
    )


def load_cached_cards(state: BriefState) -> dict[str, Any]:
    repos: RepositoryBundle | None = state.get("repositories")
    topics = state.get("unique_topics", [])
    if repos is None:
        return {"topics_to_generate": topics, "cached_cards": [], "reused_count": 0}

    run_date = _parse_run_date(state["run_date"])
    cached_cards: list[dict[str, Any]] = []
    topics_to_generate: list[dict[str, Any]] = []

    for topic in topics:
        cached = repos.cards.get(topic["topic_id"], run_date)
        if cached is None:
            topics_to_generate.append(topic)
        else:
            cached_cards.append(_card_from_artifact(cached.model_copy(update={"cached": True})))

    return {
        "cards": cached_cards,
        "cached_cards": cached_cards,
        "topics_to_generate": topics_to_generate,
        "reused_count": len(cached_cards),
    }


def persist_cards(state: BriefState) -> dict[str, Any]:
    repos: RepositoryBundle | None = state.get("repositories")
    if repos is None:
        return {}

    run_date = _parse_run_date(state["run_date"])
    errors: list[dict[str, Any]] = []
    for card in state.get("cards", []):
        if card.get("cached"):
            continue
        try:
            repos.cards.upsert(_artifact_from_card(card, run_date))
        except Exception as exc:
            errors.append(
                {
                    "code": "card_cache_upsert",
                    "message": str(exc),
                    "node": "persist_cards",
                    "topic": card.get("topic_id"),
                }
            )
    return {"errors": errors} if errors else {}


# ---- 토픽별 카드 생성 서브그래프 (build_card 안에서 순차 호출) ----
def _fetch_data(topic: dict) -> dict:            # retrieve_evidence가 채운 지표 or fixture fallback
    if "indicator" in topic:
        return topic.get("indicator") or {}
    return fx.FIXTURE_INDICATORS.get(topic["topic_id"], fx.FIXTURE_INDICATORS.get(_topic_source_key(topic), {}))

def _retrieve_news(topic: dict) -> list[dict]:   # retrieve_evidence가 채운 RAG 근거 or fixture fallback
    if "evidence" in topic:
        return topic.get("evidence") or []
    return fx.FIXTURE_NEWS.get(topic["topic_id"], fx.FIXTURE_NEWS.get(_topic_source_key(topic), []))

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


def _fallback_prompt(content: dict) -> str:
    return (f"clean isometric illustration about {content.get('subtitle', '')}, "
            f"muted palette, no text, no letters, no numbers")


def _gen_image_prompt(content: dict) -> str:
    if llm.use_llm():
        try:
            user = f"topic: {content.get('subtitle')}\nheadline: {content.get('headline')}\nbody: {content.get('body')}"
            raw = llm.chat_json(IMAGE_PROMPT_SYSTEM, user)
            return raw.get("prompt") or _fallback_prompt(content)
        except Exception:
            return _fallback_prompt(content)
    return _fallback_prompt(content)


def _img_out() -> str:
    return os.environ.get("FINBRIEF_IMG_OUT") or os.path.join(_DIR, "out_llm")


def _generate_image(prompt: str, topic_id: str, run_date: str) -> str | None:
    asset = image_gen.generate_image(prompt, _img_out(), f"{run_date}_{topic_id}")
    return asset.path if asset else None


def _compose_card(content: dict, topic_id: str, run_date: str) -> str:
    out = os.environ.get("FINBRIEF_OUT") or os.path.join(os.path.dirname(__file__), "out")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{run_date}_{topic_id}.png")
    return render_card(content, path)


def _nums(s: str) -> list[str]:
    return re.findall(r"-?\d+\.?\d*", s or "")


def _verify(content: dict, data: dict) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not content.get("source"):
        issues.append("no-source")
    if not content.get("body"):
        issues.append("no-body")
    if len(content.get("headline", "")) > 14:
        issues.append("headline-overflow")
    if len(content.get("lead", "")) > 45:
        issues.append("lead-overflow")
    # 관련성: 카테고리 유효
    if content.get("category") not in ("MARKET", "GLOBAL", "DOMESTIC", "CRYPTO", "FX"):
        issues.append("bad-category")
    # 정확성: lead/body 숫자가 지표값/변화율과 근사 일치
    text = f"{content.get('lead', '')} {content.get('body', '')}"
    found = [float(x) for x in _nums(text) if x not in ("", "-", ".")]
    targets = [t for t in (data.get("value"), data.get("change_pct")) if t is not None]

    def _close(f: float, t: float) -> bool:
        return abs(f - t) <= max(0.02 * abs(t), 0.01)

    if found and targets and not any(_close(f, t) for f in found for t in targets):
        issues.append("number-mismatch")
    return (len(issues) == 0, issues)


def build_card(state: BriefState) -> dict:
    topic = state["topic"]
    run_date = state.get("run_date", "")
    try:
        data = _fetch_data(topic)
        news = _retrieve_news(topic)
        content = _analyze(topic, data, news)
        img_prompt = _gen_image_prompt(content)
        content["image_url"] = _generate_image(img_prompt, topic["topic_id"], run_date)
        out_path = _compose_card(content, topic["topic_id"], run_date)
        ok, issues = _verify(content, data)
        card = {**content, "card_id": f"card_{topic['topic_id']}_{run_date.replace('-', '')}",
                "topic_id": topic["topic_id"], "image_path": out_path,
                "image_prompt": img_prompt, "rendered": True, "verified": ok, "cached": False}
        result = {"cards": [card]}
        if not ok:
            result["errors"] = [{"code": "verify", "message": ",".join(issues), "node": "verify", "topic": topic["topic_id"]}]
        return result
    except Exception as e:
        return {"errors": [{"code": "build_card", "message": str(e), "node": "build_card", "topic": topic.get("topic_id")}]}


# ---- 집계 · 발송 ----
def aggregate_cards(state: BriefState) -> dict[str, Any]:  # [나]
    cards = state.get("cards", [])
    n_cards, n_err = len(cards), len(state.get("errors", []))
    status = "completed" if n_err == 0 else ("partial_success" if n_cards else "failed")
    generated_count = len([card for card in cards if not card.get("cached")])
    reused_count = len([card for card in cards if card.get("cached")])
    return {
        "status": status,
        "generated_count": generated_count,
        "reused_count": reused_count,
        "trace_id": state.get("trace_id") or f"local_mock_trace_{state.get('run_id', 'run')}",
    }


def _webhook_for(channel: str) -> str:
    return os.getenv("DISCORD_WEBHOOK_URL", "") if channel == "discord" else os.getenv("SLACK_WEBHOOK_URL", "")


def deliver(state: BriefState) -> dict[str, Any]:
    """[나] 구독 기준 fan-out 발송 (Discord/Slack webhook 또는 Discord bot)."""
    by_topic = {c["topic_id"]: c for c in state.get("cards", [])}
    subscriptions = state["subscriptions"] if "subscriptions" in state else fx.FIXTURE_SUBSCRIPTIONS
    deliveries = []

    for sub in subscriptions:
        topic_id = _value(sub, "topic_id")
        user_id = _value(sub, "user_id")
        channel = _value(sub, "channel")
        channel_id = _value(sub, "discord_channel_id") or _value(sub, "channel_id")
        card = by_topic.get(topic_id)

        base = {
            "delivery_id": f"{user_id}:{topic_id}",
            "user_id": user_id,
            "channel": channel,
            "topic_id": topic_id,
            "card_id": card.get("card_id") if card else None,
        }

        if not card:
            deliveries.append({**base, "status": "skipped", "attempts": 0, "error_code": None})
            continue

        text = notifier.format_card_text(card)
        image_path = card.get("image_path") or card.get("image_url")

        if channel == "discord" and channel_id and hasattr(notifier, "send_via_bot"):
            send_result = notifier.send_via_bot(
                channel_id=channel_id,
                text=text,
                image_path=image_path,
            )
        else:
            send_result = notifier.send_card(
                channel=channel,
                webhook_url=_webhook_for(channel),
                text=text,
                image_path=image_path,
            )

        deliveries.append(
            {
                **base,
                "status": send_result.get("status", "failed"),
                "attempts": 1,
                "error_code": send_result.get("error"),
            }
        )

    return {"deliveries": deliveries}

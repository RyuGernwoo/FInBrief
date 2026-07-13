"""LiteLLM 게이트웨이 — Solar 메인 + retry·timeout·fallback.
   UPSTAGE_API_KEY 없거나 FINBRIEF_LLM_STUB=1 이면 caller 가 로컬 폴백.

   주의: litellm 은 버전에 따라 `upstage/` provider 를 네이티브로 인식하지 못한다
   (예: 1.91.x). Upstage Solar 는 OpenAI 호환 API 이므로, `upstage/solar-*` 또는
   `solar-*` 모델명은 `openai/<name>` + Upstage api_base 로 라우팅한다."""
from __future__ import annotations

import json
import os
from typing import Any

from app.core import llm_guardrails, observability
from app.core.config import get_settings

SYSTEM_ANALYZE = (
    "너는 금융 카드뉴스 편집자다. 주어진 지표 수치와 뉴스 근거만 사용해 "
    "한국어로 카드 문구를 JSON으로 작성한다. 수치를 지어내지 말 것. "
    "제시된 '단위/통화'를 반드시 그대로 사용하고, 원↔달러 등 통화를 임의로 바꾸지 말 것. "
    "body는 뉴스 근거의 핵심을 종합해 4~5문장으로 충실히 채운다(배경·원인·영향·전망을 담되 반복 금지). "
    "headline은 긴 숫자 나열 대신 핵심 메시지로 짧게(≤16자). "
    'JSON 키: {"headline": "≤16자 핵심", "lead": "≤45자 한 줄", '
    '"body": "4~5문장 200~240자", "source": "출처"}'
)

UPSTAGE_BASE_URL = "https://api.upstage.ai/v1"


def use_llm() -> bool:
    return bool(os.getenv("UPSTAGE_API_KEY")) and os.getenv("FINBRIEF_LLM_STUB") != "1"


def _resolve_model() -> tuple[str, dict]:
    """모델명과 litellm 호출용 provider kwargs(api_base·api_key)를 결정한다."""
    cfg = get_settings()
    raw = os.getenv("FINBRIEF_LLM_MODEL") or cfg.litellm_model or "upstage/solar-pro"
    extra: dict = {}
    name = raw.split("/", 1)[1] if "/" in raw else raw
    is_solar = raw.startswith("upstage/") or ("/" not in raw and raw.startswith("solar"))
    if is_solar:
        model = f"openai/{name}"
        extra["api_base"] = os.getenv("FINBRIEF_LLM_API_BASE") or UPSTAGE_BASE_URL
        key = os.getenv("UPSTAGE_API_KEY")
        if key:
            extra["api_key"] = key
    else:
        # openai/..., anthropic/... 등 provider 가 명시된 경우 그대로 사용
        model = raw
        if os.getenv("FINBRIEF_LLM_API_BASE"):
            extra["api_base"] = os.environ["FINBRIEF_LLM_API_BASE"]
    return model, extra


def chat_json(
    system: str,
    user: str,
    *,
    metadata: dict[str, Any] | None = None,
    guardrail_profile: str = "generic",
) -> dict:
    import litellm

    cfg = get_settings()
    observability.configure_litellm_callbacks(litellm)
    model, extra = _resolve_model()
    safe_system, safe_user = llm_guardrails.prepare_prompt(system, user, cfg)
    fallback_model = os.getenv("FINBRIEF_LLM_FALLBACK") or cfg.litellm_fallback_model or ""
    request_metadata = {
        **(metadata or {}),
        "llm_primary_model": os.getenv("FINBRIEF_LLM_MODEL") or cfg.litellm_model,
        "llm_fallback_model": fallback_model or None,
        "llm_timeout_seconds": cfg.finbrief_llm_timeout_seconds,
        "llm_num_retries": cfg.finbrief_llm_num_retries,
        "guardrail_enabled": cfg.finbrief_llm_guardrail_enabled,
        "guardrail_profile": guardrail_profile,
        "fallback_configured": bool(fallback_model),
    }
    kwargs: dict = dict(
        model=model,
        messages=[{"role": "system", "content": safe_system}, {"role": "user", "content": safe_user}],
        response_format={"type": "json_object"},
        num_retries=cfg.finbrief_llm_num_retries,
        timeout=cfg.finbrief_llm_timeout_seconds,
        **extra,
    )
    kwargs["metadata"] = observability.sanitize_metadata(
        {k: v for k, v in request_metadata.items() if v is not None}
    )
    if fallback_model:
        kwargs["fallbacks"] = [{"model": fallback_model}]
    resp = litellm.completion(**kwargs)
    try:
        raw = json.loads(resp.choices[0].message.content)
    except Exception as exc:
        raise llm_guardrails.GuardrailViolation(
            "schema_error",
            {"error": str(exc)},
        ) from exc
    return llm_guardrails.validate_json_payload(raw, profile=guardrail_profile, settings=cfg)

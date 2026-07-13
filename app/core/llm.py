"""LiteLLM 게이트웨이 — Solar 메인 + retry·timeout·fallback.
   UPSTAGE_API_KEY 없거나 FINBRIEF_LLM_STUB=1 이면 caller 가 로컬 폴백.

   주의: litellm 은 버전에 따라 `upstage/` provider 를 네이티브로 인식하지 못한다
   (예: 1.91.x). Upstage Solar 는 OpenAI 호환 API 이므로, `upstage/solar-*` 또는
   `solar-*` 모델명은 `openai/<name>` + Upstage api_base 로 라우팅한다."""
from __future__ import annotations

import json
import os
from typing import Any

from app.core import observability

SYSTEM_ANALYZE = (
    "너는 금융 카드뉴스 편집자다. 주어진 지표 수치와 뉴스 근거만 사용해 "
    "한국어로 간결한 카드 문구를 JSON으로 작성한다. 수치를 지어내지 말 것. "
    'JSON 키: {"headline": "≤14자 강조", "lead": "≤45자 한 줄", '
    '"body": "2~3문장 ≤160자", "source": "출처"}'
)

UPSTAGE_BASE_URL = "https://api.upstage.ai/v1"


def use_llm() -> bool:
    return bool(os.getenv("UPSTAGE_API_KEY")) and os.getenv("FINBRIEF_LLM_STUB") != "1"


def _resolve_model() -> tuple[str, dict]:
    """모델명과 litellm 호출용 provider kwargs(api_base·api_key)를 결정한다."""
    raw = os.getenv("FINBRIEF_LLM_MODEL") or os.getenv("LITELLM_MODEL") or "upstage/solar-pro"
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


def chat_json(system: str, user: str, *, metadata: dict[str, Any] | None = None) -> dict:
    import litellm
    observability.configure_litellm_callbacks(litellm)
    model, extra = _resolve_model()
    kwargs: dict = dict(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        num_retries=2,
        timeout=30,
        **extra,
    )
    if metadata:
        kwargs["metadata"] = observability.sanitize_metadata(metadata)
    fb = os.getenv("FINBRIEF_LLM_FALLBACK") or os.getenv("LITELLM_FALLBACK_MODEL") or ""
    if fb:
        kwargs["fallbacks"] = [{"model": fb}]
    resp = litellm.completion(**kwargs)
    return json.loads(resp.choices[0].message.content)

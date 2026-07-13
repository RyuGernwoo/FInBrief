import pytest


def test_mask_sensitive_text_redacts_common_secrets():
    from app.core.llm_guardrails import mask_sensitive_text

    text = (
        "contact me at analyst@example.com and use "
        "https://discord.com/api/webhooks/123456789/token-value"
    )

    masked = mask_sensitive_text(text)

    assert "analyst@example.com" not in masked
    assert "discord.com/api/webhooks" not in masked
    assert "[EMAIL_REDACTED]" in masked
    assert "[WEBHOOK_REDACTED]" in masked


def test_validate_card_json_rejects_forbidden_financial_advice():
    from app.core.llm_guardrails import GuardrailViolation, validate_json_payload
    from app.core.config import Settings

    payload = {
        "headline": "지금 매수 기회",
        "lead": "단기 반등 가능성",
        "body": "목표가를 제시하며 반드시 수익이 난다고 단정합니다.",
        "source": "예시통신",
    }

    with pytest.raises(GuardrailViolation) as exc_info:
        validate_json_payload(payload, profile="card", settings=Settings())

    assert exc_info.value.reason == "forbidden_terms"
    # 조언 구(phrase) 기반: "지금 매수"(headline) + "목표가"·"반드시 수익"(body) 차단
    terms = exc_info.value.details["terms"]
    assert "지금 매수" in terms and "목표가" in terms


def test_validate_card_json_requires_card_keys():
    from app.core.llm_guardrails import GuardrailViolation, validate_json_payload
    from app.core.config import Settings

    with pytest.raises(GuardrailViolation) as exc_info:
        validate_json_payload({"headline": "나스닥 상승"}, profile="card", settings=Settings())

    assert exc_info.value.reason == "schema_error"
    assert "body" in exc_info.value.details["missing_keys"]


def test_validate_generic_payload_masks_pii_without_card_schema():
    from app.core.llm_guardrails import validate_json_payload
    from app.core.config import Settings

    payload = {"intent": "add_topic", "topic": "달러", "note": "user@example.com"}

    result = validate_json_payload(payload, profile="intent", settings=Settings())

    assert result["note"] == "[EMAIL_REDACTED]"

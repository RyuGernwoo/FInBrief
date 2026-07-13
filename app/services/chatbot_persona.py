"""Persona policy for the FinBrief Discord management chatbot."""

from __future__ import annotations

BOT_NAME = "FinBrief Mate"
BOT_NAME_KO = "브리핑 메이트"

HELP_EXAMPLES = [
    "나스닥 구독해줘",
    "내 토픽 보여줘",
    "비트코인 취소해줘",
]

STARTER_TOPIC_IDS = [
    "topic_nasdaq",
    "topic_btc",
    "topic_usdkrw",
    "topic_us_rate",
    "topic_semi",
]

INVESTMENT_ADVICE_TERMS = [
    "사야",
    "팔아",
    "매수",
    "매도",
    "목표가",
    "수익 보장",
    "확정 수익",
]


def is_investment_advice_request(message: str) -> bool:
    text = str(message).replace(" ", "")
    return any(term.replace(" ", "") in text for term in INVESTMENT_ADVICE_TERMS)

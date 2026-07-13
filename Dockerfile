FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=prod \
    ENABLE_MOCK_DATA=true \
    DELIVERY_DRY_RUN=true \
    FINBRIEF_LLM_STUB=1 \
    FINBRIEF_IMAGE_STUB=1 \
    FINBRIEF_REPORT_OUT=/app/reports \
    PATH="/home/finbrief/.local/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system finbrief \
    && useradd --system --gid finbrief --home-dir /app finbrief

COPY pyproject.toml README.md ./
COPY app ./app
COPY data/default_topics.json ./data/default_topics.json
COPY schemas/finbrief_state.schema.json ./schemas/finbrief_state.schema.json
COPY evals/finbrief_eval_set.schema.json ./evals/finbrief_eval_set.schema.json

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir . \
    && mkdir -p /app/reports /app/app/agents/out /app/app/agents/out_llm /app/app/agents/out_reports \
    && chown -R finbrief:finbrief /app

USER finbrief

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).read()"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

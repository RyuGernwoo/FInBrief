# FinBrief

FinBrief is a personalized AI financial briefing agent for Team8. It collects macro indicators and economic news every morning, creates a safe full-market report plus topic-specific cards, caches cards by topic and date, and delivers them through Discord or Slack for the MVP.

This repository starts with the directory scaffold and schema contracts only. Application logic will be added after the schema boundaries are reviewed.

## MVP Scope

Included:

- Topic subscription management
- Free-tier topic limit
- Macro indicator and news data contracts
- Supabase PostgreSQL + pgvector schema
- LangGraph morning pipeline state schema
- Card cache and delivery log schema
- Automatic evaluation schema
- Discord/Slack delivery path

Excluded from the MVP:

- Kakao notification delivery
- Real payment processing
- Volatility deep-dive loop
- Trading advice, buy/sell recommendations, or automated orders
- Large-scale multi-user production operation

## Directory Structure

```text
app/
  api/            FastAPI route modules
  agents/         LangGraph workflows
  core/           shared schemas, settings, safety, LLM gateway
  repositories/   Supabase persistence adapters
  tools/          data, news, image, and delivery tools
  ui/             Streamlit demo UI
data/             seed data and local fixtures
evals/            automatic evaluation schema and datasets
reports/          generated local report artifacts
schemas/          database and workflow schema contracts
tests/            test suite
```

## Schema Contracts

| File | Purpose |
| --- | --- |
| `app/core/schemas.py` | Python/Pydantic data models shared by API, agents, and repositories |
| `schemas/supabase.sql` | Supabase PostgreSQL and pgvector table structure |
| `schemas/finbrief_state.schema.json` | LangGraph morning pipeline state contract |
| `evals/finbrief_eval_set.schema.json` | JSONL entry schema for automatic evaluation cases |

## Planned Runtime Stack

- Python 3.11+
- FastAPI
- LangGraph
- Supabase PostgreSQL + pgvector
- LiteLLM
- Langfuse
- Streamlit
- Discord/Slack webhooks

## Safety Rule

Every generated report and card must include a disclaimer that the content is for reference only and is not investment advice.

## Repository Status

The first commit intentionally contains only the scaffold, schema contracts, `README.md`, and `.gitignore`. Push is handled manually.

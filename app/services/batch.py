"""아침 배치 러너 — 구독 기반 카드 생성 + 발송(전체 파이프라인 1회 실행).

실행:  python -m app.services.batch            # DELIVERY_DRY_RUN 환경값 그대로
       python -m app.services.batch --dry-run  # 발송 없이 상태만(테스트)

live 데이터(실 지표/RAG 뉴스)는 ENABLE_MOCK_DATA=false 일 때 켜진다(pipeline 규약).
실 발송은 DELIVERY_DRY_RUN=false + DISCORD_BOT_TOKEN 필요.
"""
from __future__ import annotations

import argparse
import os
from datetime import date

from app.agents.pipeline import run_morning_pipeline
from app.core.schemas import BatchRunResult


def run_batch(*, run_date: date | None = None) -> BatchRunResult:
    """전체시장 리포트 + 구독 토픽 카드 생성/발송을 1회 실행."""
    # 실 repo + RAG 쿼리 임베딩 provider (뉴스 match_news 에 필요)
    from app.repositories.supabase import create_supabase_repositories
    from app.tools.embedding.upstage import UpstageEmbeddingProvider

    run_date = run_date or date.today()
    repos = create_supabase_repositories(
        query_embedding_provider=UpstageEmbeddingProvider().embed_query
    )
    from app.services import notifier

    return run_morning_pipeline(
        repos,
        run_date=run_date,
        run_id=f"batch_{run_date:%Y%m%d}",
        dry_run=notifier.dry_run(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="FinBrief 아침 배치 실행")
    parser.add_argument("--dry-run", action="store_true", help="발송 없이 상태만(DELIVERY_DRY_RUN=true 강제)")
    args = parser.parse_args()
    if args.dry_run:
        os.environ["DELIVERY_DRY_RUN"] = "true"

    result = run_batch()
    print(
        f"[batch] status={result.status} "
        f"cards={len(result.generated_cards)} "
        f"deliveries={len(result.delivery_results)} "
        f"errors={len(result.errors)} report_url={(result.report or None) and result.report.report_url}"
    )
    for d in result.delivery_results:
        print(f"  deliver {d.topic_id}: {d.status}")


if __name__ == "__main__":
    main()

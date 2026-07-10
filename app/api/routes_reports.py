"""Report execution and lookup endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.agents.pipeline import get_latest_result, run_morning_pipeline
from app.api.dependencies import get_repository_bundle
from app.core.schemas import BatchRunResult
from app.repositories.protocols import RepositoryBundle


router = APIRouter()
DISCLAIMER = "본 브리핑은 투자 조언이 아닌 참고용 정보입니다."


class ReportRunRequest(BaseModel):
    run_date: date | None = None
    dry_run: bool = True


def _summary(result: BatchRunResult) -> dict[str, object]:
    generated = len([card for card in result.generated_cards if not card.cached])
    reused = len([card for card in result.generated_cards if card.cached])
    return {
        "run_id": result.run_id,
        "run_date": result.run_date.isoformat(),
        "status": result.status,
        "generated_cards": generated,
        "reused_cards": reused,
        "delivery_results": len(result.delivery_results),
        "trace_id": result.trace_id,
        "disclaimer": result.report.disclaimer if result.report else DISCLAIMER,
        "errors": result.errors,
    }


@router.post("/reports/run")
def run_report(
    request: ReportRunRequest,
    repos: RepositoryBundle = Depends(get_repository_bundle),
) -> dict[str, object]:
    result = run_morning_pipeline(
        repos,
        run_date=request.run_date or date.today(),
        dry_run=request.dry_run,
    )
    return _summary(result)


@router.get("/reports/today")
def get_today_report(
    run_date: date | None = Query(default=None),
) -> dict[str, object]:
    result = get_latest_result(run_date)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_NOT_FOUND", "message": "No report has been generated."},
        )
    return _summary(result)

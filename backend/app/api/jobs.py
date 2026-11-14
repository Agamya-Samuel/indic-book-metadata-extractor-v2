"""Job lookup by id."""

from fastapi import APIRouter, Depends

from app.api.deps import get_job_for_user_or_404
from app.models.job import Job
from app.schemas.job import JobResponse

router = APIRouter()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job: Job = Depends(get_job_for_user_or_404),
) -> JobResponse:
    return JobResponse.model_validate(job)

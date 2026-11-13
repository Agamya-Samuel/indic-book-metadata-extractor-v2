"""Unauthenticated liveness probe for external uptime monitors.

Deliberately says nothing about downstream dependencies; the detailed check
lives at ``/health`` and is not routed publicly.
"""

from fastapi import APIRouter, Response

router = APIRouter()


@router.get("/health")
async def liveness(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
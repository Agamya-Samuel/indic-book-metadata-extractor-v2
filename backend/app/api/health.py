"""Unauthenticated liveness probe for external uptime monitors.

Deliberately says nothing about downstream dependencies; the detailed check
lives at ``/health`` and is not routed publicly.
"""

from fastapi import APIRouter, Response

from app.services import maintenance_service

router = APIRouter()


@router.get("/health")
async def liveness(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}


@router.get("/status")
async def public_status(response: Response) -> dict:
    """Public maintenance state so the frontend can gate the app."""
    response.headers["Cache-Control"] = "no-store"
    return {"maintenance": maintenance_service.get_public_state()}

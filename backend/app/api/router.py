from fastapi import APIRouter, Depends

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.books import router as books_router
from app.api.bulk import router as bulk_router
from app.api.dashboard import router as dashboard_router
from app.api.deps import require_approved_user
from app.api.extraction import router as extraction_router
from app.api.health import router as health_router
from app.api.metadata import router as metadata_router
from app.api.notifications import router as notifications_router
from app.api.pages import router as pages_router
from app.api.sse import router as sse_router
from app.api.stages import router as stages_router

api_router = APIRouter()
# Liveness must stay unauthenticated so an external monitor can poll it.
api_router.include_router(health_router, tags=["health"])
# /auth/* stays outside the approval gate so pending/rejected users can hold a
# session, refresh it, and log out while they sit on the holding screen.
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
# Include routers with static /books sub-paths (e.g. /books/models) before the
# books router, whose /{book_id} route would otherwise shadow them and 422 on
# UUID validation.
api_router.include_router(
    extraction_router,
    prefix="/books",
    tags=["extraction"],
    dependencies=[Depends(require_approved_user)],
)
api_router.include_router(
    books_router,
    prefix="/books",
    tags=["books"],
    dependencies=[Depends(require_approved_user)],
)
api_router.include_router(
    pages_router,
    prefix="/pages",
    tags=["pages"],
    dependencies=[Depends(require_approved_user)],
)
api_router.include_router(
    metadata_router,
    prefix="/books",
    tags=["metadata"],
    dependencies=[Depends(require_approved_user)],
)
api_router.include_router(
    bulk_router,
    prefix="/bulk",
    tags=["bulk"],
    dependencies=[Depends(require_approved_user)],
)
api_router.include_router(
    dashboard_router,
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_approved_user)],
)
api_router.include_router(
    sse_router, tags=["SSE"], dependencies=[Depends(require_approved_user)]
)
api_router.include_router(
    notifications_router,
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_approved_user)],
)
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(
    stages_router,
    prefix="/books",
    tags=["stages"],
    dependencies=[Depends(require_approved_user)],
)

from fastapi import APIRouter, Depends

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.books import router as books_router
from app.api.bulk import router as bulk_router
from app.api.dashboard import router as dashboard_router
from app.api.deps import get_current_user
from app.api.extraction import router as extraction_router
from app.api.library import router as library_router
from app.api.metadata import router as metadata_router
from app.api.pages import router as pages_router
from app.api.sse import router as sse_router
from app.api.stages import router as stages_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(library_router, prefix="/library", tags=["library"])
# Include routers with static /books sub-paths (e.g. /books/models) before the
# books router, whose /{book_id} route would otherwise shadow them and 422 on
# UUID validation.
api_router.include_router(
    extraction_router,
    prefix="/books",
    tags=["extraction"],
    dependencies=[Depends(get_current_user)],
)
api_router.include_router(books_router, prefix="/books", tags=["books"])
api_router.include_router(
    pages_router,
    prefix="/pages",
    tags=["pages"],
    dependencies=[Depends(get_current_user)],
)
api_router.include_router(
    metadata_router,
    prefix="/books",
    tags=["metadata"],
    dependencies=[Depends(get_current_user)],
)
api_router.include_router(bulk_router, prefix="/bulk", tags=["bulk"])
api_router.include_router(
    dashboard_router, tags=["dashboard"], dependencies=[Depends(get_current_user)]
)
api_router.include_router(
    sse_router, tags=["SSE"], dependencies=[Depends(get_current_user)]
)
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(
    stages_router,
    prefix="/books",
    tags=["stages"],
    dependencies=[Depends(get_current_user)],
)

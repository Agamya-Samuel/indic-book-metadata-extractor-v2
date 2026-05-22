from fastapi import APIRouter

from app.api.books import router as books_router
from app.api.extraction import router as extraction_router
from app.api.library import router as library_router
from app.api.metadata import router as metadata_router
from app.api.pages import router as pages_router

api_router = APIRouter()
api_router.include_router(library_router, prefix="/library", tags=["library"])
api_router.include_router(books_router, prefix="/books", tags=["books"])
api_router.include_router(pages_router, prefix="/pages", tags=["pages"])
api_router.include_router(extraction_router, prefix="/books", tags=["extraction"])
api_router.include_router(metadata_router, prefix="/books", tags=["metadata"])

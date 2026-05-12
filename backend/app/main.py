"""FastAPI application factory and exception handlers.

Run locally (from the ``backend/`` directory):

    uvicorn app.main:app --reload

Exception handlers map ``app.core.exceptions`` to the HTTP status codes
documented in ``docs/00-design/05-api-contract.md``. Layers below
``api/`` never raise FastAPI's ``HTTPException`` directly.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import ops as ops_api
from app.api import upload as upload_api
from app.config import get_settings
from app.core.exceptions import (
    ChunkLimitExceeded,
    EmptyDreamspace,
    EntityNotFound,
    IngestionError,
    LLMUnavailable,
)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="dreamforge",
        version=__version__,
        description=(
            "Backend for dreamforge. Upload documents and (in later phases) "
            "explore the resulting semantic graph. See "
            "docs/00-design/05-api-contract.md for the full contract."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(upload_api.router)
    app.include_router(ops_api.router)

    @app.exception_handler(IngestionError)
    async def _ingestion_422(_request: Request, exc: IngestionError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "IngestionError", "message": str(exc), "details": {}},
        )

    @app.exception_handler(ChunkLimitExceeded)
    async def _chunk_limit_409(
        _request: Request, exc: ChunkLimitExceeded
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": "ChunkLimitExceeded",
                "message": str(exc),
                "details": {
                    "current": exc.current,
                    "incoming": exc.incoming,
                    "limit": exc.limit,
                },
            },
        )

    @app.exception_handler(EmptyDreamspace)
    async def _empty_409(_request: Request, exc: EmptyDreamspace) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": "EmptyDreamspace", "message": str(exc), "details": {}},
        )

    @app.exception_handler(EntityNotFound)
    async def _entity_404(_request: Request, exc: EntityNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": "EntityNotFound",
                "message": str(exc),
                "details": {"entity": exc.entity},
            },
        )

    @app.exception_handler(LLMUnavailable)
    async def _llm_502(_request: Request, exc: LLMUnavailable) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"error": "LLMUnavailable", "message": str(exc), "details": {}},
        )

    return app


app = create_app()

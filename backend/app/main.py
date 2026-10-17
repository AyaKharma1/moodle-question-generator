"""FastAPI application entrypoint.

Wires the routers together, configures CORS for the Vue dev server, sets up
logging that never prints secrets, and installs a safe fallback error handler
so unexpected exceptions return a generic 500 instead of a stack trace.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import auth, documents, export, generation, questions
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app")

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Generate, review, approve and export Moodle-compatible XML questions "
        "from lecture materials. Standalone - no live Moodle connection."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(generation.router)
app.include_router(questions.router)
app.include_router(export.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "ai_provider": settings.ai_provider, "version": __version__}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the detail server-side, return a generic message to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

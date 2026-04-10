"""Presentation — Structured request logging middleware."""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware de logging estruturado para todas as requisições HTTP.
    Registra: método, path, status code, duração e request_id.
    """

    SKIP_PATHS = {"/health", "/", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # Adicionar request_id aos headers de contexto
        request.state.request_id = request_id

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            logger.info(
                "request_started",
                method=request.method,
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown",
            )

            try:
                response = await call_next(request)
            except Exception as exc:
                logger.error(
                    "request_failed",
                    method=request.method,
                    path=request.url.path,
                    error=str(exc),
                )
                raise

            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            response.headers["X-Request-ID"] = request_id
            return response

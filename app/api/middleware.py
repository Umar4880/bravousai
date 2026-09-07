import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Attaches a unique correlation ID to every request.
    Logs method, path, status code, and duration.
    Never logs request body — PII risk.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start = time.perf_counter()

        logger.info(
            "request_start",
            extra={
                "correlation_id": correlation_id,
                "method":         request.method,
                "path":           request.url.path,
                "client_ip":      request.client.host if request.client else "unknown",
            },
        )

        try:
            response = await call_next(request)

        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "request_unhandled_error",
                extra={
                    "correlation_id": correlation_id,
                    "method":         request.method,
                    "path":           request.url.path,
                    "duration_ms":    round(duration_ms, 2),
                    "error":          str(exc),
                },
                exc_info=True,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000

        # Attach headers so frontend/load balancer can trace requests
        response.headers["X-Correlation-Id"]  = correlation_id
        response.headers["X-Response-Time"]   = f"{duration_ms:.2f}ms"

        logger.info(
            "request_end",
            extra={
                "correlation_id": correlation_id,
                "method":         request.method,
                "path":           request.url.path,
                "status_code":    response.status_code,
                "duration_ms":    round(duration_ms, 2),
            },
        )

        return response
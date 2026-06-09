"""
Middleware de gestion globale des exceptions domaine.
Convertit les DomainException en réponses HTTP propres.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.domain.exceptions import DomainException


class DomainExceptionMiddleware(BaseHTTPMiddleware):
    """Intercepte les DomainException et les convertit en réponses HTTP."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except DomainException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )

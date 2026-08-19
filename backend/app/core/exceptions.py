"""Errores de dominio y su traducción a respuestas HTTP.

Todos los errores de la API salen con la MISMA forma, para que el frontend tenga
un solo camino de manejo:

    {"detail": {"code": "...", "message": "...", "hint": "...", "retry_after_seconds": 12}}

`message` va en español y es apto para mostrarle al usuario tal cual.
"""

from typing import Any, Literal

ErrorCode = Literal[
    "invalid_credentials",
    "forbidden",
    "not_found",
    "conflict",
    "validation_error",
    "rate_limited",
    "generation_failed",
    "internal_error",
]


class AppError(Exception):
    """Base de todos los errores esperados de la aplicación."""

    status_code: int = 500
    code: ErrorCode = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.retry_after_seconds = retry_after_seconds

    def to_detail(self) -> dict[str, Any]:
        detail: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.hint:
            detail["hint"] = self.hint
        if self.retry_after_seconds is not None:
            detail["retry_after_seconds"] = self.retry_after_seconds
        return detail


class InvalidCredentials(AppError):
    status_code = 401
    code: ErrorCode = "invalid_credentials"

    def __init__(self, message: str = "Correo o contraseña incorrectos.") -> None:
        super().__init__(message)


class Forbidden(AppError):
    status_code = 403
    code: ErrorCode = "forbidden"

    def __init__(self, message: str = "No tienes permisos para realizar esta acción.") -> None:
        super().__init__(message)


class NotFound(AppError):
    status_code = 404
    code: ErrorCode = "not_found"

    def __init__(self, message: str = "El recurso solicitado no existe.") -> None:
        super().__init__(message)


class Conflict(AppError):
    status_code = 409
    code: ErrorCode = "conflict"


class RateLimited(AppError):
    status_code = 429
    code: ErrorCode = "rate_limited"


class LLMGenerationError(AppError):
    """El modelo falló o devolvió algo que no valida contra el schema."""

    status_code = 502
    code: ErrorCode = "generation_failed"

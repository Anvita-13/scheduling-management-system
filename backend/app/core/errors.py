"""Domain errors raised by the service layer (kept independent of FastAPI/HTTP)."""
from typing import Any, Dict, Optional


class DomainError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, code: Optional[str] = None, extra: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.extra = extra or {}


class NotFoundError(DomainError):
    status_code = 404
    code = "NOT_FOUND"


class ForbiddenError(DomainError):
    status_code = 403
    code = "FORBIDDEN"


class ConflictError(DomainError):
    status_code = 409
    code = "CONFLICT"


class ValidationFailed(DomainError):
    status_code = 422
    code = "VALIDATION_FAILED"

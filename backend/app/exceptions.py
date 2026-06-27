"""
AGRIOS — Exception Definitions and Handlers
All API errors follow the standard envelope:
  { success: false, error: { code: "ERROR_CODE", message: "..." } }

Error codes are defined in the Engineering Constitution.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError


# ── Base Exception ────────────────────────────────────────────────────────────

class AGRIOSException(Exception):
    """Base exception for all AGRIOS business logic errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ── Auth Exceptions ───────────────────────────────────────────────────────────

class UnauthenticatedException(AGRIOSException):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__("UNAUTHENTICATED", message, status.HTTP_401_UNAUTHORIZED)


class ForbiddenException(AGRIOSException):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__("FORBIDDEN", message, status.HTTP_403_FORBIDDEN)


class OTPExpiredException(AGRIOSException):
    def __init__(self) -> None:
        super().__init__("OTP_EXPIRED", "This OTP has expired. Request a new one.")


class OTPInvalidException(AGRIOSException):
    def __init__(self, attempts_remaining: int) -> None:
        super().__init__(
            "OTP_INVALID",
            f"Incorrect code. {attempts_remaining} attempt(s) remaining.",
        )


class OTPMaxAttemptsException(AGRIOSException):
    def __init__(self) -> None:
        super().__init__(
            "OTP_MAX_ATTEMPTS",
            "Too many incorrect attempts. Request a new OTP.",
        )


class RateLimitedException(AGRIOSException):
    def __init__(self, message: str = "Too many requests. Please wait before trying again.") -> None:
        super().__init__("RATE_LIMITED", message, status.HTTP_429_TOO_MANY_REQUESTS)


# ── Resource Exceptions ───────────────────────────────────────────────────────

class NotFoundException(AGRIOSException):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(
            "NOT_FOUND",
            f"{resource} not found.",
            status.HTTP_404_NOT_FOUND,
        )


class ConflictException(AGRIOSException):
    def __init__(self, message: str = "A conflict occurred with an existing resource.") -> None:
        super().__init__("CONFLICT", message, status.HTTP_409_CONFLICT)


class FarmAccessException(AGRIOSException):
    def __init__(self, message: str = "You do not have access to this farm.") -> None:
        super().__init__("FARM_ACCESS_DENIED", message, status.HTTP_403_FORBIDDEN)


class PlanLimitException(AGRIOSException):
    def __init__(self, message: str = "Your current plan limit has been reached.") -> None:
        super().__init__("PLAN_LIMIT", message, status.HTTP_402_PAYMENT_REQUIRED)


class ValidationException(AGRIOSException):
    def __init__(self, message: str = "Validation failed.") -> None:
        super().__init__("VALIDATION_ERROR", message, status.HTTP_422_UNPROCESSABLE_ENTITY)


class QuotaExceededException(AGRIOSException):
    def __init__(self) -> None:
        super().__init__(
            "QUOTA_EXCEEDED",
            "You have reached your ARIA query limit for this month. Upgrade to continue.",
            status.HTTP_402_PAYMENT_REQUIRED,
        )


# ── Exception Handlers ────────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Register all AGRIOS exception handlers on the FastAPI application."""

    @app.exception_handler(AGRIOSException)
    async def agrios_exception_handler(
        request: Request, exc: AGRIOSException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            },
        )

    @app.exception_handler(JWTError)
    async def jwt_exception_handler(
        request: Request, exc: JWTError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": {
                    "code": "UNAUTHENTICATED",
                    "message": "Invalid or expired token.",
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": exc.errors(),
                },
            },
        )

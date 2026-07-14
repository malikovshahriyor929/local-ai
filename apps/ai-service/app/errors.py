from __future__ import annotations

from fastapi import HTTPException


class LocalAIError(Exception):
    def __init__(self, code: str, message: str, details: str = "", retryable: bool = False):
        self.code, self.message, self.details, self.retryable = code, message, details, retryable
        super().__init__(message)

    def body(self) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "details": self.details, "retryable": self.retryable}


def http_error(error: LocalAIError, status_code: int = 503) -> HTTPException:
    return HTTPException(status_code=status_code, detail=error.body())

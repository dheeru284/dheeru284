"""Domain errors raised by services and mapped to HTTP problems by the API layer."""

from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    title = "Bad request"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFound(DomainError):
    status_code = 404
    title = "Not Found"


class Forbidden(DomainError):
    status_code = 403
    title = "Forbidden"


class Conflict(DomainError):
    status_code = 409
    title = "Conflict"


class Unprocessable(DomainError):
    status_code = 422
    title = "Unprocessable content"

from __future__ import annotations


class DomainError(Exception):
    """A command was refused because it would break a product or safety rule.

    `code` is stable and machine-readable (for example `R3_EVIDENCE_REQUIRED`); the API returns it as-is.
    """

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class NotFound(Exception):
    def __init__(self, what: str, ident: str) -> None:
        super().__init__(f"{what} '{ident}' not found")
        self.what = what
        self.ident = ident

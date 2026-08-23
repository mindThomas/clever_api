"""Exceptions for Clever API"""


class CleverError(Exception):
    """Generic Clever exception"""


class CleverConnectionError(CleverError):
    """Clever connection exception"""


class CleverAuthenticationError(CleverError):
    """Firebase authentication or token refresh failed."""


class CleverApiError(CleverError):
    """Clever or Firestore returned an unsuccessful response."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status

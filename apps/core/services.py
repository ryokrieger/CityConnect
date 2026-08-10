"""
Design Pattern 5 — Singleton Pattern
Applied to: application-level service registry.

Shared services like EmailService should be instantiated once per
process. Python's module import system naturally enforces singleton
semantics: `services` below is created once at module load time and
reused on every subsequent `from apps.core.services import services`.
"""

from apps.core.email_service import DjangoEmailAdapter, EmailService


class _ServiceRegistry:
    """
    Singleton service registry. Instantiated once at module load time.
    Import `services` from this module anywhere in the project.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._email = EmailService(DjangoEmailAdapter())
        return cls._instance

    @property
    def email(self) -> EmailService:
        return self._email


# Module-level singleton
services = _ServiceRegistry()

# Usage:
#   from apps.core.services import services
#   services.email.send_welcome(new_user)
"""Singleton Pattern — application-level service registry.

Python's import system runs this module once per process, so the
module-level `services` object is created once and reused everywhere.
"""
from apps.core.email_service import DjangoEmailAdapter, EmailService


class _ServiceRegistry:
    """Instantiated once at import time. Use the `services` object below."""

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
"""Adapter Pattern — email delivery behind a stable interface.

Swapping Django SMTP for SendGrid or SES means writing one new adapter;
no call site changes.
"""
import logging
from abc import ABC, abstractmethod

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class EmailAdapter(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> bool:
        """Send one email; return True on success, False on failure."""


class DjangoEmailAdapter(EmailAdapter):
    def send(self, to: str, subject: str, body: str) -> bool:
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to],
                fail_silently=False,
            )
            return True
        except Exception as exc:  # delivery must never break a request
            logger.error('Email send failed to %s: %s', to, exc)
            return False


class EmailService:
    def __init__(self, adapter: EmailAdapter = None):
        self._adapter = adapter or DjangoEmailAdapter()

    def send_welcome(self, user) -> bool:
        return self._adapter.send(
            to=user.email,
            subject='Welcome to CityConnect!',
            body=f'Hi {user.username}, welcome to your community platform.',
        )

    def send_password_reset(self, user, reset_link: str) -> bool:
        return self._adapter.send(
            to=user.email,
            subject='Reset Your CityConnect Password',
            body=f'Click the link below to reset your password:\n{reset_link}',
        )
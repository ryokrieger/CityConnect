"""
Design Pattern 4 — Adapter Pattern
Applied to: email service integration.

EmailAdapter is the stable interface. DjangoEmailAdapter is today's
concrete implementation (Django SMTP backend). Swapping to SendGrid or SES
later means adding one new adapter class here — EmailService and every
call site stay untouched.
"""

import logging
from abc import ABC, abstractmethod

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class EmailAdapter(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> bool:
        pass


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
        except Exception as e:
            logger.error(f"Email send failed to {to}: {e}")
            return False


class EmailService:
    def __init__(self, adapter: EmailAdapter = None):
        self._adapter = adapter or DjangoEmailAdapter()

    def send_welcome(self, user) -> bool:
        return self._adapter.send(
            to=user.email,
            subject="Welcome to CityConnect!",
            body=f"Hi {user.username}, welcome to your community platform.",
        )

    def send_password_reset(self, user, reset_link: str) -> bool:
        return self._adapter.send(
            to=user.email,
            subject="Reset Your CityConnect Password",
            body=f"Click the link below to reset your password:\n{reset_link}",
        )
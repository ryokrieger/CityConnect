from django.core import mail
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.core.email_service import EmailAdapter, EmailService
from apps.core.services import _ServiceRegistry, services


class ServiceRegistryTests(TestCase):
    def test_registry_is_a_singleton(self):
        self.assertIs(_ServiceRegistry(), services)
        self.assertIs(services.email, _ServiceRegistry().email)


class EmailServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ria', 'ria@example.com', 'pass12345')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_welcome_email_is_sent_through_default_adapter(self):
        self.assertTrue(services.email.send_welcome(self.user))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ria@example.com'])

    def test_adapter_can_be_swapped(self):
        sent = []

        class FakeAdapter(EmailAdapter):
            def send(self, to, subject, body):
                sent.append((to, subject))
                return True

        self.assertTrue(EmailService(FakeAdapter()).send_password_reset(self.user, 'http://x/reset'))
        self.assertEqual(sent, [('ria@example.com', 'Reset Your CityConnect Password')])

    def test_failure_returns_false_instead_of_raising(self):
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
                               EMAIL_HOST='127.0.0.1', EMAIL_PORT=1):
            with self.assertLogs('apps.core.email_service', level='ERROR'):
                self.assertFalse(EmailService().send_welcome(self.user))
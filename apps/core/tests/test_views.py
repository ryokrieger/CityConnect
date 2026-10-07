import re

from django.contrib.messages import constants as message_levels
from django.contrib.staticfiles import finders
from django.contrib.messages.storage.fallback import FallbackStorage
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import User


class PublicPageTests(TestCase):
    def test_home_and_about_render_with_base_layout(self):
        for name in ('core:home', 'core:about'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            self.assertTemplateUsed(response, 'base.html')
            self.assertContains(response, 'Skip to content')

    def test_pages_are_read_only(self):
        for name in ('core:home', 'core:about'):
            self.assertEqual(self.client.post(reverse(name)).status_code, 405, name)

    def test_unbuilt_pages_do_not_break_the_menu(self):
        """Links to pages from later sprints are skipped, not errors."""
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'href="/about/"')
        self.assertNotContains(response, 'Dashboard')

    def test_navigation_marks_current_page(self):
        response = self.client.get(reverse('core:about'))
        self.assertContains(response, 'aria-current="page"', count=1)

    def test_signed_in_user_sees_member_menu_only_for_built_pages(self):
        user = User.objects.create_user('ria', 'ria@example.com', 'pass12345')
        self.client.force_login(user)
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Sign In')


class DesignSystemTests(TestCase):
    def test_rendered_pages_have_no_inline_styles(self):
        for name in ('core:home', 'core:about'):
            html = self.client.get(reverse(name)).content.decode()
            self.assertIsNone(re.search(r'\sstyle\s*=', html), f'inline style in {name}')
            self.assertNotIn('<style', html, name)

    def test_every_linked_stylesheet_and_script_exists(self):
        html = self.client.get(reverse('core:home')).content.decode()
        assets = re.findall(r'(?:href|src)="/static/([^"]+)"', html)
        self.assertGreaterEqual(len(assets), 6)
        for asset in assets:
            self.assertIsNotNone(finders.find(asset), f'missing static file: {asset}')

    def test_default_avatar_exists(self):
        self.assertIsNotNone(finders.find('img/default_avatar.png'))

    def test_css_uses_variables_for_colours(self):
        """Hex colours may only appear in variables.css."""
        for css in ('base', 'layout', 'components', 'forms'):
            path = finders.find(f'css/{css}.css')
            with open(path, encoding='utf-8') as fh:
                source = fh.read()
            self.assertIsNone(re.search(r'#[0-9a-fA-F]{3,8}\b', source), f'hex colour in {css}.css')
            self.assertIsNone(re.search(r'rgba?\(', source), f'raw rgb() in {css}.css')


class FlashMessageTests(TestCase):
    def test_messages_render_with_matching_alert_class(self):
        request = RequestFactory().get('/')
        request.session = {}
        request._messages = FallbackStorage(request)
        request._messages.add(message_levels.ERROR, 'Something went wrong.')
        request._messages.add(message_levels.SUCCESS, 'Saved!')
        request.user = User(username='x')
        html = render_to_string('core/about.html', request=request)
        self.assertIn('alert alert-error', html)
        self.assertIn('alert alert-success', html)
        self.assertIn('Something went wrong.', html)

    def test_message_text_is_escaped(self):
        request = RequestFactory().get('/')
        request.session = {}
        request._messages = FallbackStorage(request)
        request._messages.add(message_levels.INFO, '<script>alert(1)</script>')
        request.user = User(username='x')
        html = render_to_string('core/about.html', request=request)
        self.assertNotIn('<script>alert(1)</script>', html)
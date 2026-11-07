from django.test import TestCase
from django.db import OperationalError
from django.urls import reverse
from django.contrib.auth import get_user_model

from unittest import mock

class HealthCheckTests(TestCase):
    def test_returns_ok_when_database_available(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
        
    def test_returns_503_when_database_unavailable(self):
        with mock.patch("apps.core.views.connection.cursor", side_effect=OperationalError):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        
    def test_does_not_require_sign_in(self):
        response = self.client.get(reverse("health"))
        self.assertNotEqual(response.status_code, 302)

class LayoutTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            "admin2", password="Hero-Snake-1", role=User.Role.ADMINISTRATOR
        )
        self.tech = User.objects.create_user(
            "tech3", password="Shadow-Dog-1", role=User.Role.TECHNICIAN
        )
    
    def test_home_uses_app_layout_and_shows_role(self):
        self.client.force_login(self.tech)
        response = self.client.get(reverse("home"))
        self.assertTemplateUsed(response, "layouts/app.html")
        self.assertContains(response, "Technician")
        
    def test_administrator_menu_only_for_administrators(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("home")), "Administration")
        self.client.force_login(self.tech)
        self.assertNotContains(self.client.get(reverse("home")), "Administration")
        
    def test_sign_out_asks_for_confirmation(self):
        self.client.force_login(self.tech)
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'id="sign-out-modal"')
        
    def test_success_message_is_displayed(self):
        response = self.client.post(
            reverse("sign_in"),
            {"username": "tech3", "password": "Shadow-Dog-1"},
            follow=True,
        )
        self.assertContains(response, "Signed in successfully.")
from django.test import TestCase
from django.db import OperationalError
from django.urls import reverse

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

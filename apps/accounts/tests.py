from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

class SignInTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tech1", password="Correct-Horse-1"
        )
        
    def test_sign_in_page_loads(self):
        response = self.client.get(reverse("sign_in"))
        self.assertEqual(response.status_code, 200)
        
    def test_valid_credentials_sign_in_and_redirect_home(self):
        response = self.client.post(
            reverse("sign_in"), {"username": "tech1", "password": "Correct-Horse-1"}
        )
        self.assertRedirects(response, reverse("home"))
        
    def test_invalid_credentials_show_error(self):
        response = self.client.post(
            reverse("sign_in"), {"username": "tech1", "password": "Wrong"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertTrue(response.context["form"].errors)
    
    def test_home_requires_sign_in(self):
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, f"{reverse('sign_in')}?next=/")
        
    def test_sign_out_signs_user_out(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("sign_out"))
        self.assertRedirects(response, reverse("sign_in"))
        self.assertNotIn("_auth_user_id", self.client.session)    
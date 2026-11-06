from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from apps.accounts.permissions import rule_required


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
        
@rule_required("can_manage_users")
def users_only_view(request):
    """Stand-in view used by these tests"""
    return HttpResponse("ok")

class RoleRuleTests(TestCase):
    def test_rules_for_each_role(self):
        User = get_user_model()
        expected = {
            User.Role.ADMINISTRATOR: {
                "can_manage_users": True, "can_manage_portfolio": True, "can_edit_project_data": True, "can_delete_project_data": True, "can_update_tasks": True,
            },
            User.Role.PROJECT_MANAGER: {
                "can_manage_users": False, "can_manage_portfolio": False, "can_edit_project_data": True, "can_delete_project_data": True, "can_update_tasks": True,
            },
            User.Role.TECHNICIAN: {
                "can_manage_users": False, "can_manage_portfolio": False, "can_edit_project_data": False, "can_delete_project_data": False, "can_update_tasks": True,
            },
        }
        for role, rules in expected.items():
            user = User(username=role, role=role)
            for rule, allowed in rules.items():
                with self.subTest(role=role, rule=rule):
                    self.assertEqual(getattr(user, rule), allowed)
    
    def test_superuser_counts_as_administrator(self):
        user = get_user_model()(username="su", is_superuser=True)
        self.assertTrue(user.can_manage_users)
        
class RuleRequiredTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.factory = RequestFactory()
        self.admin = User.objects.create_user(
            "admin1", password="Chaos-Shark-1", role=User.Role.ADMINISTRATOR
        )
        self.tech = User.objects.create_user(
            "tech2", password="Forge-Lion-1", role=User.Role.TECHNICIAN
        )
        
    def call_view_as(self, user):
        request = self.factory.get("/test/")
        request.user = user
        return users_only_view(request)
    
    def test_allowed_role_reaches_view(self):
        self.assertEqual(self.call_view_as(self.admin).status_code, 200)
        
    def test_other_role_is_refused(self):
        with self.assertRaises(PermissionDenied):
            self.call_view_as(self.tech)
            
    def test_anonymous_user_is_sent_to_sign_in(self):
        response = self.call_view_as(AnonymousUser())
        self.assertEqual(response.status_code, 302)
    
    
    
    
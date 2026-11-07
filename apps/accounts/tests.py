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
    
class CaseInsensitiveUsernameTests(TestCase):
    def test_username_stored_in_lower_case(self):
        user = get_user_model().objects.create_user("MixedCase", password="Mine-Cat-1")
        self.assertEqual(user.username, "mixedcase")
        
    def test_sign_in_ignores_capitalisation(self):
        get_user_model().objects.create_user("tech5", password="Home-Monkey-1")
        response = self.client.post(
            reverse("sign_in"), {"username": "TECH5", "password": "Home-Monkey-1"}
        )
        self.assertRedirects(response, reverse("home"))
        
class ManageUsersTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            "admin3", password="Craft-Fish-1", role=User.Role.ADMINISTRATOR
        )
        self.tech = User.objects.create_user(
            "tech6", password="Ready-Prawn-1", role=User.Role.TECHNICIAN
        )
        
    def test_technician_cannot_open_users_page(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse("user_list")).status_code, 403)
        
    def test_admin_can_create_user(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("user_create"), {
            "username": "NewPM", "first_name": "New", "last_name": "Manager",
            "email": "pm@test.com", "role": "pm",
            "password1": "Strong-Pass-1", "password2": "Strong-Pass-1",
        })
        self.assertRedirects(response, reverse("user_list"))
        self.assertTrue(
            get_user_model().objects.filter(username="newpm", role="pm").exists()
        )
    
    def test_duplicate_username_rejected_whatever_the_case(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("user_create"), {
            "username": "TECH6", "first_name": "tech", "last_name": "6",
            "email": "tech6@test.com", "role": "tech",
            "password1": "Small-Pass-1", "password2": "Small-Pass-1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)
        
    def test_admin_cannot_remove_own_admin_access(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("user_update", args=[self.admin.pk]), {"role": "tech", "is_active": "on"}
        )
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "admin")
    
    def test_last_active_admin_cannot_be_demoted(self):
        superuser = get_user_model().objects.create_superuser("su", password="Wow-Tail-1")
        self.client.force_login(superuser)
        self.client.post(
            reverse("user_update", args=[self.admin.pk]), {"role": "tech", "is_active": "on"}
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "admin")
        
    def test_admin_can_set_password(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("user_set_password", args=[self.tech.pk]), {
            "new_password1": "New-Strong-Pass-1", "new_password2": "New-Strong-Pass-1",
        })
        self.tech.refresh_from_db()
        self.assertTrue(self.tech.check_password("New-Strong-Pass-1"))
        
    def test_delete_asks_for_confirmation(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("user_delete", args=[self.tech.pk]))
        self.assertContains(response, "Are you sure")
        
    def test_admin_can_delete_another_user(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("user_delete", args=[self.tech.pk]))
        self.assertFalse(get_user_model().objects.filter(pk=self.tech.pk).exists())
        
    def test_admin_cannot_delete_own_account(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("user_delete", args=[self.admin.pk]))
        self.assertTrue(get_user_model().objects.filter(pk=self.admin.pk).exists())
        
    
    
    
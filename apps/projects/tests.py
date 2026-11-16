from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.portfolio.gias import run_import
from apps.portfolio.models import School, Trust
from apps.portfolio.tests import OPEN_ACADEMY, make_gias_csv
from apps.projects.models import Project, ProjectSchool

def dfe(row):
    return row["LA (code)"] + row["EstablishmentNumber"]

def shown(row):
    number = dfe(row)
    return f"{number[:3]}/{number[3:]}"

SECOND_SCHOOL = {**OPEN_ACADEMY, "URN": "143999", "EstablishmentNumber": "2999", "EstablishmentName": "Second Primary"}
CLOSED_SCHOOL = {**OPEN_ACADEMY, "URN": "100500", "EstablishmentNumber": "2888", "EstablishmentName": "Closed Infant", "EstablishmentStatus (name)": "Closed", 
                 "CloseDate": "31-08-2020"}
STANDALONE = {**OPEN_ACADEMY, "URN": "100600", "EstablishmentNumber": "2777", "EstablishmentName": "Lone School", "Trusts (code)": "", 
              "Trusts (name)": "", "TrustSchoolFlag (name)": "Not applicable"}

class NewProjectTests(TestCase):
    def setUp(self):
        run_import(
            make_gias_csv([OPEN_ACADEMY, SECOND_SCHOOL, CLOSED_SCHOOL, STANDALONE]), "edubasealldata20261107.csv",
        )
        User = get_user_model()
        self.pm = User.objects.create_user(
            "pm8", email = "pm8@test.com", password = "Bright-Goose-1", role = User.Role.PROJECT_MANAGER, first_name = "Pro", last_name = "ject",
        )
        self.tech = User.objects.create_user(
            "tech8", email = "tech8@test.com", password = "Dark-Swan-1", role = User.Role.TECHNICIAN, first_name = "Tech", last_name = "nician"
        )
        self.client.force_login(self.pm)
        
    def create_url(self, row):
        return f"{reverse('project_create')}?school={dfe(row)}"
    
    def project_data(self, **changes):
        data = {
            "name": "Laptop rollout", "scope": Project.Scope.SCHOOL, "start_date": "2027-01-11", "target_end_date": "2027-02-01", "pm": self.pm.pk
        }
        data.update(changes)
        return data
    
    def test_technicians_cannot_start_a_project(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse("project_customer")).status_code, 403)
        self.assertEqual(self.client.get(self.create_url(OPEN_ACADEMY)).status_code, 403)
    
    def test_valid_dfe_number_is_used(self):
        response = self.client.post(reverse("project_customer"), {"dfe_number": shown(OPEN_ACADEMY)})
        self.assertRedirects(response, self.create_url(OPEN_ACADEMY))
        
    def test_closed_school_is_refused(self):
        response = self.client.post(reverse("project_customer"), {"dfe_number": shown(CLOSED_SCHOOL)})
        self.assertIn("Closed schools can't be added.", response.context["form"].errors["dfe_number"][0])
        
    def test_unknown_dfe_number_is_refused(self):
        response = self.client.post(reverse("project_customer"), {"dfe_number": "999/9999"})
        self.assertContains(response, "No DFE number 999/9999 in the latest GIAS file.")
        
    def test_dfe_number_must_use_the_slash_format(self):
        response = self.client.post(reverse("project_customer"), {"dfe_number": dfe(OPEN_ACADEMY)})
        self.assertContains(response, "Enter the DFE number.")
        
    def test_edited_url_with_unknown_school_goes_back_to_step_one(self):
        response = self.client.get(f"{reverse('project_create')}?school=0000000")
        self.assertRedirects(response, reverse("project_customer"))
        
    def test_Standalone_school_only_offers_single_school(self):
        response = self.client.get(self.create_url(STANDALONE))
        scopes = [value for value, _ in response.context["form"].fields["scope"].choices]
        self.assertEqual(scopes, [Project.Scope.SCHOOL])
    
    def test_single_school_project_copies_school_and_trust(self):
        self.client.post(self.create_url(OPEN_ACADEMY), self.project_data())
        project = Project.objects.get()
        self.assertEqual(project.status, Project.Status.PLANNING)
        self.assertEqual(project.trust.gias_code, int(OPEN_ACADEMY["Trusts (code)"]))
        self.assertEqual([s.dfe_number for s in project.schools.all()], [dfe(OPEN_ACADEMY)])
        
    def test_selected_schools_need_at_least_one(self):
        response = self.client.post(
            self.create_url(OPEN_ACADEMY), self.project_data(scope = Project.Scope.SELECTED)
        )
        self.assertContains(response, "Choose at least one school.")
        self.assertFalse(Project.objects.exists())
        
    def test_selected_schools_links_only_those_ticket(self):
        self.client.post(self.create_url(OPEN_ACADEMY), self.project_data(
            scope = Project.Scope.SELECTED, selected_schools = [dfe(OPEN_ACADEMY), dfe(SECOND_SCHOOL)]
        ))
        self.assertEqual(Project.objects.get().schools.count(), 2)
        
    def test_closed_school_cannot_be_ticked(self):
        response = self.client.post(self.create_url(OPEN_ACADEMY), self.project_data(
            scope = Project.Scope.SELECTED, selected_schools = [dfe(CLOSED_SCHOOL)]
        ))
        self.assertIn("selected_schools", response.context["form"].errors)
        self.assertFalse(Project.objects.exists())
        
    def test_trust_wide_links_every_open_school(self):
        self.client.post(self.create_url(OPEN_ACADEMY), self.project_data(scope = Project.Scope.TRUST_WIDE))
        linked = set(Project.objects.get().schools.values_list("dfe_number", flat = True))
        self.assertEqual(linked, {dfe(OPEN_ACADEMY), dfe(SECOND_SCHOOL)})
        
    def test_central_team_project_has_trust_but_no_schools(self):
        self.client.post(self.create_url(OPEN_ACADEMY), self.project_data(scope = Project.Scope.CENTRAL))
        project = Project.objects.get()
        self.assertIsNotNone(project.trust)
        self.assertEqual(project.schools.count(), 0)
        self.assertFalse(School.objects.exists())
        
    def test_end_date_before_start_is_refused(self):
        response = self.client.post(
            self.create_url(OPEN_ACADEMY), self.project_data(target_end_date = "2027-01-01")
        )
        self.assertContains(response, "Target end date must be on or after the start date.")
        self.assertFalse(Project.objects.exists())
        
    def test_technician_cannot_be_chosen_as_pm(self):
        response = self.client.post(self.create_url(OPEN_ACADEMY), self.project_data(pm=self.tech.pk))
        self.assertIn("pm", response.context["form"].errors)
        self.assertFalse(Project.objects.exists())
        
    def test_nothing_is_created_just_by_opening_the_form(self):
        self.client.get(self.create_url(OPEN_ACADEMY))
        self.assertFalse(School.objects.exists())
        self.assertFalse(Trust.objects.exists())
        
    def trust_url(self, trust_id):
        return f"{reverse('project_create')}?trust={trust_id}"

    def make_trust(self):
        return Trust.objects.create(
            name=OPEN_ACADEMY["Trusts (name)"], gias_code=int(OPEN_ACADEMY["Trusts (code)"]),
            trust_type=Trust.TrustType.MULTI_ACADEMY,
        )

    def test_trust_start_does_not_offer_single_school(self):
        response = self.client.get(self.trust_url(self.make_trust().pk))
        form = response.context["form"]
        scopes = [value for value, _ in form.fields["scope"].choices]
        self.assertNotIn(Project.Scope.SCHOOL, scopes)
        self.assertEqual(form.fields["scope"].initial, Project.Scope.SELECTED)

    def test_unknown_or_invalid_trust_goes_back_to_portfolio(self):
        for trust_id in ("99999", "abc"):
            with self.subTest(trust_id=trust_id):
                self.assertRedirects(self.client.get(self.trust_url(trust_id)), reverse("portfolio"))

    def test_trust_wide_project_from_a_trust_links_its_open_schools(self):
        trust = self.make_trust()
        self.client.post(self.trust_url(trust.pk), self.project_data(scope=Project.Scope.TRUST_WIDE))
        project = Project.objects.get()
        self.assertEqual(project.trust, trust)
        linked = set(project.schools.values_list("dfe_number", flat=True))
        self.assertEqual(linked, {dfe(OPEN_ACADEMY), dfe(SECOND_SCHOOL)})

    def test_single_school_scope_is_refused_from_a_trust(self):
        response = self.client.post(self.trust_url(self.make_trust().pk), self.project_data())
        self.assertIn("scope", response.context["form"].errors)
        self.assertFalse(Project.objects.exists())
        
class ProjectStatusRuleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.pm = User.objects.create_user(
            "pm12", email = "pm12@test.com", password = "Safari-Fantasy-1", role = User.Role.PROJECT_MANAGER
        )
        self.project = Project.objects.create(
            name = "Wifi refresh", scope = Project.Scope.SCHOOL, pm = self.pm, start_date = date(2027, 1, 11), target_end_date = date(2027, 2, 1)
        )
        
    def test_allowed_moves_from_each_status(self):
        S = Project.Status
        expected = {
            S.PLANNING: [S.ACTIVE, S.CANCELLED],
            S.ACTIVE: [S.ON_HOLD, S.AWAITING_SIGN_OFF, S.CANCELLED],
            S.ON_HOLD: [S.ACTIVE, S.CANCELLED],
            S.AWAITING_SIGN_OFF: [S.ACTIVE],
            S.COMPLETED: [S.ACTIVE],
            S.CANCELLED: [S.PLANNING],
        }
        for status, moves in expected.items():
            with self.subTest(status = status):
                self.project.status = status
                self.assertEqual(self.project.next_statuses(), moves)
                
    def test_allowed_move_changes_status(self):
        self.project.move_to(Project.Status.ACTIVE)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.ACTIVE)
        
    def test_illegal_move_is_refused(self):
        with self.assertRaisesMessage(ValueError, "cannot move from Planning to Completed"):
            self.project.move_to(Project.Status.COMPLETED)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.PLANNING)
        
    def test_unknown_status_is_refused(self):
        with self.assertRaisesMessage(ValueError, "That is not a valid project status."):
            self.project.move_to("rabbit")
            
    def test_only_completed_cancelled_are_read_only(self):
        for status in Project.Status:
            with self.subTest(status = status):
                self.project.status = status
                expected = status in (Project.Status.COMPLETED, Project.Status.CANCELLED)
                self.assertEqual(self.project.is_read_only, expected)
    
    def test_cancel_and_reopen_ask_for_confirmation(self):
        self.assertIn("Cancel this project?", self.project.confirmation_for(Project.Status.CANCELLED))
        self.assertIsNone(self.project.confirmation_for(Project.Status.ACTIVE))
        self.project.status = Project.Status.COMPLETED
        self.assertIn("sign-off is kept", self.project.confirmation_for(Project.Status.ACTIVE))
        self.project.status = Project.Status.CANCELLED
        self.assertIn("goes back to Planning", self.project.confirmation_for(Project.Status.PLANNING))
        
class ProjectPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.pm = User.objects.create_user(
            "pm13", email="pm13@test.com", password="Sleep-Floor-1", role=User.Role.PROJECT_MANAGER
        )
        self.tech = User.objects.create_user(
            "tech13", email="tech13@test.com", password="Testify-Panel-1", role=User.Role.TECHNICIAN
        )
        self.school = School.objects.create(name="Beacon High", dfe_number="8874005")
        self.project = Project.objects.create(
            name="Wi-Fi Refresh", scope=Project.Scope.SCHOOL, pm=self.pm,
            start_date=date(2027, 1, 11), target_end_date=date(2027, 2, 1),
        )
        ProjectSchool.objects.create(project=self.project, school=self.school)
        self.client.force_login(self.pm)

    def detail_url(self):
        return reverse("project_detail", args=[self.project.pk])

    def status_url(self):
        return reverse("project_status", args=[self.project.pk])

    def edit_url(self):
        return reverse("project_update", args=[self.project.pk])

    def edit_data(self, **changes):
        data = {"name": "Wi-Fi Refresh", "start_date": "2027-01-11",
                "target_end_date": "2027-02-01", "pm": self.pm.pk}
        data.update(changes)
        return data

    def test_every_role_can_view_a_project(self):
        for user in (self.pm, self.tech):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertContains(self.client.get(self.detail_url()), "Wi-Fi Refresh")

    def test_missing_project_is_not_found(self):
        self.assertEqual(self.client.get(reverse("project_detail", args=[99999])).status_code, 404)

    def test_technicians_see_no_edit_or_status_controls(self):
        self.client.force_login(self.tech)
        response = self.client.get(self.detail_url())
        self.assertNotContains(response, "Change status")
        self.assertNotContains(response, "Edit project")

    def test_pm_can_change_status(self):
        response = self.client.post(self.status_url(), {"status": Project.Status.ACTIVE}, follow=True)
        self.assertContains(response, "Project status changed to Active.")
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.ACTIVE)

    def test_illegal_move_shows_an_error(self):
        response = self.client.post(self.status_url(), {"status": Project.Status.COMPLETED}, follow=True)
        self.assertContains(response, "cannot move from Planning to Completed")
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.PLANNING)

    def test_technicians_cannot_change_status(self):
        self.client.force_login(self.tech)
        response = self.client.post(self.status_url(), {"status": Project.Status.ACTIVE})
        self.assertEqual(response.status_code, 403)

    def test_status_cannot_be_changed_with_get(self):
        self.assertEqual(self.client.get(self.status_url()).status_code, 405)

    def test_pm_can_edit_project_details(self):
        response = self.client.post(self.edit_url(), self.edit_data(name="Wi-Fi Upgrade"))
        self.assertRedirects(response, self.detail_url())
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Wi-Fi Upgrade")

    def test_edit_refuses_end_date_before_start(self):
        response = self.client.post(self.edit_url(), self.edit_data(target_end_date="2027-01-01"))
        self.assertIn("target_end_date", response.context["form"].errors)

    def test_read_only_project_cannot_be_edited(self):
        self.project.status = Project.Status.CANCELLED
        self.project.save()
        response = self.client.post(self.edit_url(), self.edit_data(name="Changed"), follow=True)
        self.assertContains(response, "Reopen this project before editing it.")
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Wi-Fi Refresh")

    def test_technicians_cannot_edit(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(self.edit_url()).status_code, 403)

    def test_edit_keeps_a_pm_whose_role_has_since_changed(self):
        self.pm.role = get_user_model().Role.TECHNICIAN
        self.pm.save()
        self.client.force_login(get_user_model().objects.create_user(
            "admin13", email="admin13@test.com", password="Bright-Kite-1",
            role=get_user_model().Role.ADMINISTRATOR,
        ))
        response = self.client.post(self.edit_url(), self.edit_data(name="Still saves"))
        self.assertRedirects(response, self.detail_url())
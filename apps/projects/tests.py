from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.portfolio.gias import run_import
from apps.portfolio.models import School, Trust
from apps.portfolio.tests import OPEN_ACADEMY, make_gias_csv
from apps.projects.models import Project

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
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.portfolio.gias import run_import
from apps.portfolio.models import School, Trust
from apps.portfolio.tests import OPEN_ACADEMY, make_gias_csv
from apps.projects.models import Project, ProjectSchool, ProjectMember, Milestone, Task, ChecklistItem

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
        
    def test_new_project_saves_team(self):
        self.client.post(self.create_url(OPEN_ACADEMY), self.project_data(tech_lead = self.tech.pk))
        member = Project.objects.get().members.get()
        self.assertEqual((member.user, member.role), (self.tech, ProjectMember.Role.TECH_LEAD))
        
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
        self.admin = User.objects.create_user(
            "admin13", email = "admin13@test.com", password = "Bright-Kite-1", role=User.Role.ADMINISTRATOR
        )
        self.pm = User.objects.create_user(
            "pm13", email = "pm13@test.com", password = "Sleep-Floor-1", role = User.Role.PROJECT_MANAGER
        )
        self.tech = User.objects.create_user(
            "tech13", email = "tech13@test.com", password = "Testify-Panel-1", role = User.Role.TECHNICIAN
        )
        self.school = School.objects.create(name = "Beacon High", dfe_number = "8874005")
        self.project = Project.objects.create(
            name = "Wi-Fi Refresh", scope = Project.Scope.SCHOOL, pm = self.pm,
            start_date = date(2027, 1, 11), target_end_date = date(2027, 2, 1),
        )
        ProjectSchool.objects.create(project = self.project, school = self.school)
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
        self.client.force_login(self.admin)
        response = self.client.post(self.edit_url(), self.edit_data(name="Still saves"))
        self.assertRedirects(response, self.detail_url())
        
class ProjectTeamTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.pm = User.objects.create_user(
            "pm16", email = "pm16@test.com", password = "Half-Kid-1", role = User.Role.PROJECT_MANAGER
        )
        self.lead = User.objects.create_user(
            "tech16a", email = "tech16a@test.com", password = "Rain-Button-1", role = User.Role.TECHNICIAN
        )
        self.tech = User.objects.create_user(
            "tech16b", email = "tech16b@test.com", password = "Fantasy-Fire-1", role = User.Role.TECHNICIAN
        )
        self.project = Project.objects.create(
            name="Wi-Fi Refresh", scope=Project.Scope.SCHOOL, pm=self.pm,
            start_date=date(2027, 1, 11), target_end_date=date(2027, 2, 1),
        )
        self.client.force_login(self.pm)
        
    def edit_url(self):
        return reverse("project_update", args=[self.project.pk])
    
    def edit_data(self, **changes):
        data = {"name": "Wifi refresh", "start_date": "2027-01-11", "target_end_date": "2027-02-01", "pm": self.pm.pk}
        data.update(changes)
        return data
    
    def roles(self):
        return {m.user.username: m.role for m in self.project.members.select_related("user")}
    
    def test_team_is_saved_with_roles(self):
        self.client.post(self.edit_url(), self.edit_data(tech_lead = self.lead.pk, team = [self.tech.pk]))
        self.assertEqual(self.roles(), {"tech16a": "tech_lead", "tech16b": "tech"})

    def test_tech_lead_ticked_in_team_appears_once(self):
        self.client.post(self.edit_url(), self.edit_data(tech_lead = self.lead.pk, team = [self.lead.pk, self.tech.pk]))
        self.assertEqual(self.roles(), {"tech16a": "tech_lead", "tech16b": "tech"})

    def test_pm_can_also_be_tech_lead(self):
        self.client.post(self.edit_url(), self.edit_data(tech_lead = self.pm.pk))
        self.assertEqual(self.roles(), {"pm16": "tech_lead"})

    def test_team_only_lists_technicians(self):
        form = self.client.get(self.edit_url()).context["form"]
        self.assertEqual(set(form.fields["team"].queryset), {self.lead, self.tech})

    def test_editing_replaces_the_team(self):
        ProjectMember.objects.create(project = self.project, user = self.lead, role = ProjectMember.Role.TECH)
        self.client.post(self.edit_url(), self.edit_data(team = [self.tech.pk]))
        self.assertEqual(self.roles(), {"tech16b": "tech"})

    def test_edit_form_shows_the_current_team(self):
        ProjectMember.objects.create(project = self.project, user = self.lead, role = ProjectMember.Role.TECH_LEAD)
        ProjectMember.objects.create(project = self.project, user = self.tech, role = ProjectMember.Role.TECH)
        form = self.client.get(self.edit_url()).context["form"]
        self.assertEqual(form.fields["tech_lead"].initial, self.lead.pk)
        self.assertEqual(form.fields["team"].initial, [self.tech.pk])

    def test_deactivated_member_does_not_block_editing(self):
        ProjectMember.objects.create(project = self.project, user = self.tech, role = ProjectMember.Role.TECH)
        self.tech.is_active = False
        self.tech.save()
        response = self.client.post(self.edit_url(), self.edit_data(name = "Still saves", team = [self.tech.pk]))
        self.assertRedirects(response, reverse("project_detail", args = [self.project.pk]))

    def test_database_allows_only_one_tech_lead(self):
        ProjectMember.objects.create(project = self.project, user = self.lead, role = ProjectMember.Role.TECH_LEAD)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectMember.objects.create(project = self.project, user = self.tech, role = ProjectMember.Role.TECH_LEAD)

    def test_project_page_shows_the_team(self):
        ProjectMember.objects.create(project = self.project, user = self.lead, role = ProjectMember.Role.TECH_LEAD)
        ProjectMember.objects.create(project = self.project, user = self.tech, role = ProjectMember.Role.TECH)
        response = self.client.get(reverse("project_detail", args = [self.project.pk]))
        self.assertContains(response, "tech16a")
        self.assertContains(response, "tech16b")

    def test_project_page_says_when_there_is_no_team(self):
        response = self.client.get(reverse("project_detail", args = [self.project.pk]))
        self.assertContains(response, "No techs yet")
        
class MilestoneTests(TestCase):
    
    def setUp(self):
        User = get_user_model()
        self.pm = User.objects.create_user(
            "pm17", email="pm17@test.com", password="Curve-Outlet-1", role=User.Role.PROJECT_MANAGER
        )
        self.tech = User.objects.create_user(
            "tech17", email="tech17@test.com", password="Menu-Source-1", role=User.Role.TECHNICIAN
        )
        self.outsider = User.objects.create_user(
            "tech18", email="tech18@test.com", password="Battery-Cycle-1", role=User.Role.TECHNICIAN
        )
        self.school = School.objects.create(name="Beacon High", dfe_number="8874005")
        self.project = Project.objects.create(
            name="Wi-Fi Refresh", scope=Project.Scope.SCHOOL, pm=self.pm,
            start_date=date(2027, 1, 4), target_end_date=date(2027, 3, 31),
        )
        ProjectSchool.objects.create(project=self.project, school=self.school)
        ProjectMember.objects.create(project=self.project, user=self.tech, role=ProjectMember.Role.TECH)
        self.milestone = Milestone.objects.create(project=self.project, name="Install", due_date=date(2027, 2, 26))
        self.client.force_login(self.pm)

    def make_task(self, **changes):
        fields = {"project": self.project, "school": self.school, "title": "Mount APs",
                  "start_date": date(2027, 1, 11), "due_date": date(2027, 1, 15),
                  "where": Task.Where.REMOTE}
        fields.update(changes)
        return Task.objects.create(**fields)
    
    def add(self, **data):
        return self.client.post(reverse("milestone_create", args=[self.project.pk]),
                                {"name": "Handover", "due_date": "2027-03-26", **data})

    def test_pm_can_add_a_milestone(self):
        self.add()
        self.assertTrue(self.project.milestones.filter(name="Handover").exists())

    def test_technicians_cannot_add_milestones(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.add().status_code, 403)

    def test_due_date_must_be_within_the_project(self):
        response = self.add(due_date="2027-05-01")
        self.assertIn("Milestone dates must fall within the project", response.context["form"].errors["due_date"][0])

    def test_duplicate_name_is_refused_whatever_the_case(self):
        response = self.add(name="INSTALL")
        self.assertIn(f"already exists", response.context["form"].errors["name"][0])

    def test_ticking_completes_and_unticking_reopens(self):
        url = reverse("milestone_toggle", args=[self.milestone.pk])
        self.client.post(url)
        self.milestone.refresh_from_db()
        self.assertEqual((self.milestone.status, self.milestone.completed_by), ("done", self.pm))
        self.client.post(url)
        self.milestone.refresh_from_db()
        self.assertIsNone(self.milestone.completed_at)

    def test_deleting_a_milestone_keeps_its_tasks(self):
        task = self.make_task(milestone=self.milestone)
        self.client.post(reverse("milestone_delete", args=[self.milestone.pk]))
        task.refresh_from_db()
        self.assertIsNone(task.milestone)

    def test_status_is_worked_out_from_dates(self):
        today = timezone.localdate()
        self.assertEqual(Milestone(due_date=today + timedelta(days=1)).status, "open")
        self.assertEqual(Milestone(due_date=today - timedelta(days=1)).status, "overdue")
        self.assertEqual(Milestone(due_date=today, completed_at=timezone.now()).status, "done")

    def test_closed_project_refuses_new_milestones(self):
        self.project.status = Project.Status.CANCELLED
        self.project.save()
        response = self.add()
        self.assertRedirects(response, reverse("project_detail", args=[self.project.pk]))
        self.assertFalse(self.project.milestones.filter(name="Handover").exists())
        
class TaskFormTests(TestCase):
    
    def setUp(self):
        User = get_user_model()
        self.pm = User.objects.create_user(
            "pm18", email="pm17@test.com", password="Cave-Doctor-1", role=User.Role.PROJECT_MANAGER
        )
        self.tech = User.objects.create_user(
            "tech18", email="tech17@test.com", password="Step-Lamp-1", role=User.Role.TECHNICIAN
        )
        self.outsider = User.objects.create_user(
            "tech19", email="tech18@test.com", password="Vison-Mold-1", role=User.Role.TECHNICIAN
        )
        self.school = School.objects.create(name="Beacon High", dfe_number="8874005")
        self.project = Project.objects.create(
            name="Wi-Fi Refresh", scope=Project.Scope.SCHOOL, pm=self.pm,
            start_date=date(2027, 1, 4), target_end_date=date(2027, 3, 31),
        )
        ProjectSchool.objects.create(project=self.project, school=self.school)
        ProjectMember.objects.create(project=self.project, user=self.tech, role=ProjectMember.Role.TECH)
        self.milestone = Milestone.objects.create(project=self.project, name="Install", due_date=date(2027, 2, 26))
        self.client.force_login(self.pm)

    def make_task(self, **changes):
        fields = {"project": self.project, "school": self.school, "title": "Mount APs",
                  "start_date": date(2027, 1, 11), "due_date": date(2027, 1, 15),
                  "where": Task.Where.REMOTE}
        fields.update(changes)
        return Task.objects.create(**fields)
    
    def task_data(self, checklist=(), **changes):
        data = {
            "school": self.school.pk, "milestone": self.milestone.pk, "title": "Mount APs",
            "priority": Task.Priority.NORMAL, "start_date": "2027-01-11", "due_date": "2027-01-15",
            "where": Task.Where.REMOTE, "assignees": [self.tech.pk],
            "checklist_items-TOTAL_FORMS": "3", "checklist_items-INITIAL_FORMS": "0",
            "checklist_items-MIN_NUM_FORMS": "0", "checklist_items-MAX_NUM_FORMS": "1000",
        }
        for index, text in enumerate(checklist):
            data[f"checklist_items-{index}-text"] = text
        data.update(changes)
        return data

    def create(self, **kwargs):
        return self.client.post(reverse("task_create", args=[self.project.pk]), self.task_data(**kwargs))

    def errors(self, response):
        return response.context["form"].errors

    def test_task_is_created_with_assignees_and_checklist(self):
        response = self.create(checklist=["Label leads", "Test ports"])
        task = Task.objects.get()
        self.assertRedirects(response, f"{reverse('project_detail', args=[self.project.pk])}?tab=tasks")
        self.assertEqual(list(task.assignees.all()), [self.tech])
        self.assertEqual([item.text for item in task.checklist_items.all()], ["Label leads", "Test ports"])

    def test_blank_checklist_rows_are_ignored(self):
        self.create(checklist=["Only one"])
        self.assertEqual(ChecklistItem.objects.count(), 1)

    def test_dates_must_be_within_the_project_and_in_order(self):
        self.assertIn("start_date", self.errors(self.create(start_date="2026-12-01")))
        self.assertIn("due_date", self.errors(self.create(start_date="2027-01-15", due_date="2027-01-11")))

    def test_times_are_both_or_neither_and_in_order(self):
        self.assertIn("end_time", self.errors(self.create(start_time="09:00")))
        self.assertIn("end_time", self.errors(self.create(start_time="13:00", end_time="12:00")))

    def test_on_site_needs_a_location(self):
        self.assertIn("location", self.errors(self.create(where=Task.Where.ON_SITE)))

    def test_only_this_projects_choices_are_accepted(self):
        other_school = School.objects.create(name="Elsewhere", dfe_number="8870001")
        self.assertIn("school", self.errors(self.create(school=other_school.pk)))
        self.assertIn("assignees", self.errors(self.create(assignees=[self.outsider.pk])))
        self.assertFalse(Task.objects.exists())

    def test_editing_can_remove_a_checklist_item(self):
        task = self.make_task()
        item = ChecklistItem.objects.create(task=task, text="Old item")
        data = self.task_data(**{
            "checklist_items-TOTAL_FORMS": "1", "checklist_items-INITIAL_FORMS": "1",
            "checklist_items-0-id": item.pk, "checklist_items-0-text": "Old item",
            "checklist_items-0-DELETE": "on",
        })
        self.client.post(reverse("task_update", args=[task.pk]), data)
        self.assertFalse(task.checklist_items.exists())

    def test_task_can_be_deleted(self):
        task = self.make_task()
        self.client.post(reverse("task_delete", args=[task.pk]))
        self.assertFalse(Task.objects.exists())

    def test_technicians_cannot_open_the_task_form(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse("task_create", args=[self.project.pk])).status_code, 403)
        
class TaskProgressTests(TestCase):
    
    def setUp(self):
        User = get_user_model()
        self.pm = User.objects.create_user(
            "pm19", email="pm17@test.com", password="Matter-Maid-1", role=User.Role.PROJECT_MANAGER
        )
        self.tech = User.objects.create_user(
            "tech20", email="tech17@test.com", password="Lick-Match-1", role=User.Role.TECHNICIAN
        )
        self.outsider = User.objects.create_user(
            "tech21", email="tech18@test.com", password="Curtain-Sail-1", role=User.Role.TECHNICIAN
        )
        self.school = School.objects.create(name="Beacon High", dfe_number="8874005")
        self.project = Project.objects.create(
            name="Wi-Fi Refresh", scope=Project.Scope.SCHOOL, pm=self.pm,
            start_date=date(2027, 1, 4), target_end_date=date(2027, 3, 31),
        )
        ProjectSchool.objects.create(project=self.project, school=self.school)
        ProjectMember.objects.create(project=self.project, user=self.tech, role=ProjectMember.Role.TECH)
        self.milestone = Milestone.objects.create(project=self.project, name="Install", due_date=date(2027, 2, 26))
        self.client.force_login(self.pm)

    def make_task(self, **changes):
        fields = {"project": self.project, "school": self.school, "title": "Mount APs",
                  "start_date": date(2027, 1, 11), "due_date": date(2027, 1, 15),
                  "where": Task.Where.REMOTE}
        fields.update(changes)
        return Task.objects.create(**fields)
    
    def toggle(self, task, **data):
        return self.client.post(reverse("task_toggle", args=[task.pk]), data)

    def test_ticking_marks_done_and_unticking_reopens(self):
        task = self.make_task()
        self.toggle(task)
        task.refresh_from_db()
        self.assertTrue(task.is_done)
        self.assertIsNotNone(task.completed_at)
        self.toggle(task)
        task.refresh_from_db()
        self.assertEqual((task.status, task.completed_at), (Task.Status.TO_DO, None))

    def test_assigned_tech_can_tick_but_others_cannot(self):
        task = self.make_task()
        task.assignees.add(self.tech)
        self.client.force_login(self.tech)
        self.toggle(task)
        task.refresh_from_db()
        self.assertTrue(task.is_done)
        self.client.force_login(self.outsider)
        self.assertEqual(self.toggle(task).status_code, 403)

    def test_tick_returns_to_the_page_it_came_from_but_not_other_sites(self):
        task = self.make_task()
        here = f"{reverse('project_detail', args=[self.project.pk])}?tab=tasks&status=all"
        self.assertRedirects(self.toggle(task, next=here), here)
        response = self.toggle(task, next="https://evil.example/")
        self.assertEqual(response.url, f"{reverse('project_detail', args=[self.project.pk])}?tab=tasks")

    def test_progress_counts_done_tasks(self):
        self.make_task().mark_done()
        self.make_task()
        progress = self.client.get(reverse("project_detail", args=[self.project.pk])).context["progress"]
        self.assertEqual(progress, {"done": 1, "total": 2, "percent": 50})

    def test_tasks_are_grouped_by_milestone_with_no_milestone_last(self):
        self.make_task(milestone=self.milestone, title="In milestone")
        self.make_task(title="Loose")
        groups = self.client.get(
            reverse("project_detail", args=[self.project.pk]), {"tab": "tasks"}
        ).context["groups"]
        self.assertEqual([g["milestone"] for g in groups], [self.milestone, None])
        self.assertEqual([t.title for t in groups[1]["tasks"]], ["Loose"])

    def test_open_filter_hides_done_tasks(self):
        self.make_task(title="Finished").mark_done()
        self.make_task(title="Still open")
        groups = self.client.get(
            reverse("project_detail", args=[self.project.pk]), {"tab": "tasks", "status": "open"}
        ).context["groups"]
        shown = [t.title for g in groups for t in g["tasks"]]
        self.assertEqual(shown, ["Still open"])

    def test_project_dates_cannot_leave_tasks_outside(self):
        self.make_task(due_date=date(2027, 3, 20))
        response = self.client.post(reverse("project_update", args=[self.project.pk]), {
            "name": "Wi-Fi Refresh", "start_date": "2027-01-04", "target_end_date": "2027-03-01", "pm": self.pm.pk,
        })
        self.assertIn("1 task falls outside", response.context["form"].errors["start_date"][0])
        

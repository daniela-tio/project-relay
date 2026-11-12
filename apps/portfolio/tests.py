import csv
import io
import tempfile
from datetime import date
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from urllib.parse import urlencode
from unittest import mock
from apps.portfolio.models import School, Trust, GiasEstablishment, GiasImport
from apps.portfolio.gias import REQUIRED_COLUMNS, GiasFileError, file_date_from_name, load_establishments, run_import
from apps.portfolio.services import add_school_from_gias, build_portfolio
from apps.projects.models import Project, ProjectSchool


class SchoolModelTests(TestCase):
    def setUp(self):
        self.trust = Trust.objects.create(
            name = "Temp Academy Trust", gias_code = 1234, trust_type=Trust.TrustType.MULTI_ACADEMY
        )
        self.school = School.objects.create(
            name="Temp Primary", dfe_number = "2034257", trust=self.trust
        )
    
    def test_dfe_number_displayed_with_slash(self):
        self.assertEqual(self.school.formatted_dfe_number, "203/4257")
        
    def test_database_rejects_incorrectly_formatted_dfe_number(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                School.objects.create(name = "Incorrect Number", dfe_number="203/425")
                
    def test_database_rejects_duplicate_dfe_number(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                School.objects.create(name = "Duplicate Number", dfe_number="2034257")
                
    def test_trust_with_schools_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.trust.delete()
        self.assertTrue(Trust.objects.filter(pk=self.trust.pk).exists())
        
class TrustModelTests(TestCase):
    def test_display_name_falls_back_to_full_name(self):
        trust = Trust(name = "Test Learning Trust")
        self.assertEqual(trust.display_name, "Test Learning Trust")
    
    def test_display_name_uses_short_name_when_set(self):
        trust = Trust(name = "Test Learning Trust", short_name = "Test LT")
        self.assertEqual(trust.display_name, "Test LT")
        
def make_gias_csv(rows, columns=REQUIRED_COLUMNS):
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return io.BytesIO(text.getvalue().encode("cp1252"))

OPEN_ACADEMY = {
    "URN": "1946823", "LA (code)": "203", "EstablishmentNumber": "2026",
    "EstablishmentName": "Test Primary School",
    "EstablishmentStatus (name)": "Open", "PhaseOfEducation (name)": "Primary",
    "Town": "London", "Postcode": "SE10 0BG",
    "Trusts (code)": "5102", "Trusts (name)": "Northfield Learning Trust",
    "TrustSchoolFlag (name)": "Supported by a multi-academy trust",
}

class GiasImportTests(TestCase):
    def test_missing_colum_is_rejected(self):
        columns = [c for c in REQUIRED_COLUMNS if c != "LA (code)"]
        with self.assertRaisesMessage(GiasFileError, 'missing column "LA (code)"'):
            load_establishments(make_gias_csv([OPEN_ACADEMY], columns))
    
    def test_rows_are_saved_with_mapped_values(self):
        load_establishments(make_gias_csv([OPEN_ACADEMY]))
        school = GiasEstablishment.objects.get(urn=1946823)
        self.assertEqual(school.dfe_number, "2032026")
        self.assertEqual(school.status, School.Status.OPEN)
        self.assertEqual(school.trust_code, 5102)
        self.assertEqual(school.trust_type, Trust.TrustType.MULTI_ACADEMY)
        
    def test_closed_date_is_parsed(self):
        closed = {**OPEN_ACADEMY, "URN": "100111", "EstablishmentStatus (name)": "Closed", "CloseDate": "31-08-2019"}
        load_establishments(make_gias_csv([closed]))
        self.assertEqual(GiasEstablishment.objects.get(urn=100111).close_date, date(2019, 8, 31))
        
    def test_rows_without_dfe_number_skipped_but_counted(self):
        university = {**OPEN_ACADEMY, "URN": "133768", "EstablishmentNumber": ""}
        rows_read = load_establishments(make_gias_csv([OPEN_ACADEMY, university]))
        self.assertEqual(rows_read, 2)
        self.assertEqual(GiasEstablishment.objects.count(), 1)
        
    def test_new_import_replaces_the_previous_one(self):
        load_establishments(make_gias_csv([OPEN_ACADEMY]))
        other = {**OPEN_ACADEMY, "URN": "143601", "EstablishmentNumber": "2024"}
        load_establishments(make_gias_csv([other]))
        self.assertEqual(list(GiasEstablishment.objects.values_list("urn", flat=True)), [143601])
        
    def test_failed_import_keeps_existing_data(self):
        load_establishments(make_gias_csv([OPEN_ACADEMY]))
        with self.assertRaises(GiasFileError):
            load_establishments(make_gias_csv([OPEN_ACADEMY], ["URN"]))
        self.assertEqual(GiasEstablishment.objects.count(), 1)
        
    def test_accented_names_read_correctly(self):
        welsh = {**OPEN_ACADEMY, "EstablishmentName": "Ysgol Gymraeg Brynsierfel - Ffôr"}
        load_establishments(make_gias_csv([welsh]))
        self.assertEqual(GiasEstablishment.objects.get().name, "Ysgol Gymraeg Brynsierfel - Ffôr")
        
    def test_file_date_is_read_from_file_name(self):
        self.assertEqual(file_date_from_name("edubasealldata20261107.csv"), date(2026, 11, 7))
        self.assertIsNone(file_date_from_name("schools.csv"))
        
    def test_run_import_records_success(self):
        record = run_import(make_gias_csv([OPEN_ACADEMY]), "edubasealldata20261107.csv")
        self.assertEqual(record.status, GiasImport.Status.SUCCEEDED)
        self.assertEqual(record.rows_read, 1)
        self.assertEqual(record.file_date, date(2026, 11, 7))
        self.assertIsNotNone(record.finished_at)
        
    def test_run_import_records_failure(self):
        record = run_import(make_gias_csv([OPEN_ACADEMY], ["URN"]), "bad.csv")
        self.assertEqual(record.status, GiasImport.Status.FAILED)
        self.assertIn("missing column", record.error_summary)
        self.assertIsNotNone(record.finished_at)
        
    def test_bad_row_gives_readable_error_and_keeps_data(self):
        load_establishments(make_gias_csv([OPEN_ACADEMY]))
        bad = {**OPEN_ACADEMY, "URN": "9999999", "EstablishmentStatus (name)": "Randomness"}
        with self.assertRaisesMessage(GiasFileError, "row 2"):
            load_establishments(make_gias_csv([bad]))
        self.assertEqual(GiasEstablishment.objects.count(), 1)
        
    def test_command_imports_file(self):
        with tempfile.NamedTemporaryFile(suffix = ".csv", delete_on_close = False) as csv_file:
            csv_file.write(make_gias_csv([OPEN_ACADEMY]).getvalue())
            csv_file.close()
            call_command("import_gias", csv_file.name, stdout=io.StringIO())
        self.assertTrue(GiasEstablishment.objects.filter(urn=1946823).exists())
        
    def test_command_reports_failure(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete_on_close=False) as csv_file:
            csv_file.write(make_gias_csv([OPEN_ACADEMY], ["URN"]).getvalue())
            csv_file.close()
            with self.assertRaisesMessage(CommandError, "missing column"):
                call_command("import_gias", csv_file.name, stdout=io.StringIO())
                
class GiasImportPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            "admin7", email = "admin7@test.com", password = "Bright-Kite-1", role = User.Role.ADMINISTRATOR
        )
        self.pm = User.objects.create_user(
            "pm7", email = "pm7@test.com", password = "Bright-Kite-1", role = User.Role.PROJECT_MANAGER
        )
        self.tech = User.objects.create_user(
            "tech7", email = "tech7@test.com", password = "Bright-Kite-1", role = User.Role.TECHNICIAN
        )
        
    def upload(self, name="edubasealldata20261107.csv", rows=(OPEN_ACADEMY,)):
        return SimpleUploadedFile(name, make_gias_csv(list(rows)).getvalue(), content_type="text/csv")
    
    def test_only_administrators_can_open_the_page(self):
        for user, status in [(self.tech, 403), (self.pm, 403), (self.admin, 200)]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse("gias_import")).status_code, status)
    
    def test_valid_upload_imports_and_redirects(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("gias_import"), {"csv_file": self.upload()})
        self.assertRedirects(response, reverse("gias_import"))
        record = GiasImport.objects.get()
        self.assertEqual(record.status, GiasImport.Status.SUCCEEDED)
        self.assertEqual(record.uploaded_by, self.admin)
        self.assertEqual(GiasEstablishment.objects.count(), 1)
        
    def test_non_csv_file_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("gias_import"), {"csv_file": self.upload(name = "schools.txt")})
        self.assertContains(response, "The file must be a .csv file.")
        self.assertFalse(GiasImport.objects.exists())
        
    def test_upload_refused_while_an_import_is_running(self):
        GiasImport.objects.create(file_name = "other.csv", status = GiasImport.Status.RUNNING)
        self.client.force_login(self.admin)
        response = self.client.post(reverse("gias_import"), {"csv_file": self.upload()}, follow=True)
        self.assertContains(response, "An import is already running.")
        self.assertEqual(GiasEstablishment.objects.count(), 0)
        
    def test_unexpected_error_marks_import_failed(self):
        with mock.patch(
            "apps.portfolio.gias.load_establishments", 
            side_effect=RuntimeError("boom"),
            ):
                with self.assertRaises(RuntimeError):
                    run_import(make_gias_csv([OPEN_ACADEMY]), "edubasealldata20261107.csv")
        self.assertEqual(GiasImport.objects.get().status, GiasImport.Status.FAILED)
        
class GiasServiceTests(TestCase):
    def setUp(self):
        load_establishments(make_gias_csv([OPEN_ACADEMY]))
        self.establishment = GiasEstablishment.objects.get(urn="1946823")
    
    def test_school_is_copied_with_its_trust(self):
        school = add_school_from_gias(self.establishment)
        expected_dfe = OPEN_ACADEMY["LA (code)"] + OPEN_ACADEMY["EstablishmentNumber"]
        self.assertEqual(school.dfe_number, expected_dfe)
        self.assertFalse(school.is_manual)
        self.assertEqual(school.trust.gias_code, int(OPEN_ACADEMY["Trusts (code)"]))
        self.assertEqual(school.trust.name, OPEN_ACADEMY["Trusts (name)"])
    
    def test_existing_school_is_reused_not_duplicated(self):
        first = add_school_from_gias(self.establishment)
        second = add_school_from_gias(self.establishment)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(School.objects.count(), 1)
        
    def test_existing_trust_is_reused(self):
        Trust.objects.create(name = "Northfield LT", gias_code = 5102, trust_type = Trust.TrustType.MULTI_ACADEMY)
        add_school_from_gias(self.establishment)
        self.assertEqual(Trust.objects.count(), 1)
        
    def test_standalone_school_has_no_trust(self):
        standalone = {**OPEN_ACADEMY, "URN": "100200", "EstablishmentNumber": "2100", "Trusts (code)": "", "Trusts (name)": "", "TrustSchoolFlag (name)": "Not applicable"}
        load_establishments(make_gias_csv([standalone]))
        school = add_school_from_gias(GiasEstablishment.objects.get(urn=100200))
        self.assertIsNone(school.trust)
        
class ManualSchoolAndTrustTests(TestCase):
    def setUp(self):
        run_import(make_gias_csv([OPEN_ACADEMY]), "edubasealldata20261107.csv")
        User = get_user_model()
        self.pm = User.objects.create_user(
            "pm9", email="pm9@test.com", password="Dark-Kite-1", role=User.Role.PROJECT_MANAGER
        )
        self.tech = User.objects.create_user(
            "tech9", email="tech9@test.com", password="Slow-Hand-1", role=User.Role.TECHNICIAN
        )
        self.client.force_login(self.pm)
        
    def school_data(self, **changes):
        data = {"name": "Elmstead Primary", "dfe_number": "302/2002", "trust": "", "phase": "Primary", "town": "Elmstead", "postcode": "nf42hp"}
        data.update(changes)
        return data
    
    def trust_data(self, **changes):
        data = {"name": "Elmstead Trust", "short_name": "Elmstead", "trust_type": Trust.TrustType.MULTI_ACADEMY, "gias_code": ""}
        data.update(changes)
        return data
    
    def test_technicians_cannot_add_school_or_trusts(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse("school_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("trust_create")).status_code, 403)
        
    def test_dfe_number_is_carried_over(self):
        response = self.client.get(f"{reverse('school_create')}?dfe=302/2002")
        self.assertEqual(response.context["form"].initial["dfe_number"], "302/2002")
        
    def test_manual_school_is_saved_and_goes_to_project_form(self):
        response = self.client.post(reverse("school_create"), self.school_data())
        school = School.objects.get()
        self.assertTrue(school.is_manual)
        self.assertEqual(school.dfe_number, "3022002")
        self.assertEqual(school.postcode, "NF4 2HP")
        self.assertRedirects(response, f"{reverse('project_create')}?school=3022002")
        
    def test_gias_school_cannot_be_added_by_hand(self):
        gias_number = OPEN_ACADEMY["LA (code)"] + "/" + OPEN_ACADEMY["EstablishmentNumber"]
        response = self.client.post(reverse("school_create"), self.school_data(dfe_number = gias_number))
        self.assertIn("This school already exists. Please look it by its DFE number.", response.context["form"].errors["dfe_number"][0])
        self.assertFalse(School.objects.exists())
 
    def test_duplicate_dfe_number_is_refused(self):
        School.objects.create(name = "Existing", dfe_number = "3022002", is_manual=True)
        response = self.client.post(reverse("school_create"), self.school_data())
        self.assertIn("dfe_number", response.context["form"].errors)
        self.assertEqual(School.objects.count(), 1)

    def test_bad_postcode_is_refused(self):
        response = self.client.post(reverse("school_create"), self.school_data(postcode = "12345"))
        self.assertEqual(
            response.context["form"].errors["postcode"], ["Enter a real UK postcode."]
        )

    def test_manual_trust_is_saved_and_returns_to_school_form(self):
        response = self.client.post(f"{reverse('trust_create')}?dfe=302/2002", self.trust_data())
        trust = Trust.objects.get()
        self.assertTrue(trust.is_manual)
        query = urlencode({"trust": trust.pk, "dfe": "302/2002"})
        self.assertRedirects(response, f"{reverse('school_create')}?{query}")

    def test_new_trust_is_selected_on_the_school_form(self):
        trust = Trust.objects.create(
            name = "Elmstead Trust", short_name = "Elmstead", trust_type = Trust.TrustType.MULTI_ACADEMY, is_manual = True
        )
        response = self.client.get(f"{reverse('school_create')}?trust={trust.pk}")
        self.assertEqual(str(response.context["form"].initial["trust"]), str(trust.pk))

    def test_duplicate_trust_name_is_refused_whatever_the_case(self):
        Trust.objects.create(name = "Elmstead Trust", trust_type = Trust.TrustType.MULTI_ACADEMY, is_manual = True)
        response = self.client.post(reverse("trust_create"), self.trust_data(name = "ELMSTEAD TRUST"))
        self.assertIn("name", response.context["form"].errors)
        self.assertEqual(Trust.objects.count(), 1)

    def test_duplicate_trust_code_is_refused(self):
        Trust.objects.create(name = "Other Trust", gias_code = 4877, trust_type = Trust.TrustType.MULTI_ACADEMY)
        response = self.client.post(reverse("trust_create"), self.trust_data(gias_code = "4877"))
        self.assertIn("gias_code", response.context["form"].errors)

    def test_short_name_is_required(self):
        response = self.client.post(reverse("trust_create"), self.trust_data(short_name = ""))
        self.assertEqual(
            response.context["form"].errors["short_name"], ["Enter a short name of up to 30 characters."]
        )

    def test_project_can_start_from_a_manual_school(self):
        School.objects.create(name = "Elmstead Primary", dfe_number = "3022002", is_manual = True)
        response = self.client.post(reverse("project_customer"), {"dfe_number": "302/2002"})
        self.assertRedirects(response, f"{reverse('project_create')}?school=3022002")       
        
class PortfolioTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.pm = User.objects.create_user(
            "pm10", email="pm10@test.com", password="Print-Norm-1", role=User.Role.PROJECT_MANAGER
        )
        self.tech = User.objects.create_user(
            "tech10", email="tech10@test.com", password="Eye-Fax-1", role=User.Role.TECHNICIAN
        )
        self.trust = Trust.objects.create(
            name="Northfield Learning Trust", gias_code=5102, trust_type=Trust.TrustType.MULTI_ACADEMY
        )
        self.oakfield = School.objects.create(
            name="Oakfield Primary", dfe_number="8862014", trust=self.trust, postcode="NF4 2HP"
        )
        self.riverside = School.objects.create(
            name="Riverside Academy", dfe_number="8864021", trust=self.trust
        )
        self.beacon = School.objects.create(name="Beacon High", dfe_number="8874005")
    
    def make_project(self, schools = (), trust = None, status = Project.Status.PLANNING, scope = Project.Scope.SCHOOL):
        project = Project.objects.create(
            name = "Test Project", scope = scope, trust = trust, status = status, pm = self.pm, start_date = date(2027, 1 , 11), target_end_date = date(2027, 2 , 1)
        )
        for school in schools:
            ProjectSchool.objects.create(project = project, school = school)
        return project
    
    def names(self, rows):
        return [row.name for row in rows]
    
    def test_every_role_can_view_the_portfolio(self):
        for user in (self.pm, self.tech):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse("portfolio")).status_code, 200)
    
    def test_signed_out_users_are_sent_to_sign_in(self):
        response = self.client.get(reverse("portfolio"))
        self.assertRedirects(response, f"{reverse('sign_in')}?next={reverse('portfolio')}")
        
    def test_create_project_button_only_for_pms_and_admins(self):
        self.make_project([self.beacon])
        self.client.force_login(self.pm)
        self.assertContains(self.client.get(reverse("portfolio")), "Create project")
        self.client.force_login(self.tech)
        self.assertNotContains(self.client.get(reverse("portfolio")), "Create project")
        
    def test_empty_state_when_there_are_no_projects(self):
        self.client.force_login(self.pm)
        self.assertContains(self.client.get(reverse("portfolio")), "No projects yet")
        
    def test_only_trusts_and_schools_with_projects_are_listed(self):
        self.make_project([self.oakfield], trust = self.trust)
        rows = build_portfolio()
        self.assertEqual(self.names(rows), ["Northfield Learning Trust"])
        self.assertEqual(self.names(rows[0].schools), ["Oakfield Primary"])
        
    def tests_standalone_schools_sit_at_the_top_level(self):
        self.make_project([self.oakfield], trust = self.trust)
        self.make_project([self.beacon])
        self.assertEqual(self.names(build_portfolio()), ["Beacon High", "Northfield Learning Trust"])
        
    def test_central_team_project_lists_the_trust_with_no_schools(self):
        self.make_project(trust = self.trust, scope = Project.Scope.CENTRAL)
        rows = build_portfolio()
        self.assertEqual(self.names(rows), ["Northfield Learning Trust"])
        self.assertEqual(rows[0].schools, [])
        
    def tests_projects_of_every_status_are_listed(self):
        self.make_project([self.beacon], status = Project.Status.CANCELLED)
        self.assertEqual(self.names(build_portfolio()), ["Beacon High"])
        
    def test_active_count_only_counts_active_projects(self):
        self.make_project([self.oakfield], trust = self.trust, status = Project.Status.ACTIVE)
        self.make_project([self.oakfield], trust = self.trust, status = Project.Status.PLANNING)
        trust_row = build_portfolio()[0]
        self.assertEqual(trust_row.active_projects, 1)
        self.assertEqual(trust_row.schools[0].active_projects, 1)
        
    def test_closed_school_with_active_project_needs_attention(self):
        self.beacon.status = School.Status.CLOSED
        self.beacon.save()
        self.make_project([self.beacon], status = Project.Status.ACTIVE)
        self.assertTrue(build_portfolio()[0].needs_attention)
        
    def test_search_matches_names_dfe_numbers_postcodes_and_trust_codes(self):
        self.make_project([self.oakfield, self.riverside], trust = self.trust)
        self.make_project([self.beacon])
        searches = {
            "beacon": ["Beacon High"],
            "886/2014": ["Northfield Learning Trust"],
            "8862014": ["Northfield Learning Trust"],
            "nf4 2hp": ["Northfield Learning Trust"],
            "5102": ["Northfield Learning Trust"]
        }
        for query, expected in searches.items():
            with self.subTest(query = query):
                self.assertEqual(self.names(build_portfolio(query)), expected)
                
    def test_search_on_a_school_shows_only_that_school_under_its_trust(self):
        self.make_project([self.oakfield, self.riverside], trust = self.trust)
        rows = build_portfolio("riverside")
        self.assertEqual(self.names(rows[0].schools), ["Riverside Academy"])
        
    def test_search_with_no_matches_says_so(self):
        self.make_project([self.beacon])
        self.client.force_login(self.pm)
        response = self.client.get(reverse("portfolio"), {"q": "zzz"})
        self.assertContains(response, "No trusts or schools match")
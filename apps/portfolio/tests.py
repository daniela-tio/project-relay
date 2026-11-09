import csv
import io
from datetime import date
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from apps.portfolio.models import School, Trust
from apps.portfolio.gias import REQUIRED_COLUMNS, GiasFileError, file_date_from_name, load_establishments
from apps.portfolio.models import GiasEstablishment


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
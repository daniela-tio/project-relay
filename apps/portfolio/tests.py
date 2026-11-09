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
        

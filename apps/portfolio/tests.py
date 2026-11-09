from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from apps.portfolio.models import School, Trust

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

from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.conf import settings

class Trust(models.Model):
    """A trust of schools, imported from GIAS or added manually"""
    
    class TrustType(models.TextChoices):
        MULTI_ACADEMY = "mat", "Multi-academy trust"
        SINGLE_ACADEMY = "sat", "Single-academy trust"
        FOUNDATION = "foundation", "Foundation trust"
    
    name = models.CharField(max_length = 255)
    gias_code = models.PositiveIntegerField(unique = True, null = True, blank = True)
    trust_type = models.CharField(max_length = 20, choices = TrustType.choices)
    is_manual = models.BooleanField(default = False)
    
    """TIO-owned details. These are never changed by the GIAS import"""
    short_name = models.CharField(max_length = 50, blank = True)
    website = models.URLField(blank = True)
    notes = models.TextField(blank = True)
    
    class Meta:
        ordering = ["name"]
        
    def __str__(self):
        return self.name
    
    @property
    def display_name(self):
        return self.short_name or self.name

DFE_NUMBER_PATTERN = r"^\d{7}$"

class School(models.Model):
    """A school PMs can add projects to, located by its DFE number"""
    
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PROPOSED_TO_OPEN = "proposed_open", "Proposed to open"
        PROPOSED_TO_CLOSE = "proposed_close", "Proposed to close"
        CLOSED = "closed", "Closed"
        
    name = models.CharField(max_length=255)
    dfe_number = models.CharField(
        max_length = 7,
        unique = True,
        validators = [RegexValidator(DFE_NUMBER_PATTERN, "DFE number must be 7 digits.")],
    )
    urn = models.PositiveIntegerField(null = True, blank = True)
    trust = models.ForeignKey(
        Trust,
        on_delete = models.PROTECT,
        null = True,
        blank = True,
        related_name = "schools",
    )
    status = models.CharField(max_length = 20, choices = Status.choices, default = Status.OPEN)
    phase = models.CharField(max_length = 50, blank=True)
    town = models.CharField(max_length = 100, blank=True)
    postcode = models.CharField(max_length = 10, blank=True)
    is_manual = models.BooleanField(default=False)
        
    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition = Q(dfe_number__regex = DFE_NUMBER_PATTERN),
                name = "school_dfe_number_7_digits",
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.formatted_dfe_number})"
    
    @property
    def formatted_dfe_number(self):
        return f"{self.dfe_number[:3]}/{self.dfe_number[3:]}"

class GiasEstablishment(models.Model):
    """Import from the latest GIAS file. Replaced on every import."""
    
    urn = models.PositiveIntegerField(unique = True)
    dfe_number = models.CharField(max_length = 7, db_index = True)
    name = models.CharField(max_length = 255)
    status = models.CharField(max_length = 20, choices = School.Status.choices)
    close_date = models.DateField(null = True, blank = True)
    phase = models.CharField(max_length = 100, blank = True)
    town = models.CharField(max_length = 100, blank = True)
    postcode = models.CharField(max_length = 10, blank = True)
    trust_code = models.PositiveIntegerField(null = True, blank = True)
    trust_name = models.CharField(max_length = 255, blank = True)
    trust_type = models.CharField(max_length = 20, choices = Trust.TrustType.choices, blank = True)
    
    def __str__(self):
        return f"{self.name} ({self.urn})"
    
class GiasImport(models.Model):
    """Record of GIAS file upload."""
    
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        
    file_name = models.CharField(max_length = 255)
    file_date = models.DateField(null = True, blank = True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete = models.SET_NULL, null = True, related_name = "gias_imports"
    )
    started_at = models.DateTimeField(auto_now_add = True)
    finished_at = models.DateTimeField(null = True, blank = True)
    status = models.CharField(max_length = 20, choices = Status.choices, default = Status.RUNNING)
    rows_read = models.PositiveIntegerField(default = 0)
    error_summary = models.TextField(blank = True)
    
    class Meta:
        ordering = ["-started_at"]
        
    @property
    def duration(self):
        """Time the import took or None while it is still running"""
        if self.finished_at:
            return round((self.finished_at - self.started_at).total_seconds())
        return None
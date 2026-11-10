from django.conf import settings
from django.db import models
from django.db.models import F, Q
from apps.portfolio.models import School, Trust

class Project(models.Model):
    """A piece of work for a trust or school."""
    
    class Scope(models.TextChoices):
        SCHOOL = "school", "Single school"
        SELECTED = "selected", "Selected schools"
        TRUST_WIDE = "trust_wide", "Trust-wide"
        CENTRAL = "central", "Trust central team only"
        
    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On hold"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        
    name = models.CharField(max_length = 120)
    scope = models.CharField(max_length = 20, choices = Scope.choices)
    
    trust = models.ForeignKey(
        Trust, on_delete = models.PROTECT, null = True, blank = True, related_name = "projects"
    )
    schools = models.ManyToManyField(
        School, through = "ProjectSchool", related_name = "projects", blank = True
    )
    status = models.CharField(max_length = 20, choices = Status.choices, default = Status.PLANNING)
    start_date = models.DateField()
    target_end_date = models.DateField()
    pm = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete = models.PROTECT, related_name = "managed_projects"
    )
    halo_opportunity_url = models.URLField(blank = True)
    halo_presales_url = models.URLField(blank = True)
    halo_project_url = models.URLField(blank = True)
    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now = True)
    
    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition = Q(target_end_date__gte=F("start_date")),
                name = "project_end_on_or_after_start",
            ),
        ]
        
    def __str__(self):
        return self.name
    
class ProjectSchool(models.Model):
    """Links a project to a school."""
    
    project = models.ForeignKey(Project, on_delete = models.CASCADE)
    school = models.ForeignKey(School, on_delete = models.PROTECT)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields = ["project", "school"], name = "project_school_unique"),
        ]

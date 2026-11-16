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
        AWAITING_SIGN_OFF = "awaiting_sign_off", "Awaiting sign-off"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        
    ALLOWED_MOVES = {
        Status.PLANNING: [Status.ACTIVE, Status.CANCELLED],
        Status.ACTIVE: [Status.ON_HOLD, Status.AWAITING_SIGN_OFF, Status.CANCELLED],
        Status.ON_HOLD: [Status.ACTIVE, Status.CANCELLED],
        Status.AWAITING_SIGN_OFF: [Status.ACTIVE],
        Status.COMPLETED: [Status.ACTIVE],
        Status.CANCELLED: [Status.PLANNING]
    }
        
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
    
    def next_statuses(self):
        return self.ALLOWED_MOVES[self.status]
    
    @property
    def is_read_only(self):
        return self.status in (self.Status.COMPLETED, self.Status.CANCELLED)
    
    def move_to(self, status):
        if status not in self.Status.values:
            raise ValueError("That is not a valid project status.")
        if status not in self.next_statuses():
            raise ValueError(
                f"A project cannot move from {self.get_status_display()} to {self.Status(status).label}."
            )
        self.status = status
        self.save(update_fields=["status", "updated_at"])
        
    def confirmation_for(self, status):
        if status == self.Status.CANCELLED:
            return "Cancel this project? Open tasks stay as they are."
        if self.status == self.Status.COMPLETED:
            return "Reopen this project? Its sign-off is kept and it becomes editable again."
        if self.status == self.Status.CANCELLED:
            return "Reopen this project? It goes back to Planning and becomes editable again."
        return None
    
    def status_options(self):
        options = []
        for status in self.next_statuses():
            if self.is_read_only:
                label = "Reopen project"
            elif status == self.Status.CANCELLED:
                label = "Cancel Project"
            else:
                label = status.label
            options.append({
                "value": status.value,
                "label": label,
                "confirmation": self.confirmation_for(status)
            })
        return options
    
    @property
    def halo_links(self):
        return [
            ("Opportunity", self.halo_opportunity_url),
            ("Pre-sales", self.halo_presales_url),
            ("Project", self.halo_project_url)
        ]
    
class ProjectSchool(models.Model):
    """Links a project to a school."""
    
    project = models.ForeignKey(Project, on_delete = models.CASCADE)
    school = models.ForeignKey(School, on_delete = models.PROTECT)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields = ["project", "school"], name = "project_school_unique"),
        ]
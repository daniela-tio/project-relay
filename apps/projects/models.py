from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
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
                label = "Cancel project"
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
    
    @property
    def tech_lead(self):
        return next((m.user for m in self.members.all() if m.role == "tech_lead"), None)
    
    @property
    def techs(self):
        users = [m.user for m in self.members.all() if m.role == "tech"]
        return sorted(users, key=lambda user: (user.get_full_name() or user.username).lower())
    
class ProjectSchool(models.Model):
    """Links a project to a school."""
    
    project = models.ForeignKey(Project, on_delete = models.CASCADE)
    school = models.ForeignKey(School, on_delete = models.PROTECT)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields = ["project", "school"], name = "project_school_unique"),
        ]
        
class ProjectMember(models.Model):
    """member of the project team."""
    
    class Role(models.TextChoices):
        TECH_LEAD = "tech_lead", "Tech Lead"
        TECH = "tech", "Tech"
        
    project = models.ForeignKey(Project, on_delete = models.CASCADE, related_name = "members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete = models.PROTECT, related_name = "project_memberships"
    )
    role = models.CharField(max_length = 20, choices = Role.choices)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields = ["project", "user"], name = "project_member_unique"),
            models.UniqueConstraint(fields = ["project"], condition = Q(role = "tech_lead"), name = "project_one_tech_lead")
        ]
    
    def __str__(self):
        return f"{self.user} ({self.get_role_display()}) on {self.project}"
        
class Milestone(models.Model):
    
    project = models.ForeignKey(Project, on_delete = models.CASCADE, related_name = "milestones")
    name = models.CharField(max_length = 120)
    due_date = models.DateField()
    completed_at = models.DateField()
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete = models.SET_NULL, null = True, blank = True, related_name = "+"
    )
    
    class Meta:
        ordering = ["due_date", "name"]
        constraints = [
            models.UniqueConstraint(fields = ["project", "name"], name = "milestone_name_unique_in_project")
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def status(self):
        if self.completed_at:
            return "done"
        if self.due_date < timezone.localdate():
            return "overdue"
        return "open"
    
class Task(models.Model):
    
    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        NORMAL = 2, "Normal"
        HIGH = 3, "High"
        
    class Status(models.TextChoices):
        TO_DO = "to_do", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        BLOCKED = "blocked", "Blocked"
        DONE = "done", "Done"
        
    class Where(models.TextChoices):
        ON_SITE = "on_site", "On Site"
        REMOTE = "remote", "Remote"
        
    project = models.ForeignKey(Project, on_delete = models.CASCADE, related_name = "tasks")
    milestone = models.ForeignKey(Milestone, on_delete = models.SET_NULL, null = True, blank = True, related_name = "tasks")
    school = models.ForeignKey(School, on_delete = models.PROTECT, null = True, blank = True, related_name = "tasks")
    title = models.CharField(max_length = 150)
    description = models.TextField(blank = True)
    priority = models.IntegerField(choices = Priority.choices, default = Priority.NORMAL)
    status = models.CharField(max_length = 20, choices = Status.choices, default = Status.TO_DO)
    start_date = models.DateField()
    due_date = models.DateField()
    start_time = models.TimeField(null = True, blank = True)
    end_time = models.TimeField(null = True, blank = True)
    where = models.CharField(max_length = 20, choices = Where.choices, default = Where.ON_SITE)
    location = models.CharField(max_length = 200, blank = True)
    site_contact = models.CharField(max_length = 200, blank = True)
    assignees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank = True, related_name = "tasks")
    halo_url = models.DateTimeField(null = True, blank = True)
    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now = True)
    
    class Meta:
        ordering = ["due_date", "-priority", "title"]
        constraints = [
            models.CheckConstraint(
                condition = Q(due_date__gte = F("start_date")),
                name = "task_due_on_or_after_start"
            ),
            models.CheckConstraint(
                condition = (
                    Q(start_time__isnull = True, end_time__isnull = True) | Q(start_time__isnull = False, end_time__isnull = False, end_time__gt = F("start_time"))
                ),
                name = "task_times_both_or_neither_and_ordered"
            )
        ]
        
    def __str__(self):
        return self.title

class ChecklistItem(models.Model):
    
    task = models.ForeignKey(Task, on_delete = models.CASCADE, related_name = "checklist_items")
    text = models.CharField(max_length = 200)
    done = models.BooleanField(default = False)
    position = models.PositiveIntegerField(default = 0)
    
    class Meta:
        ordering = ["position", "pk"]
        
    def __str__(self):
        return self.text
    
from django import forms
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from django.db.models import Q
from apps.core.forms import TablerFormMixin
from apps.portfolio.services import SchoolLookupError, find_school_for_project
from apps.projects.models import Project, ProjectMember, Milestone, Task, ChecklistItem
from apps.portfolio.forms import DFE_ENTRY_PATTERN

class ProjectCustomerForm(TablerFormMixin, forms.Form):
    """Choose Trust or a single school by DFE number"""
    
    dfe_number = forms.CharField(
        label = "DFE number",
        validators = [RegexValidator(DFE_ENTRY_PATTERN, "Enter the DFE number.")],
        error_messages = {"required": "Enter a DFE number"},
        widget = forms.TextInput(
            attrs = {"placeholder": "123/4567", "inputmode": "numeric", "pattern": DFE_ENTRY_PATTERN}
        ),
    )
        
    def clean_dfe_number(self):
        dfe_number = self.cleaned_data["dfe_number"].replace("/", "")
        try:
            find_school_for_project(dfe_number)
        except SchoolLookupError as error:
            raise forms.ValidationError(str(error))
        return dfe_number

class ProjectDetailsForm(TablerFormMixin, forms.ModelForm):
    """Fields used to create and edit a project."""
    
    tech_lead = forms.ModelChoiceField(
        queryset = None, required = False, label = "Tech Lead", empty_label = "No Tech Lead"
    )
    team = forms.ModelMultipleChoiceField(
        queryset = None, required = False, label = "Team", widget = forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Project
        fields = [
            "name", "start_date", "target_end_date", "pm",
            "halo_opportunity_url", "halo_presales_url", "halo_project_url",
        ]
        labels = {
            "name": "Project name",
            "pm": "PM",
            "target_end_date": "Target end date",
            "halo_opportunity_url": "Opportunity URL",
            "halo_presales_url": "Pre-sales URL",
            "halo_project_url": "Project URL",
        }
        widgets = {
            "start_date": forms.DateInput(format = "%Y-%m-%d", attrs = {"type": "date"}),
            "target_end_date": forms.DateInput(format = "%Y-%m-%d", attrs = {"type": "date"}),
        }
        error_messages = {
            "name": {"required": "Enter a project name."},
            "start_date": {"required": "Enter a start date."},
            "target_end_date": {"required": "Enter a target end date."},
            "pm": {"required": "Choose a PM."},
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        User = get_user_model()
        eligible = Q(is_active=True) & (
            Q(role__in = [User.Role.ADMINISTRATOR, User.Role.PROJECT_MANAGER]) | Q(is_superuser=True)
        )
        if self.instance.pk:
            eligible |= Q(pk=self.instance.pm_id)
        self.fields["pm"].queryset = User.objects.filter(eligible)
        self.fields["pm"].label_from_instance = lambda person: person.get_full_name() or person.username
        if user is not None and not self.instance.pk:
            self.fields["pm"].initial = user

        for name in ["halo_opportunity_url", "halo_presales_url", "halo_project_url"]:
            self.fields[name].error_messages["invalid"] = "Enter a full web address starting with https://"
            
        current = []
        if self.instance.pk:
            members = list(self.instance.members.all())
            current = [member.user_id for member in members]
            self.fields["tech_lead"].initial = next(
                (m.user_id for m in members if m.role == ProjectMember.Role.TECH_LEAD), None
            )
            self.fields["team"].initial = [
                m.user_id for m in members if m.role == ProjectMember.Role.TECH 
            ]
        active = Q(is_active = True) | Q(pk__in = current)
        self.fields["tech_lead"].queryset = User.objects.filter(active).order_by("first_name", "username")
        self.fields["team"].queryset = User.objects.filter(
            (Q(is_active=True) & Q(role=User.Role.TECHNICIAN)) | Q(pk__in = current)
        ).order_by("first_name", "username")
        for name in ("tech_lead", "team"):
            self.fields[name].label_from_instance = lambda person: person.get_full_name() or person.username

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("target_end_date")
        if start and end and end < start:
            self.add_error("target_end_date", "Target end date must be on or after the start date.")
            
        if self.instance.pk and start and end and end >= start:
            tasks_outside = self.instance.tasks.filter(Q(start_date__lt = start) | Q(due_date__gt = end)).count()
            milestones_outside = self.instance.milestones.filter(Q(due_date__lt = start) | Q(due_date__gt = end)).count()
            if tasks_outside or milestones_outside:
                parts = []
                if tasks_outside:
                    parts.append(f"{tasks_outside} task{'s' if tasks_outside != 1 else ''}")
                if milestones_outside:
                    parts.append(f"{milestones_outside} milestone{'s' if milestones_outside != 1 else ''}")
                self.add_error("start_date", f"{' and '.join(parts)} falls outside these dates. Move them first.")
        return cleaned
    
    def save_members(self, project):
        tech_lead = self.cleaned_data.get("tech_lead")
        members = []
        if tech_lead:
            members.append(ProjectMember(project = project, user = tech_lead, role = ProjectMember.Role.TECH_LEAD))
        for user in self.cleaned_data.get("team", []):
            if user != tech_lead:
                members.append(ProjectMember(project = project, user = user, role = ProjectMember.Role.TECH))
        project.members.all().delete()
        ProjectMember.objects.bulk_create(members)     


class ProjectForm(ProjectDetailsForm):
    """Form to create a project."""

    selected_schools = forms.MultipleChoiceField(
        label = "Schools in scope", required = False, widget = forms.CheckboxSelectMultiple
    )

    class Meta(ProjectDetailsForm.Meta):
        fields = ProjectDetailsForm.Meta.fields + ["scope"]
        widgets = {**ProjectDetailsForm.Meta.widgets, "scope": forms.RadioSelect}

    def __init__(self, *args, customer, user, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        self.customer = customer
        
        if customer.is_trust:
            self.fields["scope"].choices = [
                choice for choice in Project.Scope.choices if choice[0] != Project.Scope.SCHOOL
            ]
            self.fields["scope"].initial = Project.Scope.SELECTED
            self.fields["selected_schools"].choices = customer.school_choices()
        elif customer.has_trust:
            self.fields["scope"].choices = Project.Scope.choices
            self.fields["scope"].initial = Project.Scope.SCHOOL
            self.fields["selected_schools"].choices = customer.school_choices()
            self.fields["selected_schools"].initial = [customer.dfe_number]
        else:
            self.fields["scope"].choices = [(Project.Scope.SCHOOL, Project.Scope.SCHOOL.label)]
            self.fields["scope"].initial = Project.Scope.SCHOOL
            del self.fields["selected_schools"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("scope") == Project.Scope.SELECTED and not cleaned.get("selected_schools"):
            self.add_error("selected_schools", "Choose at least one school.")
        return cleaned


class ProjectEditForm(ProjectDetailsForm):
    """Form to edit a project."""

class MilestoneForm(TablerFormMixin, forms.ModelForm):
    
    class Meta:
        model = Milestone
        fields = ["name", "due_date"]
        labels = {"due_date": "due_date"}
        widgets = {"due_date": forms.DateInput(format = "%Y-%n-%d", attrs = {"type": "date"})}
        error_messages = {
            "name": {"required": "Enter a milestone name."},
            "due_date": {"required": "Enter a due date."}
        }
        
    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        
    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        duplicate = self.project.milestones.filter(name__iexact = name).exclude(pk = self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError(f"Milestone {name} already exists.")
        return name
    
    def clean_due_date(self):
        due = self.cleaned_data["due_date"]
        start, end = self.project.start_date, self.project.target_end_date
        if not start <= due <= end:
            raise forms.ValidationError(f"Milestone dates must fall within the project dates.")
        return due
    
class TaskForm(TablerFormMixin, forms.ModelForm):

    class Meta:
        model = Task
        fields = [
            "school", "milestone", "title", "description", "priority",
            "start_date", "due_date", "start_time", "end_time",
            "where", "location", "site_contact", "assignees", "halo_url",
        ]
        labels = {"halo_url": "Halo link", "start_time": "Start time", "end_time": "End time"}
        widgets = {
            "description": forms.Textarea(attrs = {"rows": 3}),
            "start_date": forms.DateInput(format = "%Y-%m-%d", attrs = {"type": "date"}),
            "due_date": forms.DateInput(format = "%Y-%m-%d", attrs = {"type": "date"}),
            "start_time": forms.TimeInput(format = "%H:%M", attrs = {"type": "time"}),
            "end_time": forms.TimeInput(format = "%H:%M", attrs = {"type": "time"}),
            "where": forms.RadioSelect,
            "assignees": forms.CheckboxSelectMultiple,
        }
        error_messages = {
            "title": {"required": "Enter a task title."},
            "start_date": {"required": "Enter a start date."},
            "due_date": {"required": "Enter a due date."},
            "halo_url": {"invalid": "Enter a full web address starting with https://"},
        }

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project

        self.fields["school"].queryset = project.schools.all()
        self.fields["school"].error_messages["invalid_choice"] = "That school isn't part of this project."
        if project.scope == Project.Scope.SCHOOL:
            self.fields["school"].required = True
            self.fields["school"].initial = project.schools.first()
        else:
            self.fields["school"].empty_label = "Trust-wide (no single school)"

        self.fields["milestone"].queryset = project.milestones.all()
        self.fields["milestone"].empty_label = "No milestone"
        self.fields["milestone"].error_messages["invalid_choice"] = "That milestone isn't part of this project."

        User = get_user_model()
        self.fields["assignees"].queryset = User.objects.filter(
            Q(pk=project.pm_id) | Q(project_memberships__project=project)
        ).distinct().order_by("first_name", "username")
        self.fields["assignees"].error_messages["invalid_choice"] = "Only people on this project can be assigned."

    def clean(self):
        cleaned = super().clean()
        start, due = cleaned.get("start_date"), cleaned.get("due_date")
        project_start, project_end = self.project.start_date, self.project.target_end_date

        if start and due and due < start:
            self.add_error("due_date", "Start date must be on or before the due date.")
        for name in ("start_date", "due_date"):
            value = cleaned.get(name)
            if value and not project_start <= value <= project_end:
                self.add_error(name, (
                    f"Dates must fall within the project ({project_start:%-d %b %Y} - {project_end:%-d %b %Y})."
                ))

        start_time, end_time = cleaned.get("start_time"), cleaned.get("end_time")
        if (start_time is None) != (end_time is None):
            self.add_error("end_time", "Enter both a start and an end time, or neither.")
        elif start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "End time must be after the start time.")

        if cleaned.get("where") == Task.Where.ON_SITE and not cleaned.get("location"):
            self.add_error("location", "Enter where the work is.")
        return cleaned


class ChecklistItemForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ["text"]
        labels = {"text": "Checklist item"}


ChecklistFormSet = forms.inlineformset_factory(
    Task, ChecklistItem, form = ChecklistItemForm, extra = 3, can_delete=True
)


from django import forms
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from django.db.models import Q
from apps.core.forms import TablerFormMixin
from apps.portfolio.services import SchoolLookupError, find_school_for_project
from apps.projects.models import Project
from apps.portfolio.forms import DFE_ENTRY_PATTERN

class ProjectCustomerForm(TablerFormMixin, forms.Form):
    """Choose Trust or a single school by DFE number"""
    
    dfe_number = forms.CharField(
        label = "DFE number",
        validators = [RegexValidator(DFE_ENTRY_PATTERN, "Enter the DFE number.")],
        error_messages={"required": "Enter a DFE number"},
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
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "target_end_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
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
            Q(role__in=[User.Role.ADMINISTRATOR, User.Role.PROJECT_MANAGER]) | Q(is_superuser=True)
        )
        if self.instance.pk:
            eligible |= Q(pk=self.instance.pm_id)
        self.fields["pm"].queryset = User.objects.filter(eligible)
        self.fields["pm"].label_from_instance = lambda person: person.get_full_name() or person.username
        if user is not None and not self.instance.pk:
            self.fields["pm"].initial = user

        for name in ["halo_opportunity_url", "halo_presales_url", "halo_project_url"]:
            self.fields[name].error_messages["invalid"] = "Enter a full web address starting with https://"

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("target_end_date")
        if start and end and end < start:
            self.add_error("target_end_date", "Target end date must be on or after the start date.")
        return cleaned


class ProjectForm(ProjectDetailsForm):
    """Form to create a project."""

    selected_schools = forms.MultipleChoiceField(
        label="Schools in scope", required=False, widget=forms.CheckboxSelectMultiple
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


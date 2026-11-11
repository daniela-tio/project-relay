from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, CreateView
from django.contrib import messages
from django.db import transaction
from urllib.parse import urlencode
from apps.accounts.permissions import RuleRequiredMixin
from apps.portfolio.services import SchoolLookupError, find_school_for_project
from apps.projects.forms import ProjectCustomerForm, ProjectForm
from apps.projects.models import Project, ProjectSchool
from apps.projects.services import ProjectCustomer



class ProjectCustomerView(RuleRequiredMixin, FormView):
    permission_rule = "can_edit_project_data"
    form_class = ProjectCustomerForm
    template_name = "projects/project_customer.html"
    
    def form_valid(self, form):
        query = urlencode({"school": form.cleaned_data["dfe_number"]})
        return redirect(f"{reverse('project_create')}?{query}")
    
class ProjectCreateView(RuleRequiredMixin, CreateView):
    permission_rule = "can_edit_project_data"
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    
    def load_customer(self):
        try:
            found = find_school_for_project(self.request.GET.get("school", ""))
        except SchoolLookupError as error:
            messages.error(self.request, str(error))
            return redirect("project_customer")
        self.customer = ProjectCustomer(found)
        return None
    
    def get(self, request, *args, **kwargs):
        return self.load_customer() or super().get(request, *args, *kwargs)
    
    def post(self, request, *args, **kwargs):
        return self.load_customer() or super().post(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["customer"] = self.customer
        kwargs["user"] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customer"] = self.customer
        return context
    
    @transaction.atomic
    def form_valid(self, form):
        scope = form.cleaned_data["scope"]
        project = form.save(commit=False)
        project.trust = self.customer.save_trust()
        project.save()
        
        if scope == Project.Scope.SCHOOL:
            dfe_numbers = [self.customer.dfe_number]
        elif scope == Project.Scope.SELECTED:
            dfe_numbers = form.cleaned_data["selected_schools"]
        elif scope == Project.Scope.TRUST_WIDE:
            dfe_numbers = [dfe for dfe, _ in self.customer.school_choices()]
        else:
            dfe_numbers = []
            
        for dfe_number in dfe_numbers:
            ProjectSchool.objects.create(project = project, school = self.customer.save_school(dfe_number))
            
        messages.success(self.request, "Project created.")
        return redirect("home")
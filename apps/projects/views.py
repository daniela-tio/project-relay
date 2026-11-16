from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, CreateView, DetailView, View 
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from urllib.parse import urlencode
from apps.accounts.permissions import RuleRequiredMixin
from apps.portfolio.services import SchoolLookupError, find_school_for_project
from apps.projects.forms import ProjectCustomerForm, ProjectForm
from apps.projects.models import Project, ProjectSchool, Trust
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
        trust_id = self.request.GET.get("trust", "")
        if trust_id:
            trust = Trust.objects.filter(pk = trust_id).first() if trust_id.isdigit() else None
            if trust is None:
                messages.error(self.request, "That trust couldn't be found.")
                return redirect("portfolio")
            self.customer = ProjectCustomer(trust = trust)
            return None 
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
        return redirect("project_detail", pk = project.pk)
    
class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "projects/project_detail.html"
    
    def get_queryset(self):
        return Project.objects.select_related("trust", "pm").prefetch_related("schools")
    
class ProjectStatusView(RuleRequiredMixin, View):
    
    permission_rule = "can_edit_project_data"
    http_method_names = ["post"]
    
    def post(self, request, pk):
        project = get_object_or_404(Project, pk = pk)
        try:
            project.move_to(request.POST.get("status", ""))
        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"Project status changed to {project.get_status_display()}.")
        return redirect("project_detail", pk = project.pk) 
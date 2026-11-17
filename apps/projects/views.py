from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, CreateView, UpdateView, DetailView, View 
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.messages.views import SuccessMessageMixin
from django.utils import timezone
from urllib.parse import urlencode
from apps.accounts.permissions import RuleRequiredMixin
from apps.portfolio.services import SchoolLookupError, find_school_for_project
from apps.projects.forms import ProjectCustomerForm, ProjectForm, ProjectEditForm, MilestoneForm
from apps.projects.models import Project, ProjectSchool, Trust, Milestone, Task
from apps.projects.services import ProjectCustomer

def refuse_if_read_only(request, project):
    if project.is_read_only:
        messages.error(request, "This project is closed. Reopen to make changes")
        return redirect("project_detail", pk = project.pk)
    return None

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
        
        form.save_members(project)    
        messages.success(self.request, "Project created.")
        return redirect("project_detail", pk = project.pk)
    
class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "projects/project_detail.html"
    
    def get_queryset(self):
        return Project.objects.select_related("trust", "pm").prefetch_related("schools", "members__user")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["milestones"] = self.object.milestones.annotate(
            task_count = Count("tasks"),
            done_count = Count("tasks", filter = Q(tasks__status = Task.Status.DONE)),
        )
        return context
    
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
    
class ProjectUpdateView(RuleRequiredMixin, SuccessMessageMixin, UpdateView):
    """Edit project view"""
    
    permission_rule = "can_edit_project_data"
    model = Project
    form_class = ProjectEditForm
    template_name = "projects/project_edit.html"
    success_message = "Project Updated"
    
    def refuse_if_read_only(self):
        project = self.get_object()
        if project.is_read_only:
            messages.error(self.request, "Reopen this project before editing it.")
            return redirect("project_detail", pk = project.pk)
        return None
    
    def get(self, request, *args, **kwargs):
        return self.refuse_if_read_only() or super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        return self.refuse_if_read_only() or super().post(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse("project_detail", args=[self.object.pk])
    
    @transaction.atomic
    def form_valid(self, form):
        response = super().form_valid(form)
        form.save_members(self.object)
        return response
    
class MilestoneFormMixin(RuleRequiredMixin):
    
    permission_rule = "can_edit_project_data"
    model = Milestone
    form_class = MilestoneForm
    template_name = "projects/milestone_form.html"
    
    def get(self, request, *args, **kwargs):
        return refuse_if_read_only(request, self.get_project()) or super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        return refuse_if_read_only(request, self.get_project()) or super().post(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.get_project()
        return context

    def get_success_url(self):
        return reverse("project_detail", args=[self.get_project().pk])

class MilestoneCreateView(MilestoneFormMixin, CreateView):
    def get_project(self):
        return get_object_or_404(Project, pk=self.kwargs["project_pk"])

    def form_valid(self, form):
        form.instance.project = self.get_project()
        messages.success(self.request, "Milestone added.")
        return super().form_valid(form)

class MilestoneUpdateView(MilestoneFormMixin, UpdateView):
    def get_project(self):
        return self.get_object().project

    def form_valid(self, form):
        messages.success(self.request, "Milestone updated.")
        return super().form_valid(form)

class MilestoneDeleteView(RuleRequiredMixin, View):

    permission_rule = "can_edit_project_data"
    http_method_names = ["post"]

    def post(self, request, pk):
        milestone = get_object_or_404(Milestone, pk=pk)
        project = milestone.project
        refused = refuse_if_read_only(request, project)
        if refused:
            return refused
        milestone.delete()
        messages.success(request, f"Milestone “{milestone.name}” deleted.")
        return redirect("project_detail", pk=project.pk)

class MilestoneToggleView(RuleRequiredMixin, View):

    permission_rule = "can_edit_project_data"
    http_method_names = ["post"]

    def post(self, request, pk):
        milestone = get_object_or_404(Milestone, pk=pk)
        refused = refuse_if_read_only(request, milestone.project)
        if refused:
            return refused
        if milestone.completed_at:
            milestone.completed_at = None
            milestone.completed_by = None
            messages.success(request, f"Milestone “{milestone.name}” reopened.")
        else:
            milestone.completed_at = timezone.now()
            milestone.completed_by = request.user
            messages.success(request, f"Milestone “{milestone.name}” completed.")
        milestone.save()
        return redirect("project_detail", pk=milestone.project.pk)
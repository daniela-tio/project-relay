from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, CreateView, UpdateView, DetailView, View 
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.messages.views import SuccessMessageMixin
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode
from apps.accounts.permissions import RuleRequiredMixin
from apps.portfolio.services import SchoolLookupError, find_school_for_project
from apps.projects.forms import ProjectCustomerForm, ProjectForm, ProjectEditForm, MilestoneForm, TaskForm, ChecklistFormSet
from apps.projects.models import Project, ProjectSchool, Trust, Milestone, Task, ChecklistItem
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
        project = self.object
        milestones = list(project.milestones.annotate(
            task_count = Count("tasks"),
            done_count = Count("tasks", filter = Q(tasks__status = Task.Status.DONE))
        ))
        all_tasks = list(
            project.tasks.select_related("school", "milestone").prefetch_related("assignees")
        )
        
        done = sum(1 for task in all_tasks if task.is_done)
        context["progress"] = {
            "done": done,
            "total": len(all_tasks),
            "percent": round(done * 100 / len(all_tasks)) if all_tasks else 0
        }
        
        status = self.request.GET.get("status", "open")
        if status == "open":
            shown = [task for task in all_tasks if not task.is_done]
        elif status == "done":
            shown = [task for task in all_tasks if task.is_done]
        else:
            shown = all_tasks
        groups = [
            {"milestone": milestone, "tasks": [t for t in shown if t.milestone_id == milestone.pk], "task_count": milestone.task_count, "done_count": milestone.done_count} for milestone in milestones
        ]
        unassigned = [t for t in all_tasks if t.milestone_id is None]
        groups.append({
            "milestone": None,
            "tasks": [t for t in shown if t.milestone_id is None],
            "task_count": len(unassigned),
            "done_count": sum(1 for t in unassigned if t.is_done)            
        })
        
        context.update({
            "tab": self.request.GET.get("tab", "overview"),
            "status": status,
            "milestones": milestones,
            "groups": groups
        })
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
    
class TaskFormMixin(RuleRequiredMixin):
    """Shared by creating and editing a task: the form plus its checklist, saved together."""

    permission_rule = "can_edit_project_data"
    model = Task
    form_class = TaskForm
    template_name = "projects/task_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs

    def get(self, request, *args, **kwargs):
        return refuse_if_read_only(request, self.get_project()) or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        refused = refuse_if_read_only(request, self.get_project())
        if refused:
            return refused
        self.object = self.get_existing_task()
        form = self.get_form()
        checklist = ChecklistFormSet(request.POST, instance=self.object or Task())
        if form.is_valid() and checklist.is_valid():
            return self.save_task(form, checklist)
        return self.render_to_response(self.get_context_data(form=form, checklist=checklist))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.get_project()
        context.setdefault("checklist", ChecklistFormSet(instance=self.object or Task()))
        return context

    @transaction.atomic
    def save_task(self, form, checklist):
        task = form.save(commit=False)
        task.project = self.get_project()
        task.save()
        form.save_m2m()  # saves the assignees, which need the task to exist first
        checklist.instance = task
        checklist.save()
        messages.success(self.request, self.success_text)
        return redirect(f"{reverse('project_detail', args=[task.project.pk])}?tab=tasks")


class TaskCreateView(TaskFormMixin, CreateView):
    success_text = "Task created."

    def get_project(self):
        return get_object_or_404(Project, pk=self.kwargs["project_pk"])

    def get_existing_task(self):
        return None

    def get_initial(self):
        # "Add task to {milestone}" (C8) pre-selects that milestone
        initial = super().get_initial()
        if self.request.GET.get("milestone"):
            initial["milestone"] = self.request.GET["milestone"]
        return initial


class TaskUpdateView(TaskFormMixin, UpdateView):
    success_text = "Task updated."

    def get_project(self):
        return self.get_object().project

    def get_existing_task(self):
        return self.get_object()


class TaskDeleteView(RuleRequiredMixin, View):
    """Delete a task. POST only, from its confirmation modal."""

    permission_rule = "can_edit_project_data"
    http_method_names = ["post"]

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        project = task.project
        refused = refuse_if_read_only(request, project)
        if refused:
            return refused
        task.delete()
        messages.success(request, f"Task “{task.title}” deleted.")
        return redirect(f"{reverse('project_detail', args=[project.pk])}?tab=tasks")
    
class TaskToggleView(LoginRequiredMixin, View):
    
    http_method_names = ["post"]
    
    def post(self, request, pk):
        task = get_object_or_404(Task.objects.select_related("project"), pk = pk)
        refused = refuse_if_read_only(request, task.project)
        if refused:
            return refused
        if not task.can_be_ticked_by(request.user):
            raise PermissionDenied
        if task.is_done:
            task.reopen()
            messages.success(request, f"{task.title} reopened.")
        else:
            task.mark_done()
            messages.success(request, f"{task.title} marked done.")
        next_url = request.POST.get("next", "")
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts = {request.get_host()}):
            return redirect(next_url)
        return redirect(f"{reverse('project_detail', args = [task.project.pk])}?tab=tasks")
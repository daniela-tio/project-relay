from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView
from django.urls import reverse
from django.views.generic import CreateView
from urllib.parse import urlencode
from apps.accounts.permissions import RuleRequiredMixin
from apps.portfolio.forms import GiasUploadForm, SchoolForm, TrustForm
from apps.portfolio.gias import run_import
from apps.portfolio.models import GiasImport, School, Trust, Project
from apps.portfolio.services import build_portfolio

class GiasImportView(RuleRequiredMixin, FormView):
    permission_rule = "can_manage_portfolio"
    form_class = GiasUploadForm
    template_name = "portfolio/gias_import.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["imports"] = GiasImport.objects.select_related("uploaded_by")[:10]
        return context
    
    def form_valid(self, form):
        if GiasImport.objects.filter(status=GiasImport.Status.RUNNING).exists():
            messages.error(self.request, "An import is already running. Try again later.")
            return redirect("gias_import")

        upload = form.cleaned_data["csv_file"]
        record = run_import(upload, upload.name, self.request.user)
        
        if record.status == GiasImport.Status.SUCCEEDED:
            messages.success(self.request, f"Import finished: {record.rows_read:,} rows read.")
        else:
            messages.error(self.request, record.error_summary)
        return redirect("gias_import")

class SchoolCreateView(RuleRequiredMixin, CreateView):
    """Add school that is not in the GIAS import"""
    
    permission_rule = "can_edit_project_data"
    model = School
    form_class = SchoolForm
    template_name = "portfolio/school_form.html"
    
    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("dfe"):
            initial["dfe_number"] = self.request.GET["dfe"]
        if self.request.GET.get("trust"):
            initial["trust"] = self.request.GET["trust"]
        return initial

    def form_valid(self, form):
        form.instance.is_manual = True
        school = form.save()
        messages.success(self.request, f"{school.name} added.")
        query = urlencode({"school": school.dfe_number})
        return redirect(f"{reverse('project_create')}?{query}")
    
class TrustCreateView(RuleRequiredMixin, CreateView):
    """Add trust that is not in the GIAS import"""
    
    permission_rule = "can_edit_project_data"
    model = Trust
    form_class = TrustForm
    template_name = "portfolio/trust_form.html"
    
    def form_valid(self, form):
        form.instance.is_manual = True
        trust = form.save()
        messages.success(self.request, f"{trust.name} added.")
        query = {"trust": trust.pk}
        if self.request.GET.get("dfe"):
            query["dfe"] = self.request.GET["dfe"]
        return redirect(f"{reverse('school_create')}?{urlencode(query)}")
    
class PortfolioView(LoginRequiredMixin, TemplateView):
    
    template_name = "portfolio/portfolio.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")
        context["query"] = query
        context["rows"] = build_portfolio(query)
        context["has_projects"] = Project.objects.exists()
        return context
    
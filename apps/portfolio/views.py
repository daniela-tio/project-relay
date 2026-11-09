from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import FormView
from apps.accounts.permissions import RuleRequiredMixin
from apps.portfolio.forms import GiasUploadForm
from apps.portfolio.gias import run_import
from apps.portfolio.models import GiasImport

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

from django import forms
from apps.core.forms import TablerFormMixin

MAX_UPLOAD_MB = 100

class GiasUploadForm(TablerFormMixin, forms.Form):
    csv_file = forms.FileField(
        label = "GIAS CSV file",
        error_messages = {"required": "Choose the GIAS CSV file to upload."},
        widget = forms.ClearableFileInput(attrs = {"accept": ".csv"}),
    )
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.lower().endswith(".csv"):
            raise forms.ValidationError("The file must be a .csv file.")
        if csv_file.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f"The file must be smaller than {MAX_UPLOAD_MB} MB.")
        return csv_file
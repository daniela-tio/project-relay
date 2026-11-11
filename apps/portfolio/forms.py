import re
from django import forms
from django.core.validators import RegexValidator
from apps.core.forms import TablerFormMixin
from apps.portfolio.models import GiasEstablishment, School, Trust

MAX_UPLOAD_MB = 100
DFE_ENTRY_PATTERN = r"^\d{3}/\d{4}$"
UK_POSTCODE_PATTERN = r"^[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}$"

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
    
class SchoolForm(TablerFormMixin, forms.ModelForm):
    """Adds a school that has not yet been imported."""
    
    dfe_number = forms.CharField(
        label = "DFE number",
        validators = [RegexValidator(DFE_ENTRY_PATTERN, "Enter the DFE number.")],
        error_messages = {"required": "Enter a DFE number."},
        widget = forms.TextInput(
            attrs = {"placeholder": "123/4567", "inputmode": "numeric", "pattern": DFE_ENTRY_PATTERN}
        ),
    )
    
    class Meta:
        model = School
        fields = ["name", "dfe_number", "trust", "phase", "town", "postcode"]
        labels = {"name": "School name"}
        error_messages = {
            "name": {"required": "Enter the school name."},
            "dfe_number": {"unique": "A school with this DFE number already exists."}
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["trust"].empty_label = "None (standalone)"
        self.fields["postcode"].required = True
        self.fields["postcode"].error_messages["required"] = "Enter the postcode."
        self.fields["town"].required = True
        self.fields["town"].error_messages["required"] = "Enter the town."
    
    def clean_dfe_number(self):
        dfe_number = self.cleaned_data["dfe_number"].replace("/", "")
        if GiasEstablishment.objects.filter(dfe_number = dfe_number).exists():
            raise forms.ValidationError(
                "This school already exists. Please look it by its DFE number."
            )
        return dfe_number
    
    def clean_postcode(self):
        raw = self.cleaned_data["postcode"].upper().replace(" ", "")
        postcode = f"{raw[:-3]} {raw[-3:]}"
        if not re.match(UK_POSTCODE_PATTERN, postcode):
            raise forms.ValidationError("Enter a real UK postcode.")
        return postcode
    
class TrustForm(TablerFormMixin, forms.ModelForm):
    """Adds a trust that has not yet been imported"""
    
    class Meta:
        model = Trust
        fields = ["name", "short_name", "trust_type", "gias_code"]
        labels = {"name": "Trust name", "gias_code": "Trust code"}
        helps_texts = {
            "short_name": "Used on tags and cards. Up to 30 characters.",
            "gias_code": "The DFE group code from GIAS, if available."
        }
        error_messages = {
            "name": {"required": "Enter the trust name."},
            "gias_code": {
                "unique": "A trust with this trust code already exists.",
                "invalid": "Trust code should be numbers only",
            }
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["short_name"].required = True
        self.fields["short_name"].max_length = 30
        self.fields["short_name"].error_messages["required"] = "Enter a short name of up to 30 characters."
        
    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Trust.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"A trust called {name} already exists.")
        return name
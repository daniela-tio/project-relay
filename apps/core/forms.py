class TablerFormMixin:
    """Adds Tablers CSS classes to every field"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            input_type = getattr(field.widget, "input_type", "")
            css_class = {
                "checkbox": "form-check-input",
                "radio": "form-check-input",
                "select": "form-select",
            }.get(input_type, "form-control")
            field.widget.attrs["class"] = css_class
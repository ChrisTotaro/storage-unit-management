from django import forms

from .models import Property, Unit


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ["property", "unit_number", "size", "status", "monthly_rent", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["property"].queryset = Property.objects.filter(user=user).order_by("name")
        self.fields["property"].required = True
        self.fields["status"].widget = forms.Select(choices=Unit.STATUS_CHOICES)
        for name, field in self.fields.items():
            base_class = "form-control"
            if isinstance(field.widget, forms.Select):
                base_class = "form-select"
            field.widget.attrs.setdefault("class", base_class)
    
    def clean_property(self):
        property_obj = self.cleaned_data.get("property")
        if not property_obj:
            raise forms.ValidationError("Please select a property.")
        return property_obj


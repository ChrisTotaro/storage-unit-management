from django import forms

from .models import Property, Unit, Tenant, Tenancies


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


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ["name", "address"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            base_class = "form-control"
            if isinstance(field.widget, forms.Select):
                base_class = "form-select"
            field.widget.attrs.setdefault("class", base_class)


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ["first_name", "last_name", "email_address", "phone_number", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            base_class = "form-control form-control-sm"
            if isinstance(field.widget, forms.Select):
                base_class = "form-select form-select-sm"
            field.widget.attrs.setdefault("class", base_class)


class TenancyForm(forms.ModelForm):
    class Meta:
        model = Tenancies
        fields = ["tenant", "start_date", "end_date", "monthly_rent_at_start", "notes"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["tenant"].queryset = Tenant.objects.filter(user=user).order_by("last_name", "first_name")
        else:
            self.fields["tenant"].queryset = Tenant.objects.all().order_by("last_name", "first_name")
        for name, field in self.fields.items():
            base_class = "form-control form-control-sm"
            if isinstance(field.widget, forms.Select):
                base_class = "form-select form-select-sm"
            field.widget.attrs.setdefault("class", base_class)

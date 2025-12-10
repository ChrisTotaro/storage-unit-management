from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.urls import reverse
from django.contrib import messages

from ..models import Property, Unit, Tenancies
from ..forms import UnitForm, TenancyForm, TenantForm


def _get_units_context(request, property_id=None, status=None):
    properties = Property.objects.filter(user=request.user).order_by("name")

    tenancies_prefetch = Prefetch(
        "tenancies_set",
        queryset=Tenancies.objects.select_related("tenant").order_by("-start_date"),
        to_attr="prefetched_tenancies",
    )

    units = (
        Unit.objects.filter(property__user=request.user)
        .select_related("property")
        .prefetch_related(tenancies_prefetch)
        .order_by("property__name", "unit_number")
    )

    if property_id:
        units = units.filter(property_id=property_id)

    if status:
        units = units.filter(status=status)

    return properties, units


def _normalize_property_id(value):
    if value in (None, "", "None", "null", "undefined"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_status_id(value):
    VALID_STATUSES = [choice[0] for choice in Unit.STATUS_CHOICES]
    if value in (None, "", "None", "null", "undefined") or value not in VALID_STATUSES:
        return None
    try:
        return value
    except (TypeError, ValueError):
        return None


class IndexView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request):
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)

        raw_status_id = request.GET.get("status")
        status = _normalize_status_id(raw_status_id)

        properties, units = _get_units_context(request, property_id, status)

        return render(
            request,
            "storage/units/index.html",
            {
                "units": units,
                "properties": properties,
                "selected_property_id": property_id,
                "selected_status": status,
            },
        )


class UnitCreateView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request):
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)

        raw_status = request.GET.get("status")
        status = _normalize_status_id(raw_status)

        properties, units = _get_units_context(request, property_id, status)
        add_unit_form = UnitForm(
            user=request.user, initial={"property": property_id} if property_id else None
        )

        return render(
            request,
            "storage/units/add.html",
            {
                "units": units,
                "properties": properties,
                "selected_property_id": property_id,
                "selected_status": status,
                "add_unit_form": add_unit_form,
            },
        )

    def post(self, request):
        raw_property_filter = request.POST.get("filter_property") or request.GET.get("property")
        property_filter = _normalize_property_id(raw_property_filter)

        raw_status = request.GET.get("status")
        status = _normalize_status_id(raw_status)

        form = UnitForm(request.POST, user=request.user)

        if form.is_valid():
            new_unit = form.save()
            messages.success(request, "Unit added successfully.")

            redirect_property = property_filter or new_unit.property_id
            redirect_url = reverse("index")
            params = []
            if redirect_property:
                params.append(f"property={redirect_property}")
            if status:
                params.append(f"status={status}")
            if params:
                redirect_url = f"{redirect_url}?{'&'.join(params)}"
            return redirect(redirect_url)

        properties, units = _get_units_context(request, property_filter, status)
        return render(
            request,
            "storage/units/add.html",
            {
                "units": units,
                "properties": properties,
                "selected_property_id": property_filter,
                "selected_status": status,
                "add_unit_form": form,
            },
        )


class UnitDetailView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request, unit_id):
        unit = get_object_or_404(
            Unit.objects.filter(property__user=request.user)
            .select_related("property"),
            id=unit_id
        )
        
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        raw_status = request.GET.get("status")
        status = _normalize_status_id(raw_status)
        
        properties, units = _get_units_context(request, property_id, status)
        
        # Get current tenancy
        current_tenancy = (
            Tenancies.objects.filter(unit=unit)
            .select_related("tenant")
            .order_by("-start_date")
            .first()
        )
        
        # Create tenancy form for assigning tenant
        tenancy_form = TenancyForm(initial={"monthly_rent_at_start": unit.monthly_rent}, user=request.user)
        
        # Create tenant form for creating new tenant
        tenant_form = TenantForm()
        
        return render(
            request,
            "storage/units/detail.html",
            {
                "unit": unit,
                "units": units,
                "properties": properties,
                "selected_property_id": property_id,
                "selected_status": status,
                "current_tenancy": current_tenancy,
                "tenancy_form": tenancy_form,
                "tenant_form": tenant_form,
            },
        )


class UnitEditView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request, unit_id):
        unit = get_object_or_404(
            Unit.objects.filter(property__user=request.user)
            .select_related("property"),
            id=unit_id
        )
        
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        raw_status = request.GET.get("status")
        status = _normalize_status_id(raw_status)
        
        properties, units = _get_units_context(request, property_id, status)
        
        # Get current tenancy
        current_tenancy = (
            Tenancies.objects.filter(unit=unit)
            .select_related("tenant")
            .order_by("-start_date")
            .first()
        )
        
        # Create forms
        unit_form = UnitForm(instance=unit, user=request.user)
        tenancy_form = TenancyForm(initial={"monthly_rent_at_start": unit.monthly_rent}, user=request.user)
        
        return render(
            request,
            "storage/units/edit.html",
            {
                "unit": unit,
                "units": units,
                "properties": properties,
                "selected_property_id": property_id,
                "selected_status": status,
                "current_tenancy": current_tenancy,
                "unit_form": unit_form,
                "tenancy_form": tenancy_form,
            },
        )

    def post(self, request, unit_id):
        unit = get_object_or_404(
            Unit.objects.filter(property__user=request.user),
            id=unit_id
        )
        
        form = UnitForm(request.POST, instance=unit, user=request.user)
        
        if form.is_valid():
            form.save()
            messages.success(request, "Unit updated successfully.")
            return redirect("unit_detail", unit_id=unit_id)
        
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        raw_status = request.GET.get("status")
        status = _normalize_status_id(raw_status)
        
        properties, units = _get_units_context(request, property_id, status)
        
        # Get current tenancy
        current_tenancy = (
            Tenancies.objects.filter(unit=unit)
            .select_related("tenant")
            .order_by("-start_date")
            .first()
        )
        
        tenancy_form = TenancyForm(initial={"monthly_rent_at_start": unit.monthly_rent}, user=request.user)
        
        return render(
            request,
            "storage/units/edit.html",
            {
                "unit": unit,
                "units": units,
                "properties": properties,
                "selected_property_id": property_id,
                "selected_status": status,
                "current_tenancy": current_tenancy,
                "unit_form": form,
                "tenancy_form": tenancy_form,
            },
        )


class UnitAssignTenantView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def post(self, request, unit_id):
        unit = get_object_or_404(
            Unit.objects.filter(property__user=request.user),
            id=unit_id
        )
        
        form = TenancyForm(request.POST, user=request.user)
        
        if form.is_valid():
            tenancy = form.save(commit=False)
            tenancy.unit = unit
            tenancy.save()
            # Update unit status to occupied
            unit.status = Unit.STATUS_OCCUPIED
            unit.save()
            messages.success(request, "Tenant assigned successfully.")
            return redirect("unit_detail", unit_id=unit_id)
        
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        raw_status = request.GET.get("status")
        status = _normalize_status_id(raw_status)
        
        properties, units = _get_units_context(request, property_id, status)
        
        # Get current tenancy
        current_tenancy = (
            Tenancies.objects.filter(unit=unit)
            .select_related("tenant")
            .order_by("-start_date")
            .first()
        )
        
        # Create tenant form for creating new tenant
        tenant_form = TenantForm()
        
        return render(
            request,
            "storage/units/detail.html",
            {
                "unit": unit,
                "units": units,
                "properties": properties,
                "selected_property_id": property_id,
                "selected_status": status,
                "current_tenancy": current_tenancy,
                "tenancy_form": form,
                "tenant_form": tenant_form,
            },
        )


class UnitRemoveTenantView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def post(self, request, unit_id):
        unit = get_object_or_404(
            Unit.objects.filter(property__user=request.user),
            id=unit_id
        )
        
        # Get the current tenancy
        current_tenancy = (
            Tenancies.objects.filter(unit=unit)
            .select_related("tenant")
            .order_by("-start_date")
            .first()
        )
        
        if current_tenancy:
            tenant_name = f"{current_tenancy.tenant.first_name} {current_tenancy.tenant.last_name}"
            # Delete the tenancy
            current_tenancy.delete()
            # Update unit status to vacant
            unit.status = Unit.STATUS_VACANT
            unit.save()
            messages.success(request, f"Tenant {tenant_name} removed from unit successfully.")
        else:
            messages.warning(request, "No tenant assigned to this unit.")
        
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        raw_status = request.GET.get("status")
        status = _normalize_status_id(raw_status)
        
        # Build redirect URL with filters
        redirect_url = reverse("unit_detail", kwargs={"unit_id": unit_id})
        params = []
        if property_id:
            params.append(f"property={property_id}")
        if status:
            params.append(f"status={status}")
        if params:
            redirect_url += "?" + "&".join(params)
        
        return redirect(redirect_url)


class UnitCreateAndAssignTenantView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def post(self, request, unit_id):
        unit = get_object_or_404(
            Unit.objects.filter(property__user=request.user),
            id=unit_id
        )
        
        # Get tenant form data
        tenant_form = TenantForm(request.POST)
        
        # Validate tenant form
        tenant_valid = tenant_form.is_valid()
        
        # Validate tenancy fields manually (since we don't have a tenant yet)
        from datetime import datetime
        from decimal import Decimal, InvalidOperation
        
        tenancy_errors = {}
        start_date = None
        end_date = None
        monthly_rent = None
        
        # Validate start_date
        start_date_str = request.POST.get("start_date")
        if not start_date_str:
            tenancy_errors["start_date"] = ["This field is required."]
        else:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                tenancy_errors["start_date"] = ["Enter a valid date."]
        
        # Validate end_date
        end_date_str = request.POST.get("end_date")
        if not end_date_str:
            tenancy_errors["end_date"] = ["This field is required."]
        else:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                if start_date and end_date < start_date:
                    tenancy_errors["end_date"] = ["End date must be after start date."]
            except ValueError:
                tenancy_errors["end_date"] = ["Enter a valid date."]
        
        # Validate monthly_rent_at_start
        monthly_rent_str = request.POST.get("monthly_rent_at_start", unit.monthly_rent)
        try:
            monthly_rent = Decimal(str(monthly_rent_str))
            if monthly_rent < 0:
                tenancy_errors["monthly_rent_at_start"] = ["Monthly rent must be positive."]
        except (InvalidOperation, ValueError):
            tenancy_errors["monthly_rent_at_start"] = ["Enter a valid number."]
        
        tenancy_valid = len(tenancy_errors) == 0
        
        if tenant_valid and tenancy_valid:
            # Create the tenant
            tenant = tenant_form.save(commit=False)
            tenant.user = request.user
            tenant.save()
            
            # Create the tenancy and assign to unit
            tenancy = Tenancies(
                tenant=tenant,
                unit=unit,
                start_date=start_date,
                end_date=end_date,
                monthly_rent_at_start=monthly_rent,
                notes=request.POST.get("notes", ""),
            )
            tenancy.save()
            
            # Update unit status to occupied
            unit.status = Unit.STATUS_OCCUPIED
            unit.save()
            
            messages.success(request, f"Tenant {tenant.first_name} {tenant.last_name} created and assigned successfully.")
            
            # Build redirect URL with filters
            raw_property_id = request.GET.get("property")
            property_id = _normalize_property_id(raw_property_id)
            raw_status = request.GET.get("status")
            status = _normalize_status_id(raw_status)
            
            redirect_url = reverse("unit_detail", kwargs={"unit_id": unit_id})
            params = []
            if property_id:
                params.append(f"property={property_id}")
            if status:
                params.append(f"status={status}")
            if params:
                redirect_url += "?" + "&".join(params)
            
            return redirect(redirect_url)
        
        # If forms are invalid, re-render the detail page with errors
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        raw_status = request.GET.get("status")
        status = _normalize_status_id(raw_status)
        
        properties, units = _get_units_context(request, property_id, status)
        
        # Get current tenancy
        current_tenancy = (
            Tenancies.objects.filter(unit=unit)
            .select_related("tenant")
            .order_by("-start_date")
            .first()
        )
        
        # Re-create tenancy form with POST data and add manual errors
        from django.http import QueryDict
        tenancy_post_data = QueryDict(mutable=True)
        tenancy_post_data.update({
            "tenant": "",
            "start_date": request.POST.get("start_date", ""),
            "end_date": request.POST.get("end_date", ""),
            "monthly_rent_at_start": request.POST.get("monthly_rent_at_start", unit.monthly_rent),
            "notes": request.POST.get("notes", ""),
        })
        tenancy_form = TenancyForm(tenancy_post_data, user=request.user)
        # Add manual validation errors
        for field, errors in tenancy_errors.items():
            tenancy_form.add_error(field, errors)
        
        return render(
            request,
            "storage/units/detail.html",
            {
                "unit": unit,
                "units": units,
                "properties": properties,
                "selected_property_id": property_id,
                "selected_status": status,
                "current_tenancy": current_tenancy,
                "tenancy_form": tenancy_form,
                "tenant_form": tenant_form,
            },
        )


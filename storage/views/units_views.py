from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.urls import reverse
from django.contrib import messages

from ..models import Property, Unit, Tenancies
from ..forms import UnitForm, TenancyForm


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


from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.urls import reverse
from django.contrib import messages

from .models import Property, Unit, Tenant, Tenancies
from .forms import UnitForm


def _get_units_context(request, property_id=None):
    properties = Property.objects.filter(user=request.user).order_by("name")

    for property in properties:
        print(property.id)

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

    return properties, units


class IndexView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request):
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        properties, units = _get_units_context(request, property_id)

        return render(
            request,
            "storage/index.html",
            {
                "units": units,
                "properties": properties,
                "selected_property_id": property_id,
            },
        )


class TenantListView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request):
        properties = Property.objects.filter(user=request.user).order_by("name")
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)

        tenancy_qs = (
            Tenancies.objects.filter(unit__property__user=request.user)
            .select_related("unit", "unit__property")
            .order_by("-start_date")
        )

        if property_id:
            tenancy_qs = tenancy_qs.filter(unit__property_id=property_id)

        tenants = (
            Tenant.objects.filter(tenancies__unit__property__user=request.user)
            .prefetch_related(
                Prefetch(
                    "tenancies_set",
                    queryset=tenancy_qs,
                    to_attr="prefetched_tenancies",
                )
            )
            .distinct()
            .order_by("last_name", "first_name")
        )

        if property_id:
            tenants = tenants.filter(tenancies__unit__property_id=property_id)

        return render(
            request,
            "storage/tenants.html",
            {
                "tenants": tenants,
                "properties": properties,
                "selected_property_id": property_id,
            },
        )


class UnitCreateView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request):
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        properties, units = _get_units_context(request, property_id)
        add_unit_form = UnitForm(
            user=request.user, initial={"property": property_id} if property_id else None
        )

        return render(
            request,
            "storage/add.html",
            {
                "units": units,
                "properties": properties,
                "selected_property_id": property_id,
                "add_unit_form": add_unit_form,
            },
        )

    def post(self, request):
        property_filter = request.POST.get("filter_property") or request.GET.get("property")
        form = UnitForm(request.POST, user=request.user)

        if form.is_valid():
            new_unit = form.save()
            messages.success(request, "Unit added successfully.")

            redirect_property = property_filter or new_unit.property_id
            redirect_url = reverse("index")
            if redirect_property:
                redirect_url = f"{redirect_url}?property={redirect_property}"
            return redirect(redirect_url)

        properties, units = _get_units_context(request, property_filter)
        return render(
            request,
            "storage/add.html",
            {
                "units": units,
                "properties": properties,
                "selected_property_id": property_filter,
                "add_unit_form": form,
            },
        )

def _normalize_property_id(value):
    if value in (None, "", "None", "null", "undefined"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

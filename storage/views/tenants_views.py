from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Count, Sum, Q
from django.contrib import messages

from accounts.mixins import SubscriptionRequiredMixin
from ..models import Property, Tenant, Tenancies
from ..forms import TenantForm
from .units_views import _normalize_property_id


class TenantCreateView(SubscriptionRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request):
        form = TenantForm()
        properties = Property.objects.filter(user=request.user).order_by("name")
        
        # Get all tenants for the index template
        all_tenants = (
            Tenant.objects.filter(user=request.user)
            .annotate(
                total_rent=Sum("tenancies__monthly_rent_at_start"),
                unit_count=Count("tenancies", distinct=True)
            )
            .prefetch_related(
                Prefetch(
                    "tenancies_set",
                    queryset=Tenancies.objects.filter(unit__property__user=request.user)
                    .select_related("unit", "unit__property")
                    .order_by("-start_date"),
                    to_attr="prefetched_tenancies",
                )
            )
            .order_by("last_name", "first_name")
        )
        
        return render(
            request,
            "storage/tenants/add.html",
            {
                "form": form,
                "tenants": all_tenants,
                "properties": properties,
            },
        )

    def post(self, request):
        form = TenantForm(request.POST)
        
        if form.is_valid():
            tenant = form.save(commit=False)
            tenant.user = request.user
            tenant.save()
            messages.success(request, "Tenant created successfully.")
            return redirect("tenant_detail", tenant_id=tenant.id)
        
        properties = Property.objects.filter(user=request.user).order_by("name")
        
        # Get all tenants for the index template
        all_tenants = (
            Tenant.objects.filter(user=request.user)
            .annotate(
                total_rent=Sum("tenancies__monthly_rent_at_start"),
                unit_count=Count("tenancies", distinct=True)
            )
            .prefetch_related(
                Prefetch(
                    "tenancies_set",
                    queryset=Tenancies.objects.filter(unit__property__user=request.user)
                    .select_related("unit", "unit__property")
                    .order_by("-start_date"),
                    to_attr="prefetched_tenancies",
                )
            )
            .order_by("last_name", "first_name")
        )
        
        return render(
            request,
            "storage/tenants/add.html",
            {
                "form": form,
                "tenants": all_tenants,
                "properties": properties,
            },
        )


class TenantListView(SubscriptionRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request):
        properties = Property.objects.filter(user=request.user).order_by("name")
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        
        # Get search query
        search_query = request.GET.get("search", "").strip()
        
        # Get active filter (only show tenants with units)
        active_filter = request.GET.get("active", "").strip().lower()
        show_active_only = active_filter == "true"

        tenancy_qs = (
            Tenancies.objects.filter(unit__property__user=request.user)
            .select_related("unit", "unit__property")
            .order_by("-start_date")
        )

        if property_id:
            tenancy_qs = tenancy_qs.filter(unit__property_id=property_id)

        tenants = (
            Tenant.objects.filter(user=request.user)
            .annotate(
                total_rent=Sum("tenancies__monthly_rent_at_start"),
                unit_count=Count("tenancies", distinct=True)
            )
            .prefetch_related(
                Prefetch(
                    "tenancies_set",
                    queryset=tenancy_qs,
                    to_attr="prefetched_tenancies",
                )
            )
            .order_by("last_name", "first_name")
        )

        if property_id:
            tenants = tenants.filter(tenancies__unit__property_id=property_id)
        
        # Apply active filter (only tenants with units)
        if show_active_only:
            tenants = tenants.filter(unit_count__gt=0)
        
        # Apply search filter
        if search_query:
            tenants = tenants.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email_address__icontains=search_query)
            )

        return render(
            request,
            "storage/tenants/index.html",
            {
                "tenants": tenants,
                "properties": properties,
                "selected_property_id": property_id,
                "search_query": search_query,
                "show_active_only": show_active_only,
            },
        )


class TenantDetailView(SubscriptionRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request, tenant_id):
        tenant = get_object_or_404(
            Tenant.objects.filter(user=request.user)
            .annotate(
                total_rent=Sum("tenancies__monthly_rent_at_start"),
                unit_count=Count("tenancies", distinct=True)
            ),
            id=tenant_id
        )
        
        properties = Property.objects.filter(user=request.user).order_by("name")
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        
        tenancy_qs = (
            Tenancies.objects.filter(
                tenant=tenant,
                unit__property__user=request.user
            )
            .select_related("unit", "unit__property")
            .order_by("-start_date")
        )
        
        if property_id:
            tenancy_qs = tenancy_qs.filter(unit__property_id=property_id)
        
        tenant.prefetched_tenancies = list(tenancy_qs)
        
        # Get all tenants for the index template
        all_tenants = (
            Tenant.objects.filter(user=request.user)
            .annotate(
                total_rent=Sum("tenancies__monthly_rent_at_start"),
                unit_count=Count("tenancies", distinct=True)
            )
            .prefetch_related(
                Prefetch(
                    "tenancies_set",
                    queryset=Tenancies.objects.filter(unit__property__user=request.user)
                    .select_related("unit", "unit__property")
                    .order_by("-start_date"),
                    to_attr="prefetched_tenancies",
                )
            )
            .order_by("last_name", "first_name")
        )
        
        if property_id:
            all_tenants = all_tenants.filter(tenancies__unit__property_id=property_id)
        
        return render(
            request,
            "storage/tenants/detail.html",
            {
                "tenant": tenant,
                "tenants": all_tenants,
                "properties": properties,
                "selected_property_id": property_id,
            },
        )


class TenantEditView(SubscriptionRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request, tenant_id):
        tenant = get_object_or_404(
            Tenant.objects.filter(user=request.user)
            .annotate(
                total_rent=Sum("tenancies__monthly_rent_at_start"),
                unit_count=Count("tenancies", distinct=True)
            ),
            id=tenant_id
        )
        
        properties = Property.objects.filter(user=request.user).order_by("name")
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        
        form = TenantForm(instance=tenant)
        
        tenancy_qs = (
            Tenancies.objects.filter(
                tenant=tenant,
                unit__property__user=request.user
            )
            .select_related("unit", "unit__property")
            .order_by("-start_date")
        )
        
        if property_id:
            tenancy_qs = tenancy_qs.filter(unit__property_id=property_id)
        
        tenant.prefetched_tenancies = list(tenancy_qs)
        
        # Get all tenants for the index template
        all_tenants = (
            Tenant.objects.filter(user=request.user)
            .annotate(
                total_rent=Sum("tenancies__monthly_rent_at_start"),
                unit_count=Count("tenancies", distinct=True)
            )
            .prefetch_related(
                Prefetch(
                    "tenancies_set",
                    queryset=Tenancies.objects.filter(unit__property__user=request.user)
                    .select_related("unit", "unit__property")
                    .order_by("-start_date"),
                    to_attr="prefetched_tenancies",
                )
            )
            .order_by("last_name", "first_name")
        )
        
        if property_id:
            all_tenants = all_tenants.filter(tenancies__unit__property_id=property_id)
        
        return render(
            request,
            "storage/tenants/edit.html",
            {
                "tenant": tenant,
                "tenants": all_tenants,
                "properties": properties,
                "selected_property_id": property_id,
                "form": form,
            },
        )

    def post(self, request, tenant_id):
        tenant = get_object_or_404(
            Tenant.objects.filter(user=request.user),
            id=tenant_id
        )
        
        form = TenantForm(request.POST, instance=tenant)
        
        if form.is_valid():
            form.save()
            messages.success(request, "Tenant updated successfully.")
            return redirect("tenant_detail", tenant_id=tenant_id)
        
        properties = Property.objects.filter(user=request.user).order_by("name")
        raw_property_id = request.GET.get("property")
        property_id = _normalize_property_id(raw_property_id)
        
        # Re-annotate tenant
        tenant = get_object_or_404(
            Tenant.objects.filter(user=request.user)
            .annotate(
                total_rent=Sum("tenancies__monthly_rent_at_start"),
                unit_count=Count("tenancies", distinct=True)
            ),
            id=tenant_id
        )
        
        tenancy_qs = (
            Tenancies.objects.filter(
                tenant=tenant,
                unit__property__user=request.user
            )
            .select_related("unit", "unit__property")
            .order_by("-start_date")
        )
        
        if property_id:
            tenancy_qs = tenancy_qs.filter(unit__property_id=property_id)
        
        tenant.prefetched_tenancies = list(tenancy_qs)
        
        # Get all tenants for the index template
        all_tenants = (
            Tenant.objects.filter(user=request.user)
            .annotate(
                total_rent=Sum("tenancies__monthly_rent_at_start"),
                unit_count=Count("tenancies", distinct=True)
            )
            .prefetch_related(
                Prefetch(
                    "tenancies_set",
                    queryset=Tenancies.objects.filter(unit__property__user=request.user)
                    .select_related("unit", "unit__property")
                    .order_by("-start_date"),
                    to_attr="prefetched_tenancies",
                )
            )
            .order_by("last_name", "first_name")
        )
        
        if property_id:
            all_tenants = all_tenants.filter(tenancies__unit__property_id=property_id)
        
        return render(
            request,
            "storage/tenants/edit.html",
            {
                "tenant": tenant,
                "tenants": all_tenants,
                "properties": properties,
                "selected_property_id": property_id,
                "form": form,
            },
        )


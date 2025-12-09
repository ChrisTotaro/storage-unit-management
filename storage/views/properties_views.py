from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Count
from django.contrib import messages

from ..models import Property, Unit, Tenancies
from ..forms import PropertyForm, UnitForm
from .units_views import _get_units_context


class PropertyListView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request):
        properties = (
            Property.objects.filter(user=request.user)
            .annotate(unit_count=Count("unit"))
            .order_by("name")
        )
        return render(
            request,
            "storage/properties/index.html",
            {
                "properties": properties,
            },
        )


class PropertyDetailView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request, property_id):
        property_obj = get_object_or_404(Property, id=property_id, user=request.user)
        
        # Get properties list for the index template
        properties = (
            Property.objects.filter(user=request.user)
            .annotate(unit_count=Count("unit"))
            .order_by("name")
        )
        
        tenancies_prefetch = Prefetch(
            "tenancies_set",
            queryset=Tenancies.objects.select_related("tenant").order_by("-start_date"),
            to_attr="prefetched_tenancies",
        )
        
        units = (
            Unit.objects.filter(property=property_obj)
            .prefetch_related(tenancies_prefetch)
            .order_by("unit_number")
        )
        
        # Create unit form with property pre-selected
        unit_form = UnitForm(user=request.user, initial={"property": property_obj})
        
        return render(
            request,
            "storage/properties/detail.html",
            {
                "property": property_obj,
                "units": units,
                "properties": properties,
                "unit_form": unit_form,
            },
        )

    def post(self, request, property_id):
        property_obj = get_object_or_404(Property, id=property_id, user=request.user)
        form = UnitForm(request.POST, user=request.user)
        
        if form.is_valid():
            unit = form.save()
            messages.success(request, "Unit added successfully.")
            return redirect("property_detail", property_id=property_id)
        
        # Get properties list for the index template
        properties = (
            Property.objects.filter(user=request.user)
            .annotate(unit_count=Count("unit"))
            .order_by("name")
        )
        
        tenancies_prefetch = Prefetch(
            "tenancies_set",
            queryset=Tenancies.objects.select_related("tenant").order_by("-start_date"),
            to_attr="prefetched_tenancies",
        )
        
        units = (
            Unit.objects.filter(property=property_obj)
            .prefetch_related(tenancies_prefetch)
            .order_by("unit_number")
        )
        
        return render(
            request,
            "storage/properties/detail.html",
            {
                "property": property_obj,
                "units": units,
                "properties": properties,
                "unit_form": form,
            },
        )


class PropertyCreateView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request):
        properties = (
            Property.objects.filter(user=request.user)
            .annotate(unit_count=Count("unit"))
            .order_by("name")
        )
        form = PropertyForm()
        return render(
            request,
            "storage/properties/add.html",
            {
                "properties": properties,
                "form": form,
            },
        )

    def post(self, request):
        form = PropertyForm(request.POST)
        if form.is_valid():
            property_obj = form.save(commit=False)
            property_obj.user = request.user
            property_obj.save()
            messages.success(request, "Property added successfully.")
            return redirect("property_detail", property_id=property_obj.id)
        
        properties = (
            Property.objects.filter(user=request.user)
            .annotate(unit_count=Count("unit"))
            .order_by("name")
        )
        return render(
            request,
            "storage/properties/add.html",
            {
                "properties": properties,
                "form": form,
            },
        )


class PropertyEditView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request, property_id):
        property_obj = get_object_or_404(Property, id=property_id, user=request.user)
        
        # Get properties list for the index template
        properties = (
            Property.objects.filter(user=request.user)
            .annotate(unit_count=Count("unit"))
            .order_by("name")
        )
        
        tenancies_prefetch = Prefetch(
            "tenancies_set",
            queryset=Tenancies.objects.select_related("tenant").order_by("-start_date"),
            to_attr="prefetched_tenancies",
        )
        
        units = (
            Unit.objects.filter(property=property_obj)
            .prefetch_related(tenancies_prefetch)
            .order_by("unit_number")
        )
        
        form = PropertyForm(instance=property_obj)
        
        return render(
            request,
            "storage/properties/edit.html",
            {
                "property": property_obj,
                "units": units,
                "form": form,
                "properties": properties,
            },
        )

    def post(self, request, property_id):
        property_obj = get_object_or_404(Property, id=property_id, user=request.user)
        form = PropertyForm(request.POST, instance=property_obj)
        
        if form.is_valid():
            form.save()
            messages.success(request, "Property updated successfully.")
            return redirect("property_detail", property_id=property_id)
        
        # Get properties list for the index template
        properties = (
            Property.objects.filter(user=request.user)
            .annotate(unit_count=Count("unit"))
            .order_by("name")
        )
        
        tenancies_prefetch = Prefetch(
            "tenancies_set",
            queryset=Tenancies.objects.select_related("tenant").order_by("-start_date"),
            to_attr="prefetched_tenancies",
        )
        
        units = (
            Unit.objects.filter(property=property_obj)
            .prefetch_related(tenancies_prefetch)
            .order_by("unit_number")
        )
        
        return render(
            request,
            "storage/properties/edit.html",
            {
                "property": property_obj,
                "units": units,
                "form": form,
                "properties": properties,
            },
        )


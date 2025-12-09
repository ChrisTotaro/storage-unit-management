from django.views import View
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Q, Prefetch
from django.utils import timezone
from datetime import timedelta

from ..models import Property, Unit, Tenant, Tenancies


class DashboardView(LoginRequiredMixin, View):
    login_url = "account_login"
    redirect_field_name = "next"

    def get(self, request):
        # Get all properties for this user
        properties = Property.objects.filter(user=request.user)
        
        # Get all units for this user
        units = Unit.objects.filter(property__user=request.user).select_related('property')
        
        # Get all active tenants (through current tenancies)
        today = timezone.now().date()
        active_tenancy_ids = Tenancies.objects.filter(
            unit__property__user=request.user,
            start_date__lte=today,
            end_date__gte=today
        ).values_list('tenant_id', flat=True).distinct()
        active_tenant_count = len(set(active_tenancy_ids))
        
        # Calculate key metrics
        total_properties = properties.count()
        total_units = units.count()
        occupied_units = units.filter(status=Unit.STATUS_OCCUPIED).count()
        vacant_units = units.filter(status=Unit.STATUS_VACANT).count()
        
        # Calculate monthly revenue from occupied units
        monthly_revenue = units.filter(
            status=Unit.STATUS_OCCUPIED
        ).aggregate(total=Sum('monthly_rent'))['total'] or 0
        
        # Calculate occupancy rate
        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        
        # Get recent units (last 10)
        recent_units = units.order_by('-created_at')[:10]
        
        # Get recent tenants (last 10, based on tenancy creation)
        recent_tenancies = Tenancies.objects.filter(
            unit__property__user=request.user
        ).select_related('tenant', 'unit', 'unit__property').order_by('-created_at')[:10]
        
        # Get upcoming lease expirations (next 30 days)
        thirty_days_from_now = today + timedelta(days=30)
        upcoming_expirations_raw = Tenancies.objects.filter(
            unit__property__user=request.user,
            end_date__gte=today,
            end_date__lte=thirty_days_from_now
        ).select_related('tenant', 'unit', 'unit__property').order_by('end_date')[:10]
        
        # Add days_until_expiration to each tenancy
        upcoming_expirations = []
        for tenancy in upcoming_expirations_raw:
            days_until = (tenancy.end_date - today).days
            upcoming_expirations.append({
                'tenancy': tenancy,
                'days_until': days_until,
                'days_ago': abs(days_until) if days_until < 0 else 0,
                'is_expired': days_until < 0,
                'is_today': days_until == 0,
                'is_urgent': days_until <= 7 and days_until >= 0,
            })
        
        # Get properties with unit counts
        properties_with_counts = properties.annotate(
            unit_count=Count('unit'),
            occupied_count=Count('unit', filter=Q(unit__status=Unit.STATUS_OCCUPIED)),
            vacant_count=Count('unit', filter=Q(unit__status=Unit.STATUS_VACANT)),
            total_revenue=Sum('unit__monthly_rent', filter=Q(unit__status=Unit.STATUS_OCCUPIED))
        ).order_by('-unit_count')[:5]
        
        # Get units that have been vacant for a while (30+ days)
        # We'll check units that are vacant and have no recent tenancies
        vacant_units_list = units.filter(status=Unit.STATUS_VACANT).select_related('property')
        units_needing_attention = []
        for unit in vacant_units_list:
            last_tenancy = Tenancies.objects.filter(unit=unit).order_by('-end_date').first()
            if last_tenancy:
                days_vacant = (today - last_tenancy.end_date).days
                if days_vacant >= 30:
                    units_needing_attention.append({
                        'unit': unit,
                        'days_vacant': days_vacant
                    })
            else:
                # Unit has never been occupied
                days_since_created = (today - unit.created_at.date()).days
                if days_since_created >= 30:
                    units_needing_attention.append({
                        'unit': unit,
                        'days_vacant': days_since_created
                    })
        
        # Sort by days vacant (most first) and take top 5
        units_needing_attention.sort(key=lambda x: x['days_vacant'], reverse=True)
        units_needing_attention = units_needing_attention[:5]
        
        context = {
            'total_properties': total_properties,
            'total_units': total_units,
            'occupied_units': occupied_units,
            'vacant_units': vacant_units,
            'monthly_revenue': monthly_revenue,
            'occupancy_rate': round(occupancy_rate, 1),
            'active_tenant_count': active_tenant_count,
            'recent_units': recent_units,
            'recent_tenancies': recent_tenancies,
            'upcoming_expirations': upcoming_expirations,
            'properties_with_counts': properties_with_counts,
            'units_needing_attention': units_needing_attention,
            'today': today,
        }
        
        return render(request, 'storage/dashboard/index.html', context)

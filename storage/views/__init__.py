# Views package
from .dashboard_views import DashboardView
from .units_views import IndexView, UnitCreateView, UnitDetailView, UnitEditView, UnitAssignTenantView, UnitCreateAndAssignTenantView, UnitRemoveTenantView
from .tenants_views import TenantListView, TenantCreateView, TenantDetailView, TenantEditView
from .properties_views import PropertyListView, PropertyDetailView, PropertyCreateView, PropertyEditView

__all__ = [
    'DashboardView',
    'IndexView',
    'UnitCreateView',
    'UnitDetailView',
    'UnitEditView',
    'UnitAssignTenantView',
    'UnitCreateAndAssignTenantView',
    'UnitRemoveTenantView',
    'TenantListView',
    'TenantCreateView',
    'TenantDetailView',
    'TenantEditView',
    'PropertyListView',
    'PropertyDetailView',
    'PropertyCreateView',
    'PropertyEditView',
]

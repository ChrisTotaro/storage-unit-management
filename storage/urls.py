from django.urls import path, include
from .views import IndexView, TenantListView, UnitCreateView

urlpatterns = [

    path('', IndexView.as_view(), name="index"),
    path('units/new/', UnitCreateView.as_view(), name="unit_add"),
    path('tenants/', TenantListView.as_view(), name="tenants"),
]
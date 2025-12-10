from django.urls import path, include
from .subscription_views import (
    SubscriptionRequiredView,
    SubscriptionStatusView,
    SubscriptionCheckoutView,
    SubscriptionSuccessView,
    SubscriptionCancelView,
)
from .profile_views import ProfileView
from .webhooks import stripe_webhook

urlpatterns = [
    path("", include("allauth.urls")),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("subscription/required/", SubscriptionRequiredView.as_view(), name="subscription_required"),
    path("subscription/", SubscriptionStatusView.as_view(), name="subscription_status"),
    path("subscription/checkout/", SubscriptionCheckoutView.as_view(), name="subscription_checkout"),
    path("subscription/success/", SubscriptionSuccessView.as_view(), name="subscription_success"),
    path("subscription/cancel/", SubscriptionCancelView.as_view(), name="subscription_cancel"),
    path("webhooks/stripe/", stripe_webhook, name="stripe_webhook"),
]


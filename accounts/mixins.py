from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class SubscriptionRequiredMixin(LoginRequiredMixin):
    """
    Mixin that requires user to have an active subscription.
    Redirects to subscription page if subscription is not active.
    """
    subscription_required_url = "subscription_required"
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Staff and superusers always have access
        if request.user.is_staff or request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        
        # Check if user has active subscription
        if not request.user.has_active_subscription():
            messages.warning(
                request,
                "An active subscription is required to access this feature."
            )
            return redirect(self.subscription_required_url)
        
        return super().dispatch(request, *args, **kwargs)


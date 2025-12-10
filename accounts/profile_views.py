from django.views import View
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect

from .models import Subscription


class ProfileView(LoginRequiredMixin, View):
    """User profile and settings page"""
    login_url = "account_login"
    redirect_field_name = "next"
    
    def get(self, request):
        subscription = request.user.get_subscription()
        
        context = {
            'user': request.user,
            'subscription': subscription,
            'has_subscription': subscription is not None,
            'has_active_subscription': request.user.has_active_subscription(),
        }
        
        return render(
            request,
            "account/profile.html",
            context
        )


from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import stripe
import logging

from .models import Subscription, CustomUser

logger = logging.getLogger(__name__)

# Initialize Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


class SubscriptionRequiredView(LoginRequiredMixin, View):
    """View shown when user tries to access feature without subscription"""
    login_url = "account_login"
    redirect_field_name = "next"
    
    def get(self, request):
        subscription = request.user.get_subscription()
        return render(
            request,
            "account/subscription_required.html",
            {
                "subscription": subscription,
                "has_subscription": subscription is not None,
            }
        )


class SubscriptionStatusView(LoginRequiredMixin, View):
    """View to show current subscription status"""
    login_url = "account_login"
    redirect_field_name = "next"
    
    def get(self, request):
        subscription = request.user.get_subscription()
        return render(
            request,
            "account/subscription_status.html",
            {
                "subscription": subscription,
                "has_subscription": subscription is not None,
            }
        )


class SubscriptionCheckoutView(LoginRequiredMixin, View):
    """View to handle subscription checkout (Stripe integration)"""
    login_url = "account_login"
    redirect_field_name = "next"
    
    def get(self, request):
        if not settings.STRIPE_SECRET_KEY or not settings.SUBSCRIPTION_PRICE_ID:
            messages.error(
                request,
                "Stripe is not configured. Please contact support."
            )
            return redirect("subscription_status")
        
        # Validate that it's a Price ID, not a Product ID
        price_id = settings.SUBSCRIPTION_PRICE_ID
        if price_id.startswith('prod_'):
            messages.error(
                request,
                "Configuration error: SUBSCRIPTION_PRICE_ID is set to a Product ID. "
                "Please use a Price ID (starts with 'price_') instead. "
                "You can find the Price ID in your Stripe Dashboard under Products > Your Product > Pricing."
            )
            return redirect("subscription_status")
        
        return render(
            request,
            "account/subscription_checkout.html",
            {
                "stripe_public_key": settings.STRIPE_PUBLISHABLE_KEY,
            }
        )
    
    def post(self, request):
        """Create Stripe Checkout Session"""
        if not settings.STRIPE_SECRET_KEY or not settings.SUBSCRIPTION_PRICE_ID:
            messages.error(
                request,
                "Stripe is not configured. Please contact support."
            )
            return redirect("subscription_status")
        
        try:
            # Get or create Stripe customer
            subscription = request.user.get_subscription()
            customer_id = None
            
            if subscription and subscription.stripe_customer_id:
                customer_id = subscription.stripe_customer_id
            else:
                # Create new Stripe customer
                customer = stripe.Customer.create(
                    email=request.user.email,
                    metadata={
                        'user_id': str(request.user.id),
                    }
                )
                customer_id = customer.id
                
                # Update or create subscription record with customer ID
                if subscription:
                    subscription.stripe_customer_id = customer_id
                    subscription.save()
                else:
                    subscription = Subscription.objects.create(
                        user=request.user,
                        stripe_customer_id=customer_id,
                        status=Subscription.STATUS_INCOMPLETE
                    )
            
            # Create checkout session
            checkout_params = {
                'customer': customer_id,
                'payment_method_types': ['card'],
                'line_items': [{
                    'price': settings.SUBSCRIPTION_PRICE_ID,
                    'quantity': 1,
                }],
                'mode': 'subscription',
                'success_url': request.build_absolute_uri(
                    reverse('subscription_success')
                ) + '?session_id={CHECKOUT_SESSION_ID}',
                'cancel_url': request.build_absolute_uri(
                    reverse('subscription_status')
                ),
                'metadata': {
                    'user_id': str(request.user.id),
                }
            }
            
            # Add trial period if configured
            if settings.SUBSCRIPTION_TRIAL_DAYS > 0:
                checkout_params['subscription_data'] = {
                    'trial_period_days': settings.SUBSCRIPTION_TRIAL_DAYS,
                }
            
            checkout_session = stripe.checkout.Session.create(**checkout_params)
            
            # Redirect to Stripe Checkout
            return redirect(checkout_session.url)
            
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Stripe error in checkout: {str(e)}")
            # Check if it's a price ID error
            if 'price' in str(e).lower() and 'no such' in str(e).lower():
                messages.error(
                    request,
                    "Invalid Price ID configured. Please check your SUBSCRIPTION_PRICE_ID environment variable. "
                    "Make sure you're using a Price ID (starts with 'price_'), not a Product ID (starts with 'prod_')."
                )
            else:
                messages.error(
                    request,
                    f"An error occurred while processing your request: {str(e)}"
                )
            return redirect("subscription_status")
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error in checkout: {str(e)}")
            messages.error(
                request,
                f"An error occurred while processing your request: {str(e)}"
            )
            return redirect("subscription_status")
        except Exception as e:
            logger.error(f"Error in checkout: {str(e)}")
            messages.error(
                request,
                "An unexpected error occurred. Please try again later."
            )
            return redirect("subscription_status")


class SubscriptionSuccessView(LoginRequiredMixin, View):
    """View shown after successful subscription"""
    login_url = "account_login"
    redirect_field_name = "next"
    
    def get(self, request):
        session_id = request.GET.get("session_id")
        
        if not session_id:
            messages.warning(
                request,
                "No checkout session found. Your subscription may still be processing."
            )
            return redirect("subscription_status")
        
        try:
            # Retrieve the checkout session from Stripe
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            
            # Verify it belongs to this user
            subscription = request.user.get_subscription()
            if subscription and subscription.stripe_customer_id:
                if checkout_session.customer != subscription.stripe_customer_id:
                    messages.error(
                        request,
                        "Invalid checkout session."
                    )
                    return redirect("subscription_status")
            
            # The webhook will handle the actual subscription update
            # This view just confirms the checkout was successful
            if checkout_session.payment_status == 'paid' or checkout_session.subscription:
                messages.success(
                    request,
                    "Checkout completed successfully! Your subscription is being activated."
                )
            else:
                messages.info(
                    request,
                    "Checkout session created. Your subscription will be activated once payment is confirmed."
                )
        
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error in success view: {str(e)}")
            messages.info(
                request,
                "Your subscription is being processed. You'll receive a confirmation email shortly."
            )
        except Exception as e:
            logger.error(f"Error in success view: {str(e)}")
            messages.info(
                request,
                "Your subscription is being processed. Please check back in a few moments."
            )
        
        return redirect("subscription_status")


class SubscriptionCancelView(LoginRequiredMixin, View):
    """View to cancel subscription"""
    login_url = "account_login"
    redirect_field_name = "next"
    
    def post(self, request):
        subscription = get_object_or_404(
            Subscription,
            user=request.user
        )
        
        if not subscription.stripe_subscription_id:
            messages.error(
                request,
                "No active Stripe subscription found."
            )
            return redirect("subscription_status")
        
        try:
            # Cancel subscription at period end via Stripe
            stripe_subscription = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            # Update local subscription record
            subscription.cancel_at_period_end = True
            subscription.status = stripe_subscription.status
            subscription.save()
            
            messages.info(
                request,
                "Your subscription will be canceled at the end of the current billing period."
            )
        
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error canceling subscription: {str(e)}")
            messages.error(
                request,
                f"An error occurred while canceling your subscription: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error canceling subscription: {str(e)}")
            messages.error(
                request,
                "An unexpected error occurred. Please try again later."
            )
        
        return redirect("subscription_status")


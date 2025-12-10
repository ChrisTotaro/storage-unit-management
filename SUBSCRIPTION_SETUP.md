# Subscription System Setup Guide

This application now includes a subscription system that requires users to have an active subscription to access features.

## What's Been Implemented

1. **Subscription Model** (`accounts/models.py`)
   - Tracks user subscriptions with status, billing periods, and Stripe IDs
   - Supports trial periods, cancellation, and renewal tracking

2. **SubscriptionRequiredMixin** (`accounts/mixins.py`)
   - Mixin that protects views requiring an active subscription
   - Automatically redirects to subscription page if user doesn't have access
   - Staff/superusers always have access (bypass subscription check)

3. **Subscription Views** (`accounts/subscription_views.py`)
   - Subscription status page
   - Subscription checkout page (needs Stripe integration)
   - Subscription cancellation
   - Subscription required page (shown when access is denied)

4. **All Views Updated**
   - All storage app views now use `SubscriptionRequiredMixin`
   - Users without active subscriptions will be redirected to subscription page

## Setup Steps

### 1. Create and Run Migrations

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

### 2. Install Stripe (Optional but Recommended)

```bash
pip install stripe
```

### 3. Configure Stripe Settings

Add to your `config/settings.py` or environment variables:

```python
# Get these from https://dashboard.stripe.com/apikeys
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# Your Stripe Price ID for the subscription product
SUBSCRIPTION_PRICE_ID = os.environ.get('SUBSCRIPTION_PRICE_ID', '')
SUBSCRIPTION_TRIAL_DAYS = 0  # Set to number of trial days (0 to disable)
```

### 4. Create Stripe Products and Prices

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
2. Create a Product for your subscription
3. Create a Price for that product (monthly/yearly)
4. Copy the Price ID and add it to `SUBSCRIPTION_PRICE_ID` in settings

### 5. Implement Stripe Checkout (TODO)

The checkout view (`accounts/subscription_views.py`) needs to be implemented with actual Stripe integration:

```python
import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY

def post(self, request):
    checkout_session = stripe.checkout.Session.create(
        customer_email=request.user.email,
        payment_method_types=['card'],
        line_items=[{
            'price': settings.SUBSCRIPTION_PRICE_ID,
            'quantity': 1,
        }],
        mode='subscription',
        success_url=request.build_absolute_uri(
            reverse('subscription_success')
        ) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=request.build_absolute_uri(
            reverse('subscription_status')
        ),
    )
    return redirect(checkout_session.url)
```

### 6. Set Up Stripe Webhooks

You'll need to create webhook handlers for:
- `customer.subscription.created` - Create subscription record
- `customer.subscription.updated` - Update subscription status
- `customer.subscription.deleted` - Mark subscription as canceled
- `invoice.payment_succeeded` - Update billing period
- `invoice.payment_failed` - Handle failed payments

Example webhook view:

```python
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    
    # Handle events
    if event['type'] == 'customer.subscription.created':
        # Create subscription
        pass
    elif event['type'] == 'customer.subscription.updated':
        # Update subscription
        pass
    
    return HttpResponse(status=200)
```

### 7. Grant Access to Existing Users (Optional)

If you want to grant subscriptions to existing users, you can do so via Django shell:

```python
from accounts.models import CustomUser, Subscription
from django.utils import timezone
from datetime import timedelta

# Grant subscription to a user
user = CustomUser.objects.get(email='user@example.com')
subscription = Subscription.objects.create(
    user=user,
    status=Subscription.STATUS_ACTIVE,
    current_period_start=timezone.now(),
    current_period_end=timezone.now() + timedelta(days=30)
)
```

Or grant to all existing users:

```python
from accounts.models import CustomUser, Subscription
from django.utils import timezone
from datetime import timedelta

for user in CustomUser.objects.all():
    if not hasattr(user, 'subscription'):
        Subscription.objects.create(
            user=user,
            status=Subscription.STATUS_ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
```

## Testing Without Stripe

For development/testing, you can manually create subscriptions in the Django admin or shell without Stripe integration. The system will work, but checkout won't be functional until Stripe is integrated.

## URLs Added

- `/accounts/subscription/required/` - Shown when subscription is required
- `/accounts/subscription/` - View subscription status
- `/accounts/subscription/checkout/` - Subscribe/checkout page
- `/accounts/subscription/success/` - Success page after checkout
- `/accounts/subscription/cancel/` - Cancel subscription

## Notes

- Staff and superusers automatically bypass subscription checks
- The subscription system is fully functional but needs Stripe integration for payment processing
- All existing views now require an active subscription
- Users will see a clear message when subscription is required


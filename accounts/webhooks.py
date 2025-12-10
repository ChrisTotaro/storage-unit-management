"""
Stripe webhook handlers for subscription events
"""
import stripe
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone as django_timezone
from datetime import datetime, timezone as dt_timezone

from .models import Subscription, CustomUser

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhook events
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("Stripe webhook secret not configured")
        return JsonResponse({"error": "Webhook secret not configured"}, status=400)

    if not sig_header:
        logger.error("Missing Stripe signature header")
        return JsonResponse({"error": "Missing signature header"}, status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        print("Event: ", event)
    except ValueError as e:
        logger.error(f"Invalid payload: {str(e)}")
        return JsonResponse({"error": f"Invalid payload: {str(e)}"}, status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {str(e)}")
        logger.error(f"Expected secret: {settings.STRIPE_WEBHOOK_SECRET[:10]}...")
        logger.error(
            "If using Stripe CLI, make sure you're using the webhook secret from 'stripe listen' output"
        )
        return JsonResponse(
            {
                "error": "Invalid signature",
                "hint": 'If using Stripe CLI locally, use the webhook secret from the "stripe listen" output (starts with whsec_)',
            },
            status=400,
        )

    # Handle the event
    event_type = event["type"]
    event_data = event["data"]["object"]

    logger.info(f"Received Stripe webhook: {event_type}")

    try:
        if event_type == "customer.subscription.created":
            handle_subscription_created(event_data)
        elif event_type == "customer.subscription.updated":
            handle_subscription_updated(event_data)
        elif event_type == "customer.subscription.deleted":
            handle_subscription_deleted(event_data)
        elif event_type in ("invoice.paid", "invoice.payment_succeeded"):
            # Either of these means the invoice is fully paid
            handle_invoice_payment_succeeded(event_data)
        elif event_type == "invoice.payment_failed":
            handle_invoice_payment_failed(event_data)
        elif event_type == "checkout.session.completed":
            handle_checkout_session_completed(event_data)
        else:
            logger.info(f"Unhandled event type: {event_type}")

    except Exception as e:
        logger.error(f"Error handling webhook {event_type}: {str(e)}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"status": "success"})


def handle_subscription_created(subscription_data):
    """Handle customer.subscription.created event"""
    subscription_dict = (
        subscription_data
        if isinstance(subscription_data, dict)
        else subscription_data.to_dict()
    )

    stripe_subscription_id = subscription_dict.get("id")
    stripe_customer_id = subscription_dict.get("customer")

    logger.info(
        f"Subscription created: {stripe_subscription_id} for customer {stripe_customer_id}"
    )

    # Find user by customer ID
    try:
        subscription = Subscription.objects.get(stripe_customer_id=stripe_customer_id)
        logger.info(
            f"Found existing subscription {subscription.id} for customer {stripe_customer_id}"
        )
    except Subscription.DoesNotExist:
        logger.info(
            f"Subscription not found, retrieving customer {stripe_customer_id} from Stripe"
        )
        customer = stripe.Customer.retrieve(stripe_customer_id)
        user_id = customer.metadata.get("user_id")

        if user_id:
            try:
                user = CustomUser.objects.get(id=user_id)
                subscription = Subscription.objects.create(
                    user=user,
                    stripe_customer_id=stripe_customer_id,
                    stripe_subscription_id=stripe_subscription_id,
                    status=subscription_dict.get(
                        "status", Subscription.STATUS_INCOMPLETE
                    ),
                )
                logger.info(
                    f"Created new subscription {subscription.id} for user {user_id}"
                )
            except CustomUser.DoesNotExist:
                logger.error(f"User not found for customer {stripe_customer_id}")
                return
        else:
            logger.error(
                f"Could not find subscription or user for customer {stripe_customer_id}"
            )
            return

    # Update subscription basic fields from Stripe object
    update_subscription_from_stripe(subscription, subscription_dict)


def handle_subscription_updated(subscription_data):
    """Handle customer.subscription.updated event"""
    if hasattr(subscription_data, "to_dict"):
        subscription_dict = subscription_data.to_dict()
    elif hasattr(subscription_data, "get"):
        subscription_dict = subscription_data
    else:
        subscription_dict = dict(subscription_data)

    stripe_subscription_id = subscription_dict.get("id")

    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=stripe_subscription_id
        )
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found: {stripe_subscription_id}")
        return

    update_subscription_from_stripe(subscription, subscription_dict)


def handle_subscription_deleted(subscription_data):
    """Handle customer.subscription.deleted event"""
    stripe_subscription_id = (
        subscription_data.get("id")
        if isinstance(subscription_data, dict)
        else getattr(subscription_data, "id", None)
    )

    if not stripe_subscription_id:
        logger.warning("Subscription deleted event without id")
        return

    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=stripe_subscription_id
        )
        subscription.status = Subscription.STATUS_CANCELED
        subscription.cancel_at_period_end = False
        subscription.current_period_end = django_timezone.now()
        subscription.save()
        logger.info(f"Subscription {stripe_subscription_id} marked as canceled")
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found: {stripe_subscription_id}")


def _extract_period_dates_from_subscription(sub_dict):
    """
    Handles both classic and flexible billing shapes.

    Priority:
    1) Top-level current_period_start / current_period_end (classic).
    2) First item's current_period_start / current_period_end (flexible).
    3) First item's period.start / period.end (older line-item shape).
    """
    # 1) Try top-level fields first
    start = sub_dict.get("current_period_start")
    end = sub_dict.get("current_period_end")

    items = sub_dict.get("items") or {}
    data = items.get("data") or []

    if data:
        item = data[0] or {}
        # 2) Flexible billing: item.current_period_*
        if not start:
            start = item.get("current_period_start")
        if not end:
            end = item.get("current_period_end")

        # 3) Older shape: item.period.start / item.period.end
        period = item.get("period") or {}
        if not start:
            start = period.get("start")
        if not end:
            end = period.get("end")

    return start, end


def handle_invoice_payment_succeeded(invoice_data):
    """
    Handle invoice.paid / invoice.payment_succeeded event.
    
    Important: Always retrieve the subscription from Stripe API to get the 
    authoritative billing period. For flexible billing, the period may
    live on the subscription item instead of the top-level object.
    """
    subscription_id = invoice_data.get("subscription")

    if not subscription_id:
        # e.g. one-off invoice, ignore
        return

    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=subscription_id
        )
    except Subscription.DoesNotExist:
        logger.warning(
            f"Subscription not found for invoice subscription id: {subscription_id}"
        )
        return

    # Mark subscription as active on successful payment
    subscription.status = Subscription.STATUS_ACTIVE

    # Always retrieve subscription from Stripe to get the authoritative billing period
    try:
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        stripe_sub_dict = (
            stripe_sub.to_dict() if hasattr(stripe_sub, "to_dict") else stripe_sub
        )

        current_period_start, current_period_end = _extract_period_dates_from_subscription(
            stripe_sub_dict
        )

        logger.info(
            f"Retrieved subscription {subscription_id} from Stripe: "
            f"period_start={current_period_start}, period_end={current_period_end}"
        )

        if current_period_start:
            subscription.current_period_start = datetime.fromtimestamp(
                current_period_start, tz=dt_timezone.utc
            )
        if current_period_end:
            subscription.current_period_end = datetime.fromtimestamp(
                current_period_end, tz=dt_timezone.utc
            )

        logger.info(
            f"Updated billing period from subscription API: "
            f"start={subscription.current_period_start}, end={subscription.current_period_end}"
        )
    except Exception as e:
        logger.error(
            f"Could not retrieve subscription from Stripe: {str(e)}", exc_info=True
        )
        # Fallback: try invoice-level period fields if present
        period_start_ts = invoice_data.get("period_start")
        period_end_ts = invoice_data.get("period_end")

        if period_start_ts:
            subscription.current_period_start = datetime.fromtimestamp(
                period_start_ts, tz=dt_timezone.utc
            )
        if period_end_ts:
            subscription.current_period_end = datetime.fromtimestamp(
                period_end_ts, tz=dt_timezone.utc
            )
        logger.warning("Used invoice period as fallback (subscription retrieval failed)")

    subscription.save()
    logger.info(
        f"Updated billing period for subscription {subscription_id}: "
        f"{subscription.current_period_start} -> {subscription.current_period_end}"
    )


def handle_invoice_payment_failed(invoice_data):
    """Handle invoice.payment_failed event"""
    subscription_id = invoice_data.get("subscription")

    if not subscription_id:
        return

    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=subscription_id
        )
        subscription.status = Subscription.STATUS_PAST_DUE
        subscription.save()
        logger.info(f"Subscription {subscription_id} marked as past due")
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found: {subscription_id}")


def handle_checkout_session_completed(session_data):
    """Handle checkout.session.completed event"""
    subscription_id = session_data.get("subscription")
    customer_id = session_data.get("customer")

    logger.info(
        f"Checkout session completed: subscription_id={subscription_id}, customer_id={customer_id}"
    )

    if not subscription_id:
        logger.warning("No subscription_id in checkout.session.completed event")
        return

    try:
        subscription = Subscription.objects.get(stripe_customer_id=customer_id)
        subscription.stripe_subscription_id = subscription_id

        # Retrieve subscription details mainly to sync status / cancel flags
        logger.info(f"Retrieving subscription {subscription_id} from Stripe")
        stripe_subscription = stripe.Subscription.retrieve(subscription_id)
        subscription_dict = (
            stripe_subscription.to_dict()
            if hasattr(stripe_subscription, "to_dict")
            else dict(stripe_subscription)
        )

        update_subscription_from_stripe(subscription, subscription_dict)

        logger.info(f"Checkout completed for subscription {subscription_id}")
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found for customer {customer_id}")
    except Exception as e:
        logger.error(
            f"Error in handle_checkout_session_completed: {str(e)}", exc_info=True
        )


def update_subscription_from_stripe(subscription, subscription_data):
    """
    Update subscription model from Stripe subscription data.
    
    Always retrieves the subscription from Stripe API to get the authoritative
    billing period. For flexible billing, period dates may live on the
    subscription item instead of the top-level object.
    """
    if hasattr(subscription_data, "get"):
        data_dict = subscription_data
    else:
        data_dict = (
            subscription_data.to_dict()
            if hasattr(subscription_data, "to_dict")
            else dict(subscription_data)
        )

    # Status + ID
    subscription.status = map_stripe_status_to_model(
        data_dict.get("status", "incomplete")
    )

    stripe_sub_id = data_dict.get("id")
    if stripe_sub_id:
        subscription.stripe_subscription_id = stripe_sub_id

    # Always retrieve subscription from Stripe API to get authoritative period dates
    subscription_id_to_retrieve = subscription.stripe_subscription_id or stripe_sub_id
    if subscription_id_to_retrieve:
        try:
            logger.info(
                f"Retrieving subscription {subscription_id_to_retrieve} from Stripe API for period dates"
            )
            stripe_sub = stripe.Subscription.retrieve(subscription_id_to_retrieve)
            stripe_sub_dict = (
                stripe_sub.to_dict() if hasattr(stripe_sub, "to_dict") else stripe_sub
            )

            current_period_start, current_period_end = _extract_period_dates_from_subscription(
                stripe_sub_dict
            )

            logger.info(
                f"Retrieved from API - period_start: {current_period_start}, "
                f"period_end: {current_period_end}"
            )

            if current_period_start:
                subscription.current_period_start = datetime.fromtimestamp(
                    current_period_start, tz=dt_timezone.utc
                )
            if current_period_end:
                subscription.current_period_end = datetime.fromtimestamp(
                    current_period_end, tz=dt_timezone.utc
                )

            logger.info(
                f"Retrieved period dates from Stripe API: "
                f"start={subscription.current_period_start}, "
                f"end={subscription.current_period_end}"
            )
        except Exception as e:
            logger.warning(
                f"Could not retrieve subscription from API: {str(e)}", exc_info=True
            )
            # Fallback to whatever is on data_dict (classic shape)
            if data_dict.get("current_period_start"):
                subscription.current_period_start = datetime.fromtimestamp(
                    data_dict.get("current_period_start"), tz=dt_timezone.utc
                )
            if data_dict.get("current_period_end"):
                subscription.current_period_end = datetime.fromtimestamp(
                    data_dict.get("current_period_end"), tz=dt_timezone.utc
                )

    # Trial end
    trial_end = data_dict.get("trial_end")
    if trial_end:
        subscription.trial_end = datetime.fromtimestamp(
            trial_end, tz=dt_timezone.utc
        )

    # Cancel at period end flag
    subscription.cancel_at_period_end = data_dict.get(
        "cancel_at_period_end", False
    )

    subscription.save()
    logger.info(
        f"Updated subscription {subscription.id} from Stripe: "
        f"status={subscription.status}, period_end={subscription.current_period_end}, "
        f"cancel_at_period_end={subscription.cancel_at_period_end}"
    )


def map_stripe_status_to_model(stripe_status):
    """Map Stripe subscription status to model status"""
    status_map = {
        "active": Subscription.STATUS_ACTIVE,
        "canceled": Subscription.STATUS_CANCELED,
        "past_due": Subscription.STATUS_PAST_DUE,
        "unpaid": Subscription.STATUS_UNPAID,
        "trialing": Subscription.STATUS_TRIALING,
        "incomplete": Subscription.STATUS_INCOMPLETE,
        "incomplete_expired": Subscription.STATUS_INCOMPLETE_EXPIRED,
    }
    return status_map.get(stripe_status, Subscription.STATUS_INCOMPLETE)

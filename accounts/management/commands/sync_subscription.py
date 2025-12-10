"""
Management command to manually sync a subscription from Stripe
Usage: python manage.py sync_subscription <user_email>
"""
from django.core.management.base import BaseCommand, CommandError
from accounts.models import CustomUser, Subscription
import stripe
from django.conf import settings
from accounts.webhooks import update_subscription_from_stripe


class Command(BaseCommand):
    help = 'Manually sync a subscription from Stripe'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='User email address')

    def handle(self, *args, **options):
        email = options['email']
        
        if not settings.STRIPE_SECRET_KEY:
            raise CommandError('STRIPE_SECRET_KEY is not configured')
        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise CommandError(f'User with email {email} not found')
        
        subscription = user.get_subscription()
        if not subscription:
            raise CommandError(f'User {email} does not have a subscription')
        
        if not subscription.stripe_subscription_id:
            raise CommandError(f'Subscription for {email} does not have a stripe_subscription_id')
        
        self.stdout.write(f'Syncing subscription for {email}...')
        self.stdout.write(f'Stripe subscription ID: {subscription.stripe_subscription_id}')
        
        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            self.stdout.write(f'Retrieved subscription from Stripe')
            self.stdout.write(f'  Status: {stripe_subscription.status}')
            self.stdout.write(f'  Period start: {stripe_subscription.current_period_start}')
            self.stdout.write(f'  Period end: {stripe_subscription.current_period_end}')
            
            update_subscription_from_stripe(subscription, stripe_subscription)
            
            subscription.refresh_from_db()
            self.stdout.write(self.style.SUCCESS(f'Successfully synced subscription'))
            self.stdout.write(f'  Current period end: {subscription.current_period_end}')
            
        except stripe.error.StripeError as e:
            raise CommandError(f'Stripe error: {str(e)}')
        except Exception as e:
            raise CommandError(f'Error: {str(e)}')


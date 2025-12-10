from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.email
    
    def has_active_subscription(self):
        """Check if user has an active subscription"""
        if self.is_superuser or self.is_staff:
            return True  # Staff/superusers always have access
        try:
            subscription = self.subscription
            return subscription.is_active()
        except Subscription.DoesNotExist:
            return False
    
    def get_subscription(self):
        """Get the user's subscription or None"""
        try:
            return self.subscription
        except Subscription.DoesNotExist:
            return None


class Subscription(models.Model):
    """User subscription model for managing paid subscriptions"""
    
    STATUS_ACTIVE = "active"
    STATUS_CANCELED = "canceled"
    STATUS_PAST_DUE = "past_due"
    STATUS_UNPAID = "unpaid"
    STATUS_TRIALING = "trialing"
    STATUS_INCOMPLETE = "incomplete"
    STATUS_INCOMPLETE_EXPIRED = "incomplete_expired"
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_PAST_DUE, "Past Due"),
        (STATUS_UNPAID, "Unpaid"),
        (STATUS_TRIALING, "Trialing"),
        (STATUS_INCOMPLETE, "Incomplete"),
        (STATUS_INCOMPLETE_EXPIRED, "Incomplete Expired"),
    ]
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="subscription"
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_INCOMPLETE
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="Stripe subscription ID"
    )
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="Stripe customer ID"
    )
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start of current billing period"
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End of current billing period"
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="Whether subscription will cancel at period end"
    )
    trial_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End of trial period"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "subscriptions"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_status_display()}"
    
    def is_active(self):
        """Check if subscription is currently active"""
        if self.status in [self.STATUS_ACTIVE, self.STATUS_TRIALING]:
            # Check if period hasn't ended
            if self.current_period_end:
                return timezone.now() < self.current_period_end
            return True
        return False
    
    def is_in_trial(self):
        """Check if subscription is in trial period"""
        if self.status == self.STATUS_TRIALING and self.trial_end:
            return timezone.now() < self.trial_end
        return False
    
    def days_until_renewal(self):
        """Get days until subscription renews"""
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(0, delta.days)
        return None
    
    def clean(self):
        """Validate subscription data"""
        if self.current_period_end and self.current_period_start:
            if self.current_period_end <= self.current_period_start:
                raise ValidationError(
                    "Current period end must be after current period start"
                )

from django.conf import settings
from django.db import models


class Property(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    address = models.TextField(max_length=510)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "properties"

    def __str__(self):
        return self.name


class Unit(models.Model):
    STATUS_VACANT = "vacant"
    STATUS_OCCUPIED = "occupied"
    
    STATUS_CHOICES = [
        (STATUS_VACANT, "Vacant"),
        (STATUS_OCCUPIED, "Occupied"),
    ]
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    unit_number = models.CharField(max_length=255)
    size = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(max_length=510, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "units"


class Tenant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email_address = models.EmailField(max_length=255)
    phone_number = models.CharField(max_length=20)
    notes = models.TextField(max_length=510, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tenants"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Tenancies(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    notes = models.TextField(max_length=510, blank=True)
    monthly_rent_at_start = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tenancies"
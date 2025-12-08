from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from storage.models import Property, Tenancies, Tenant, Unit


class Command(BaseCommand):
    help = "Create example properties, units, tenants, and tenancies."

    def handle(self, *args, **options):
        with transaction.atomic():
            owner = self._get_or_create_owner()
            properties = self._create_properties(owner)
            units = self._create_units(properties)
            tenants = self._create_tenants()
            tenancies = self._create_tenancies(units, tenants)

        self.stdout.write(self.style.SUCCESS("Seed data created"))
        self.stdout.write(f"Properties: {len(properties)}")
        self.stdout.write(f"Units: {len(units)} (with {len(units) - len(tenancies)} vacant)")
        self.stdout.write(f"Tenants: {len(tenants)} (with {len(tenants) - len(tenancies)} unassigned)")
        self.stdout.write(f"Tenancies: {len(tenancies)}")

    def _get_or_create_owner(self):
        User = get_user_model()
        owner, created = User.objects.get_or_create(
            email="owner@example.com",
            defaults={
                "first_name": "Olivia",
                "last_name": "Owner",
                "is_staff": True,
                "is_active": True,
            },
        )
        if created:
            owner.set_password("changeme123")
            owner.save(update_fields=["password"])
            self.stdout.write("Created demo owner user: owner@example.com / changeme123")
        return owner

    def _create_properties(self, owner):
        property_data = [
            {"name": "Oak Grove Storage", "address": "101 Oak Grove Ln, Springfield"},
            {"name": "Riverside Lockers", "address": "22 River Rd, Fairview"},
            {"name": "Pine Ridge Units", "address": "303 Pine Ridge Ave, Hilltown"},
            {"name": "Downtown Depot", "address": "18 Main St, Midtown"},
            {"name": "Airport Annex", "address": "5 Runway Blvd, Lakeside"},
        ]
        properties = []
        for data in property_data:
            prop, _ = Property.objects.get_or_create(user=owner, name=data["name"], defaults={"address": data["address"]})
            properties.append(prop)
        return properties

    def _create_units(self, properties):
        unit_data = [
            {"property": properties[0], "unit_number": "A101", "size": "10x10", "status": "occupied", "monthly_rent": Decimal("120.00"), "notes": "Climate controlled"},
            {"property": properties[0], "unit_number": "A102", "size": "5x10", "status": "vacant", "monthly_rent": Decimal("80.00"), "notes": ""},
            {"property": properties[1], "unit_number": "B201", "size": "10x15", "status": "occupied", "monthly_rent": Decimal("150.00"), "notes": "Near elevator"},
            {"property": properties[2], "unit_number": "C5", "size": "5x5", "status": "vacant", "monthly_rent": Decimal("55.00"), "notes": "Corner unit"},
            {"property": properties[3], "unit_number": "D12", "size": "10x20", "status": "occupied", "monthly_rent": Decimal("210.00"), "notes": "Drive-up access"},
        ]
        units = []
        for data in unit_data:
            unit, _ = Unit.objects.get_or_create(
                property=data["property"],
                unit_number=data["unit_number"],
                defaults={
                    "size": data["size"],
                    "status": data["status"],
                    "monthly_rent": data["monthly_rent"],
                    "notes": data["notes"],
                },
            )
            units.append(unit)
        return units

    def _create_tenants(self):
        tenant_data = [
            {"first_name": "Hannah", "last_name": "Hart", "email_address": "hannah@example.com", "phone_number": "555-1001"},
            {"first_name": "Brian", "last_name": "Banks", "email_address": "brian@example.com", "phone_number": "555-1002"},
            {"first_name": "Sam", "last_name": "Singh", "email_address": "sam@example.com", "phone_number": "555-1003"},
            {"first_name": "Priya", "last_name": "Patel", "email_address": "priya@example.com", "phone_number": "555-1004"},
            {"first_name": "Miguel", "last_name": "Mora", "email_address": "miguel@example.com", "phone_number": "555-1005"},
        ]
        tenants = []
        for data in tenant_data:
            tenant, _ = Tenant.objects.get_or_create(
                email_address=data["email_address"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone_number": data["phone_number"],
                    "notes": "",
                },
            )
            tenants.append(tenant)
        return tenants

    def _create_tenancies(self, units, tenants):
        today = date.today()
        tenancy_data = [
            {"unit": units[0], "tenant": tenants[0], "start_date": today - timedelta(days=120), "end_date": today + timedelta(days=245), "monthly_rent_at_start": units[0].monthly_rent, "notes": "Paid through this month"},
            {"unit": units[2], "tenant": tenants[1], "start_date": today - timedelta(days=60), "end_date": today + timedelta(days=305), "monthly_rent_at_start": units[2].monthly_rent, "notes": "Auto-pay enabled"},
            {"unit": units[4], "tenant": tenants[2], "start_date": today - timedelta(days=15), "end_date": today + timedelta(days=350), "monthly_rent_at_start": units[4].monthly_rent, "notes": ""},
        ]
        tenancies = []
        for data in tenancy_data:
            tenancy, _ = Tenancies.objects.get_or_create(
                unit=data["unit"],
                tenant=data["tenant"],
                defaults={
                    "start_date": data["start_date"],
                    "end_date": data["end_date"],
                    "notes": data["notes"],
                    "monthly_rent_at_start": data["monthly_rent_at_start"],
                },
            )
            tenancies.append(tenancy)
        return tenancies


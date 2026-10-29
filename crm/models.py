from django.db import models


class Client(models.Model):
    class Sector(models.TextChoices):
        PUBLIC = "public", "Public agency / owner"
        CONTRACTOR = "contractor", "Contractor"
        DEVELOPER = "developer", "Developer"
        UTILITY = "utility", "Utility"
        CONSULTANT = "consultant", "Consultant (sub-consultant role)"
        OTHER = "other", "Other"

    name = models.CharField(max_length=200, unique=True)
    sector = models.CharField(max_length=20, choices=Sector.choices, default=Sector.PUBLIC)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Contact(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=200)
    title = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_primary", "name"]

    def __str__(self):
        return f"{self.name} ({self.client})"

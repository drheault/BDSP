from decimal import Decimal

from django.db import models

from proposals.models import Employee, FeeItem, Proposal


class ActualEntry(models.Model):
    """Hours actually booked against a (won) proposal — from timesheets or manual entry.
    Cost is stored in the base currency so it can be compared with the estimate."""

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        CSV = "csv", "CSV import"
        OFFICE_TIMESHEETS = "ots", "Office Timesheets"

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="actuals")
    item = models.ForeignKey(FeeItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="actuals")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="actuals")
    employee_name = models.CharField(max_length=120, blank=True, help_text="As it appeared in the source, if not matched.")
    date = models.DateField()
    hours = models.DecimalField(max_digits=7, decimal_places=2)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Base currency. Blank = hours × employee rate.")
    description = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    external_id = models.CharField(max_length=80, blank=True, help_text="Row id in the source system, for de-duplication.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name_plural = "actual entries"
        constraints = [
            models.UniqueConstraint(fields=["source", "external_id"], condition=~models.Q(external_id=""), name="uniq_actual_external_id"),
        ]

    def __str__(self):
        return f"{self.date} {self.employee or self.employee_name} {self.hours}h"

    def save(self, *args, **kwargs):
        if self.employee_id and not self.employee_name:
            self.employee_name = self.employee.name
        if self.cost is None:
            rate = self.employee.rate if self.employee_id else Decimal(0)
            self.cost = Decimal(self.hours or 0) * Decimal(rate or 0)
        super().save(*args, **kwargs)


class TimesheetConnector(models.Model):
    """Configuration for an external timesheet source (Office Timesheets today;
    the replacement tool later). Sync strategy: sync → adopt → replace."""

    name = models.CharField(max_length=100, default="Office Timesheets")
    kind = models.CharField(max_length=10, choices=ActualEntry.Source.choices, default=ActualEntry.Source.OFFICE_TIMESHEETS)
    base_url = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    is_enabled = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_result = models.TextField(blank=True)

    def __str__(self):
        return self.name

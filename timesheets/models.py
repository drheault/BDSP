from decimal import Decimal

from django.db import models

from proposals.models import Employee, FeeItem, Proposal


class ActualEntry(models.Model):
    """Hours actually booked against a project — from timesheets or manual entry.
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
    """Configuration for the Office Timesheets sync (and, later, its replacement).

    Two transports are supported because Office Timesheets is old software:
    * **folder** — OTS runs a scheduled export into a network folder; the sync
      picks up new files there (the practical option on a locked-down LAN).
    * **http** — an export URL that returns CSV (or JSON rows) with optional
      API key / basic auth, for when a reporting endpoint is available.
    """

    class Transport(models.TextChoices):
        FOLDER = "folder", "Watched export folder"
        HTTP = "http", "HTTP export endpoint"

    name = models.CharField(max_length=100, default="Office Timesheets")
    kind = models.CharField(max_length=10, choices=ActualEntry.Source.choices, default=ActualEntry.Source.OFFICE_TIMESHEETS)
    transport = models.CharField(max_length=10, choices=Transport.choices, default=Transport.FOLDER)
    export_folder = models.CharField(max_length=255, blank=True, help_text="Folder (local or mounted share) where OTS drops export files.")
    file_pattern = models.CharField(max_length=60, default="*.csv;*.xlsx", help_text="Semicolon-separated patterns, e.g. *.csv;*.xlsx")
    column_map = models.JSONField(
        default=dict, blank=True,
        help_text="Optional header overrides for the export, e.g. {\"date\": \"Work Date\", \"employee\": \"Resource Name\", \"project_number\": \"Job #\"}. Built-in aliases cover common names.",
    )
    base_url = models.URLField(blank=True, help_text="Export URL returning CSV or JSON.")
    api_key = models.CharField(max_length=255, blank=True)
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=255, blank=True)
    only_phases = models.CharField(max_length=10, default="CDE", help_text="Import rows only for projects in these phases (e.g. CDE).")
    lookback_days = models.PositiveIntegerField(default=45, help_text="Re-request this many days of history on each sync (duplicates are skipped).")
    is_enabled = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_result = models.TextField(blank=True)

    def __str__(self):
        return self.name

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SyncRun(models.Model):
    class Status(models.TextChoices):
        OK = "ok", "OK"
        PARTIAL = "partial", "Completed with errors"
        FAILED = "failed", "Failed"

    connector = models.ForeignKey(TimesheetConnector, on_delete=models.CASCADE, related_name="runs")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OK)
    trigger = models.CharField(max_length=20, default="manual")
    files = models.PositiveIntegerField(default=0)
    created = models.PositiveIntegerField(default=0)
    skipped = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    log = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.started_at:%Y-%m-%d %H:%M} {self.get_status_display()}"


class ProcessedFile(models.Model):
    """Files already imported from the watched folder (by name + size + mtime)."""

    connector = models.ForeignKey(TimesheetConnector, on_delete=models.CASCADE, related_name="processed_files")
    name = models.CharField(max_length=255)
    fingerprint = models.CharField(max_length=80)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("connector", "fingerprint")]

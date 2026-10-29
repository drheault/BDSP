"""Connector interface for external timesheet systems.

Phase 1 (sync): pull entries from Office Timesheets via CSV export / API into
ActualEntry. Phase 2 (adopt): staff book time here and the connector pushes
back. Phase 3 (replace): the connector is retired.

`OfficeTimesheetsConnector.fetch()` is a stub until the API details are known;
`import_csv` already handles the export file format.
"""

from django.utils import timezone

from .importer import import_csv
from .models import TimesheetConnector


class OfficeTimesheetsConnector:
    def __init__(self, config: TimesheetConnector):
        self.config = config

    def fetch(self):
        """Return a file-like CSV export. Replace with real API calls."""
        raise NotImplementedError("Office Timesheets API sync is not configured yet; use CSV import.")

    def sync(self):
        result = import_csv(self.fetch(), source="ots")
        self.config.last_synced_at = timezone.now()
        self.config.last_result = f"{result['created']} created, {result['skipped']} skipped, {len(result['errors'])} errors"
        self.config.save(update_fields=["last_synced_at", "last_result"])
        return result

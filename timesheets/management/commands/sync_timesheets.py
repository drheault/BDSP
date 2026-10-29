from django.core.management.base import BaseCommand

from timesheets.connector import sync_now
from timesheets.models import TimesheetConnector


class Command(BaseCommand):
    help = "Run the Office Timesheets sync (schedule this with cron / Task Scheduler)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even if the connector is disabled.")

    def handle(self, *args, **opts):
        cfg = TimesheetConnector.get_solo()
        if not cfg.is_enabled and not opts["force"]:
            self.stdout.write("Connector is disabled; nothing to do (use --force to run anyway).")
            return
        run = sync_now(trigger="scheduled")
        self.stdout.write(f"{run.get_status_display()}: {run.files} file(s), {run.created} created, {run.skipped} skipped, {run.errors} errors")
        if run.log:
            self.stdout.write(run.log)

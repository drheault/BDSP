from django.core.management.base import BaseCommand, CommandError

from proposals.models import Proposal
from timesheets.importer import import_csv


class Command(BaseCommand):
    help = "Import a timesheet CSV or Excel export into actual entries (matched by project number)."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--source", default="csv", choices=["csv", "ots"])
        parser.add_argument("--proposal", help="Proposal number to use when rows have no project number.")

    def handle(self, *args, **opts):
        default = None
        if opts["proposal"]:
            default = Proposal.objects.filter(number=opts["proposal"]).first()
            if not default:
                raise CommandError("Unknown proposal number")
        with open(opts["path"], "rb") as f:
            result = import_csv(f, source=opts["source"], default_proposal=default, filename=opts["path"])
        self.stdout.write(f"Created {result['created']}, skipped {result['skipped']} duplicates.")
        for e in result["errors"]:
            self.stderr.write(e)

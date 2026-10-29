from django.core.management.base import BaseCommand

from core.news import fetch_all


class Command(BaseCommand):
    help = "Fetch tunnelling industry news from the configured feeds (schedule hourly)."

    def handle(self, *args, **opts):
        res = fetch_all()
        self.stdout.write(f"{res['items']} new items; {res['ok']} feeds ok, {res['failed']} failed")

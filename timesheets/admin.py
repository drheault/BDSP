from django.contrib import admin

from .models import ActualEntry, TimesheetConnector


@admin.register(ActualEntry)
class ActualEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "proposal", "item", "employee", "hours", "cost", "source")
    list_filter = ("source", "proposal")
    date_hierarchy = "date"


@admin.register(TimesheetConnector)
class TimesheetConnectorAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "is_enabled", "last_synced_at")

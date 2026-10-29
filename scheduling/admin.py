from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("name", "proposal", "phase", "start", "end", "is_milestone", "percent_complete")
    list_filter = ("phase", "is_milestone")

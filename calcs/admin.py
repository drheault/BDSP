from django.contrib import admin

from .models import CalcRun, Tool


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "category", "author", "runs", "is_published")
    list_filter = ("kind", "category")


@admin.register(CalcRun)
class CalcRunAdmin(admin.ModelAdmin):
    list_display = ("title", "tool", "user", "proposal", "created_at")

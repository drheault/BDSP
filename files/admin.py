from django.contrib import admin

from .models import FileRoot, SyncLog


@admin.register(FileRoot)
class FileRootAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "path", "is_active")


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ("started_at", "root", "proposal", "files_seen", "records_created")

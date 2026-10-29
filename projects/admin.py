from django.contrib import admin

from .models import PastProject, ProjectImage


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 0


@admin.register(PastProject)
class PastProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "display_client", "year_completed", "is_featured")
    list_filter = ("kind", "is_featured")
    search_fields = ("name", "client_name", "location")
    inlines = [ProjectImageInline]

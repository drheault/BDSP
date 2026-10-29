from django.contrib import admin

from .models import CompanyProfile


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CompanyProfile.objects.exists()

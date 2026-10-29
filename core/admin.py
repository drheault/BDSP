from django.contrib import admin

from .models import CompanyProfile, Currency


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CompanyProfile.objects.exists()


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "rate_to_base", "is_active", "sort_order")
    list_editable = ("rate_to_base", "is_active", "sort_order")

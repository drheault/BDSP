from django.contrib import admin

from .models import AccessRole, CompanyProfile, CustomField, Currency, FieldRule, NewsItem, NewsSource, Office, Region, Theme


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CompanyProfile.objects.exists()


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "rate_to_base", "is_active", "sort_order")
    list_editable = ("rate_to_base", "is_active", "sort_order")


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "is_active")
    list_filter = ("kind",)


@admin.register(AccessRole)
class AccessRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "rank", "is_system")
    filter_horizontal = ("users",)


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ("name", "based_on", "is_active", "updated_at")


@admin.register(FieldRule)
class FieldRuleAdmin(admin.ModelAdmin):
    list_display = ("form_key", "field_name", "visible", "required", "label", "order")
    list_filter = ("form_key",)


@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    list_display = ("form_key", "key", "label", "type", "required", "is_active")
    list_filter = ("form_key",)


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "city", "country", "is_hq", "is_active")


admin.site.register([NewsSource, NewsItem])

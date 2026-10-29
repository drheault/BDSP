from django.contrib import admin

from .models import (
    Employee, FeeItem, FeeLine, Proposal, ProposalSection, ProposalTemplate, Service, StaffRole, TemplateSection,
)


class TemplateSectionInline(admin.TabularInline):
    model = TemplateSection
    extra = 0


@admin.register(ProposalTemplate)
class ProposalTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "service_type", "is_default")
    inlines = [TemplateSectionInline]


class ProposalSectionInline(admin.StackedInline):
    model = ProposalSection
    extra = 0


class FeeItemInline(admin.TabularInline):
    model = FeeItem
    extra = 0


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ("number", "project_number", "title", "client", "status", "service_type", "currency", "owner", "due_date")
    list_filter = ("status", "service_type", "owner", "currency")
    search_fields = ("number", "project_number", "title", "client__name")
    inlines = [ProposalSectionInline, FeeItemInline]


class FeeLineInline(admin.TabularInline):
    model = FeeLine
    extra = 0


@admin.register(FeeItem)
class FeeItemAdmin(admin.ModelAdmin):
    list_display = ("__str__", "proposal", "kind", "total")
    inlines = [FeeLineInline]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")


@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = ("title", "default_rate", "is_active", "sort_order")
    list_editable = ("default_rate", "is_active", "sort_order")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "initials", "role", "rate", "cost_rate", "is_active", "external_id")
    list_filter = ("role", "is_active")
    search_fields = ("name", "email", "external_id")

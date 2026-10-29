from django.contrib import admin

from .models import (
    Proposal,
    ProposalSection,
    ProposalStaffing,
    ProposalTemplate,
    Service,
    StaffRole,
    TemplateSection,
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


class ProposalStaffingInline(admin.TabularInline):
    model = ProposalStaffing
    extra = 0


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "client", "status", "service_type", "owner", "due_date")
    list_filter = ("status", "service_type", "owner")
    search_fields = ("number", "title", "client__name")
    inlines = [ProposalSectionInline, ProposalStaffingInline]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")


@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = ("title", "default_rate", "is_active", "sort_order")
    list_editable = ("default_rate", "is_active", "sort_order")

from django.contrib import admin

from .models import Client, Contact


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "sector")
    list_filter = ("sector",)
    search_fields = ("name",)
    inlines = [ContactInline]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "title", "email", "is_primary")
    search_fields = ("name", "email", "client__name")

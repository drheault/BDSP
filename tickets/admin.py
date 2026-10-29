from django.contrib import admin

from .models import Notification, Request, RequestEvent, RequestKind


@admin.register(RequestKind)
class RequestKindAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "handled_by", "is_active")


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "kind", "requester", "status", "priority", "assignee", "created_at")
    list_filter = ("status", "kind", "priority")


admin.site.register([RequestEvent, Notification])

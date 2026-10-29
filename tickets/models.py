"""Requests register and notifications.

Anyone can raise a request (access, a profile change they cannot make
themselves, a data correction, a feature idea, a bug). Each request kind is
handled by a group (an AccessRole); members are notified in-app and, if they
chose so, by email. Handlers triage, assign, resolve and leave a note; the
requester is notified of every change."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class RequestKind(models.Model):
    key = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    handled_by = models.ForeignKey("core.AccessRole", on_delete=models.SET_NULL, null=True, blank=True, related_name="handles_request_kinds", help_text="Group that receives and resolves these requests.")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Request(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "progress", "In progress"
        DONE = "done", "Done"
        DECLINED = "declined", "Declined"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    number = models.PositiveIntegerField(unique=True, editable=False)
    kind = models.ForeignKey(RequestKind, on_delete=models.PROTECT, related_name="requests")
    title = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="requests_made")
    on_behalf_of = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", help_text="For profile changes: whose profile.")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="requests_assigned")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.NORMAL)
    payload = models.JSONField(default=dict, blank=True, help_text="Structured data, e.g. the requested field values.")
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"R-{self.number} {self.title}"

    def save(self, *args, **kwargs):
        if not self.number:
            last = Request.objects.order_by("-number").values_list("number", flat=True).first()
            self.number = (last or 100) + 1
        if self.status in (self.Status.DONE, self.Status.DECLINED) and not self.resolved_at:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status in (self.Status.OPEN, self.Status.IN_PROGRESS)

    def handlers(self):
        if self.kind.handled_by_id:
            return self.kind.handled_by.users.filter(is_active=True)
        from django.contrib.auth import get_user_model

        return get_user_model().objects.filter(is_superuser=True, is_active=True)


class RequestEvent(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name="events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    text = models.CharField(max_length=255)
    url = models.CharField(max_length=300, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_read(self):
        return self.read_at is not None


def notify(users, text, url="", email_subject=None):
    """In-app notification for each user; email too when the user prefers it."""
    from django.core.mail import send_mail

    for u in users:
        Notification.objects.create(user=u, text=text, url=url)
        prof = getattr(u, "profile", None)
        if prof and getattr(prof, "notify_email", False) and u.email:
            try:
                send_mail(email_subject or text, f"{text}\n\n{settings.SITE_URL}{url}", settings.DEFAULT_FROM_EMAIL, [u.email], fail_silently=True)
            except Exception:
                pass

"""Engineering tools. Built-in calculators live in `calcs/engines.py` and are
registered here so they can be tagged, commented, liked and rated like anything
else. Users can also upload their own tools (spreadsheets, scripts, notes) which
go through the same rating and feedback loop."""

from django.conf import settings
from django.db import models

from tags.models import Taggable


class Tool(Taggable):
    class Kind(models.TextChoices):
        BUILTIN = "builtin", "Built-in calculator"
        UPLOAD = "upload", "Uploaded tool"
        LINK = "link", "External link"

    key = models.SlugField(max_length=60, unique=True, help_text="Registry key for built-in tools.")
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.BUILTIN)
    category = models.CharField(max_length=60, default="Tunnel design")
    summary = models.CharField(max_length=255)
    description = models.TextField(blank=True, help_text="Method, assumptions, references, design philosophy.")
    file = models.FileField(upload_to="tools/", blank=True, null=True)
    url = models.URLField(blank=True)
    version = models.CharField(max_length=20, blank=True, default="1.0")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="tools")
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    runs = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    @property
    def engine(self):
        from .engines import REGISTRY

        return REGISTRY.get(self.key)


class CalcRun(models.Model):
    """Saved calculation: inputs and outputs, attachable to a proposal."""

    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="saved_runs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    proposal = models.ForeignKey("proposals.Proposal", on_delete=models.SET_NULL, null=True, blank=True, related_name="calc_runs")
    title = models.CharField(max_length=160)
    inputs = models.JSONField(default=dict)
    outputs = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

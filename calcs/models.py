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
        SPEC = "spec", "No-code calculator (formulas)"
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
    spec = models.JSONField(default=dict, blank=True, help_text="For no-code tools: inputs, formulas, outputs, checks and chart (see Calculations → Build a tool).")

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    @property
    def engine(self):
        from .engines import REGISTRY

        if self.kind == "spec" and self.spec:
            from .spec import SpecEngine

            return SpecEngine(self)
        return REGISTRY.get(self.key)


class ProjectParams(models.Model):
    """Canonical parameters for a proposal/project, shared by every tool."""

    proposal = models.OneToOneField("proposals.Proposal", on_delete=models.CASCADE, related_name="params")
    values = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Parameters for {self.proposal}"


class ToolState(models.Model):
    """A user's last inputs for a tool (auto-saved as they type)."""

    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="states")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tool_states")
    proposal = models.ForeignKey("proposals.Proposal", on_delete=models.SET_NULL, null=True, blank=True)
    inputs = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tool", "user")]


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

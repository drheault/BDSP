from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models

from proposals.models import Proposal


class Task(models.Model):
    """A bar (or milestone) on a proposal's Gantt chart."""

    class Phase(models.TextChoices):
        PLANNING = "planning", "Planning / studies"
        PRELIM = "prelim", "Preliminary design"
        DETAILED = "detailed", "Detailed design"
        PROCUREMENT = "procurement", "Procurement / tender"
        CONSTRUCTION = "construction", "Construction support"
        CLOSEOUT = "closeout", "Close-out"
        OTHER = "other", "Other"

    PHASE_COLORS = {
        "planning": "#6b7f99",
        "prelim": "#2f80ad",
        "detailed": "#0f3d5e",
        "procurement": "#8e6cb8",
        "construction": "#e07a1f",
        "closeout": "#3a9d6a",
        "other": "#9aa5b1",
    }

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="tasks")
    name = models.CharField(max_length=200)
    phase = models.CharField(max_length=20, choices=Phase.choices, default=Phase.DETAILED)
    start = models.DateField()
    end = models.DateField()
    is_milestone = models.BooleanField(default=False)
    percent_complete = models.PositiveSmallIntegerField(default=0)
    predecessor = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="successors"
    )
    order = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["order", "start", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.is_milestone:
            self.end = self.start
        if self.start and self.end and self.end < self.start:
            raise ValidationError({"end": "End date must be on or after the start date."})
        if self.predecessor_id and self.predecessor_id == self.pk:
            raise ValidationError({"predecessor": "A task cannot depend on itself."})

    @property
    def duration_days(self):
        return (self.end - self.start).days + 1

    @property
    def color(self):
        return self.PHASE_COLORS.get(self.phase, "#9aa5b1")

    def shift(self, days: int):
        delta = timedelta(days=days)
        self.start += delta
        self.end += delta
        self.save(update_fields=["start", "end"])

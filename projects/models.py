from django.db import models

from crm.models import Client


class PastProject(models.Model):
    """A portfolio entry (project sheet) used to showcase experience in proposals."""

    class Kind(models.TextChoices):
        TUNNEL = "tunnel", "Tunnel"
        CAVERN = "cavern", "Cavern / large underground structure"
        SHAFT = "shaft", "Shaft"
        STATION = "station", "Underground station"
        CUT_COVER = "cut_cover", "Cut & cover / deep excavation"
        MICRO = "micro", "Microtunnel / trenchless"
        OTHER = "other", "Other"

    name = models.CharField(max_length=250)
    client = models.ForeignKey(
        Client, on_delete=models.SET_NULL, null=True, blank=True, related_name="past_projects"
    )
    client_name = models.CharField(
        max_length=200, blank=True, help_text="Free text if the client is not in the CRM."
    )
    location = models.CharField(max_length=200, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.TUNNEL)
    role = models.CharField(
        max_length=200, blank=True, help_text="e.g. Lead designer, Engineer of record, CM support"
    )
    year_completed = models.PositiveIntegerField(null=True, blank=True)
    construction_value = models.DecimalField(
        max_digits=14, decimal_places=0, null=True, blank=True, help_text="USD"
    )
    key_dimensions = models.CharField(
        max_length=250, blank=True, help_text="e.g. 7.2 m ID, 3.4 km, 45 m deep"
    )
    description = models.TextField(blank=True)
    highlights = models.TextField(blank=True, help_text="One highlight per line.")
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_featured", "-year_completed", "name"]

    def __str__(self):
        return self.name

    @property
    def display_client(self):
        return self.client.name if self.client else self.client_name

    @property
    def cover(self):
        return self.images.first()

    @property
    def highlight_list(self):
        return [h.strip("•- ").strip() for h in self.highlights.splitlines() if h.strip()]


class ProjectImage(models.Model):
    project = models.ForeignKey(PastProject, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="projects/")
    caption = models.CharField(max_length=250, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.caption or f"Image {self.pk}"

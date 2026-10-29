from django.db import models

from crm.models import Client
from tags.models import Taggable


class PastProject(Taggable):
    """A portfolio entry (project sheet) used to showcase experience in proposals.
    Images and documents may live on the file server; `source_path` records where."""

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
    services = models.ManyToManyField("proposals.Service", blank=True, related_name="past_projects", help_text="Services we provided.")
    fee_value = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True, help_text="Our fee (base currency), optional.")
    duration_months = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True, help_text="What the project is and what was built.")
    challenges = models.TextField(blank=True, help_text="Ground, logistics, schedule or technical challenges.")
    contribution = models.TextField(blank=True, help_text="Our unique contribution.")
    value_added = models.TextField(blank=True, help_text="Value added: savings, risk reduction, schedule gained.")
    highlights = models.TextField(blank=True, help_text="One highlight per line.")
    source_path = models.CharField(max_length=500, blank=True, help_text="File-server folder holding source material (photos, reports).")
    reference_contact = models.CharField(max_length=200, blank=True, help_text="Client reference (name, title) — optional, shown on the sheet if filled.")
    extra = models.JSONField(default=dict, blank=True)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True, help_text="Unpublished sheets are drafts and never attached to proposals.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    @property
    def searchable_text(self):
        return " ".join([self.name, self.location, self.description, self.challenges, self.contribution, self.value_added, self.highlights, self.get_kind_display(), self.display_client or ""])

    def relevance_for(self, proposal):
        """0–100 score of how relevant this sheet is to a proposal: shared tags (weighted by category),
        shared services, same structure kind keywords, same client / sector, and text overlap."""
        from proposals.suggestions import _tokens

        score, reasons = 0.0, []
        my_tags = {t.pk: t for t in self.tags}
        p_tags = {t.pk: t for t in proposal.tags}
        shared = [my_tags[k] for k in my_tags.keys() & p_tags.keys()]
        if shared:
            w = sum(float(t.category.weight) for t in shared)
            score += min(40, 12 * w)
            reasons.append("tags: " + ", ".join(t.name for t in shared[:4]))
        svc = set(self.services.values_list("pk", flat=True)) & set(proposal.services.values_list("pk", flat=True))
        if svc:
            score += min(25, 8 * len(svc))
            reasons.append(f"{len(svc)} shared service{'s' if len(svc) > 1 else ''}")
        if proposal.client_id and self.client_id == proposal.client_id:
            score += 15
            reasons.append("same client")
        elif proposal.client_id and self.client_id and self.client.sector == proposal.client.sector:
            score += 6
            reasons.append("same sector")
        kind_words = {"tunnel": "tunnel", "cavern": "cavern", "shaft": "shaft", "station": "station", "cut_cover": "cut-and-cover", "micro": "microtunnel"}
        ptext = f"{proposal.title} {proposal.summary} {proposal.location}".lower()
        if kind_words.get(self.kind, "") and kind_words[self.kind] in ptext:
            score += 10
            reasons.append(f"{kind_words[self.kind]} project")
        overlap = _tokens(ptext) & _tokens(self.searchable_text)
        if overlap:
            score += min(15, 2.5 * len(overlap))
            reasons.append("keywords: " + ", ".join(sorted(overlap)[:4]))
        if self.is_featured:
            score += 3
        return min(100, round(score)), reasons


class ProjectImage(models.Model):
    project = models.ForeignKey(PastProject, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="projects/")
    caption = models.CharField(max_length=250, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.caption or f"Image {self.pk}"

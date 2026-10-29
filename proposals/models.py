import re
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone

from crm.models import Client, Contact


class ServiceType(models.TextChoices):
    DESIGN = "design", "Design services"
    CONSTRUCTION = "construction", "Construction support"
    BOTH = "both", "Design + construction support"
    OTHER = "other", "Other / studies"


class Service(models.Model):
    """Catalogue of services the firm offers (used as scope checklists)."""

    name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=20, choices=ServiceType.choices, default=ServiceType.DESIGN
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "sort_order", "name"]

    def __str__(self):
        return self.name


class StaffRole(models.Model):
    """Billing roles with default hourly rates used for fee estimates."""

    title = models.CharField(max_length=120, unique=True)
    default_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class ProposalTemplate(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    service_type = models.CharField(
        max_length=20, choices=ServiceType.choices, default=ServiceType.DESIGN
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            ProposalTemplate.objects.exclude(pk=self.pk).update(is_default=False)


class TemplateSection(models.Model):
    template = models.ForeignKey(
        ProposalTemplate, on_delete=models.CASCADE, related_name="sections"
    )
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, help_text="Supports placeholders like {{client_name}}.")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class Proposal(models.Model):
    class Status(models.TextChoices):
        LEAD = "lead", "Lead"
        DRAFTING = "drafting", "Drafting"
        REVIEW = "review", "In review"
        SUBMITTED = "submitted", "Submitted"
        WON = "won", "Won"
        LOST = "lost", "Lost"
        NO_BID = "no_bid", "No bid"

    OPEN_STATUSES = ("lead", "drafting", "review", "submitted")

    number = models.CharField(max_length=20, unique=True, blank=True)
    title = models.CharField(max_length=250)
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, related_name="proposals", null=True, blank=True
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, related_name="proposals", null=True, blank=True
    )
    service_type = models.CharField(
        max_length=20, choices=ServiceType.choices, default=ServiceType.DESIGN
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.LEAD)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposals",
        help_text="Senior associate leading this pursuit.",
    )
    template = models.ForeignKey(
        ProposalTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    services = models.ManyToManyField(Service, blank=True, related_name="proposals")
    location = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True, help_text="One-paragraph project summary.")
    due_date = models.DateField(null=True, blank=True, help_text="Submission deadline.")
    probability = models.PositiveSmallIntegerField(
        default=50, help_text="Chance of winning, 0–100 %."
    )
    expenses = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, help_text="Direct expenses / ODCs."
    )
    markup_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="Markup on expenses, %."
    )
    manual_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override the computed fee when the estimate is not built up yet.",
    )
    notes = models.TextField(blank=True, help_text="Internal notes (not printed).")
    submitted_at = models.DateField(null=True, blank=True)
    decided_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # ----- numbering ----------------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.next_number()
        if self.status == self.Status.SUBMITTED and not self.submitted_at:
            self.submitted_at = timezone.localdate()
        if self.status in (self.Status.WON, self.Status.LOST) and not self.decided_at:
            self.decided_at = timezone.localdate()
        super().save(*args, **kwargs)

    @classmethod
    def next_number(cls):
        from core.models import CompanyProfile

        prefix = CompanyProfile.get_solo().proposal_prefix or "P"
        year = timezone.localdate().year
        stem = f"{prefix}-{year}-"
        last = (
            cls.objects.filter(number__startswith=stem)
            .order_by("-number")
            .values_list("number", flat=True)
            .first()
        )
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{stem}{seq:03d}"

    # ----- fees ---------------------------------------------------------------
    @property
    def labour_total(self) -> Decimal:
        total = self.staffing.aggregate(t=Sum(F("hours") * F("rate")))["t"]
        return Decimal(total or 0)

    @property
    def total_hours(self) -> Decimal:
        return Decimal(self.staffing.aggregate(t=Sum("hours"))["t"] or 0)

    @property
    def expenses_total(self) -> Decimal:
        expenses = Decimal(self.expenses or 0)
        markup = Decimal(self.markup_percent or 0)
        return expenses * (1 + markup / 100)

    @property
    def fee_total(self) -> Decimal:
        if self.manual_value is not None:
            return Decimal(self.manual_value)
        return self.labour_total + self.expenses_total

    @property
    def weighted_value(self) -> Decimal:
        return self.fee_total * Decimal(self.probability) / 100

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def days_to_due(self):
        if not self.due_date:
            return None
        return (self.due_date - timezone.localdate()).days

    # ----- template placeholders ---------------------------------------------
    def placeholder_context(self):
        from core.models import CompanyProfile

        company = CompanyProfile.get_solo()
        return {
            "client_name": self.client.name if self.client else "[Client]",
            "contact_name": self.contact.name if self.contact else "[Contact]",
            "project_name": self.title,
            "project_location": self.location or "[Location]",
            "proposal_number": self.number,
            "company_name": company.name,
            "date": timezone.localdate().strftime("%B %d, %Y"),
            "owner_name": (
                self.owner.get_full_name() or self.owner.get_username()
            )
            if self.owner
            else "[Lead]",
            "fee_total": f"${self.fee_total:,.0f}",
        }

    def render_text(self, text: str) -> str:
        ctx = self.placeholder_context()
        return re.sub(
            r"\{\{\s*(\w+)\s*\}\}",
            lambda m: str(ctx.get(m.group(1), m.group(0))),
            text or "",
        )

    @property
    def rendered_summary(self) -> str:
        return self.render_text(self.summary)

    def apply_template(self, template: ProposalTemplate):
        """Copy a template's sections into this proposal (appending after existing ones)."""
        start = self.sections.count()
        for i, s in enumerate(template.sections.all()):
            ProposalSection.objects.create(
                proposal=self, order=start + i, title=s.title, body=s.body
            )
        self.template = template
        self.save(update_fields=["template"])


class ProposalSection(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="sections")
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    @property
    def rendered_body(self):
        return self.proposal.render_text(self.body)


class ProposalStaffing(models.Model):
    """One line of the fee build-up: a role, hours and rate."""

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="staffing")
    role = models.ForeignKey(StaffRole, on_delete=models.PROTECT)
    task = models.CharField(max_length=200, blank=True, help_text="Task / phase this effort covers.")
    hours = models.DecimalField(max_digits=8, decimal_places=1, default=0)
    rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.role} × {self.hours}h"

    @property
    def amount(self) -> Decimal:
        return (self.hours or 0) * (self.rate or 0)

    def save(self, *args, **kwargs):
        if not self.rate and self.role_id:
            self.rate = self.role.default_rate
        super().save(*args, **kwargs)

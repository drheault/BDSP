import re
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models


class Currency(models.Model):
    """Currencies proposals can be priced in. `rate_to_base` converts one unit of this
    currency into the company's default (base) currency, so aggregates on the
    dashboard can be shown in one currency."""

    code = models.CharField(max_length=5, unique=True, help_text="ISO code, e.g. CAD")
    name = models.CharField(max_length=60)
    symbol = models.CharField(max_length=6, default="$")
    rate_to_base = models.DecimalField(
        max_digits=12, decimal_places=6, default=1,
        help_text="1 unit of this currency = this many units of the base currency.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "code"]
        verbose_name_plural = "currencies"

    def __str__(self):
        return self.code

    def format(self, amount, decimals=0) -> str:
        amount = Decimal(amount or 0)
        sign = "-" if amount < 0 else ""
        q = Decimal(1).scaleb(-decimals)
        body = f"{abs(amount).quantize(q, rounding=ROUND_HALF_UP):,}"
        return f"{sign}{self.symbol}{body}"

    def to_base(self, amount) -> Decimal:
        return Decimal(amount or 0) * Decimal(self.rate_to_base)

    def from_base(self, amount) -> Decimal:
        rate = Decimal(self.rate_to_base) or Decimal(1)
        return Decimal(amount or 0) / rate


class CompanyProfile(models.Model):
    """Singleton holding the firm's identity: name, logo, contact details, colours."""

    name = models.CharField(max_length=200, default="Dr. Sauer & Partners")
    tagline = models.CharField(
        max_length=200, blank=True, default="Tunnels & Underground Structures"
    )
    logo = models.ImageField(upload_to="branding/", blank=True, null=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, default="#0f3d5e")
    accent_color = models.CharField(max_length=7, default="#e07a1f")
    proposal_footer = models.CharField(
        max_length=255,
        blank=True,
        default="Confidential — prepared for the exclusive use of the addressee.",
    )
    proposal_prefix = models.CharField(max_length=10, default="P")
    default_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        help_text="Base currency for rate cards, dashboard totals and new proposals.",
    )
    project_number_pattern = models.CharField(
        max_length=200, default=r"^\d{2}-\d{3}$",
        help_text="Regular expression every project number must match (your file-server / HCL Notes classification).",
    )
    project_number_example = models.CharField(max_length=50, default="26-042")
    project_number_help = models.CharField(
        max_length=255, blank=True,
        default="Two-digit year, dash, three-digit sequence — must match the file server and Notes database.",
    )
    require_project_number_when_won = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Company profile"

    def __str__(self):
        return self.name

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @property
    def base_currency(self):
        if self.default_currency_id:
            return self.default_currency
        cur = Currency.objects.filter(is_active=True).first()
        if cur is None:
            cur = Currency.objects.create(code="CAD", name="Canadian dollar", symbol="CA$", rate_to_base=1)
        return cur

    def validate_project_number(self, value: str):
        if not value:
            return
        try:
            ok = re.match(self.project_number_pattern, value) is not None
        except re.error:
            ok = True
        if not ok:
            raise ValidationError(
                f"Project number must match the company format (e.g. {self.project_number_example}). "
                f"{self.project_number_help}"
            )

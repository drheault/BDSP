import re
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.conf import settings
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
    primary_color = models.CharField(max_length=7, default="#1b3a5c")
    accent_color = models.CharField(max_length=7, default="#e3a725")
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
    # ---- project numbering: B-ON601 → 601C → 601D → 601E ----------------------
    number_digits = models.PositiveSmallIntegerField(
        default=3, help_text="Digits in the sequence (3 today, switch to 4 when the 3-digit range runs out)."
    )
    sequence_start = models.PositiveIntegerField(default=601, help_text="First sequence number the app will assign.")
    bd_number_format = models.CharField(
        max_length=60, default="B-{region}{seq}",
        help_text="Business-development (phase B) format. Placeholders: {region}, {seq}, {phase}.",
    )
    phase_number_format = models.CharField(
        max_length=60, default="{seq}{phase}",
        help_text="Format once the project moves to C / D / E. Placeholders: {region}, {seq}, {phase}.",
    )
    require_project_number_when_won = models.BooleanField(default=True)
    # ---- integrations (placeholders until credentials are available) -----------
    smb_path_template = models.CharField(
        max_length=255, blank=True, default=r"\\fileserver\Projects\{phase_name}\{project_number}",
        help_text="UNC path of a project's folder on the file server. Placeholders: {project_number}, {phase}, {phase_name}, {region}, {seq}.",
    )
    proposal_terms = models.TextField(
        blank=True,
        default=(
            "Validity: this proposal is valid for 60 days from the date of issue.\n"
            "Basis: fees are based on the scope, assumptions and schedule described; changes are handled by written change order.\n"
            "Invoicing: monthly, net 30 days. Expenses at cost plus the markup stated.\n"
            "Liability: limited to the fee under this agreement; professional indemnity insurance is maintained as stated in our standard terms.\n"
            "Confidentiality: this proposal is prepared for the exclusive use of the addressee."
        ),
        help_text="Terms, validity and notes. Printed as the 'Terms & validity' attachment; a one-line validity note also appears in the main body.",
    )
    capabilities_statement = models.TextField(
        blank=True,
        default="Dr. Sauer & Partners is an independent tunnelling consultancy providing the full range of design and construction management services for tunnels, shafts and caverns, with offices in Salzburg, London, Washington D.C., Toronto and Tel Aviv.",
        help_text="Printed on the 'Capabilities' attachment above the service catalogue.",
    )
    signature_name = models.CharField(max_length=120, blank=True, help_text="Default signatory (overridden by the proposal owner if set).")
    signature_title = models.CharField(max_length=120, blank=True, default="Partner")
    notes_server = models.CharField(max_length=200, blank=True, help_text="HCL Notes / Domino server (placeholder).")
    notes_database = models.CharField(max_length=200, blank=True, help_text="Notes database path, e.g. projects.nsf (placeholder).")

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

    def format_number(self, region: str, seq: int, phase: str) -> str:
        fmt = self.bd_number_format if phase == "B" else self.phase_number_format
        return fmt.format(region=region or "", seq=f"{seq:0{self.number_digits}d}", phase=phase)

    @property
    def number_example(self) -> str:
        return f"{self.format_number('ON', self.sequence_start, 'B')} → {self.format_number('ON', self.sequence_start, 'C')}"


class Region(models.Model):
    """Two-letter province/state or three-letter country code used in project numbers."""

    class Kind(models.TextChoices):
        PROVINCE = "province", "Province / territory"
        STATE = "state", "State"
        COUNTRY = "country", "Country"
        OTHER = "other", "Other"

    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PROVINCE)
    country = models.CharField(max_length=60, default="canada", help_text="Country folder used in file-server paths, e.g. canada, usa, uk.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "code"]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        self.code = (self.code or "").upper().strip()
        if not re.fullmatch(r"[A-Z]{2,3}", self.code):
            raise ValidationError({"code": "Use 2 letters (province/state) or 3 letters (country)."})

    def save(self, *args, **kwargs):
        self.code = (self.code or "").upper().strip()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Access roles: Partners, Associates, Engineers, HR, IT, Admins… with capabilities
# ---------------------------------------------------------------------------
CAPABILITIES = [
    ("view_proposals", "View proposals, schedules and clients"),
    ("edit_proposals", "Create and edit proposals, fees and schedules"),
    ("approve_won", "Mark proposals won / lost and assign project numbers"),
    ("change_phase", "Move projects between phases (B → C → D → E)"),
    ("view_costs", "See internal cost rates and margins"),
    ("edit_rates", "Edit employees, billing rates and the rate card"),
    ("view_actuals", "View timesheet actuals and estimate-vs-actual"),
    ("edit_actuals", "Add / import time entries"),
    ("view_metrics", "View BD metrics"),
    ("manage_projects_library", "Edit project sheets and templates"),
    ("manage_settings", "Company settings, currencies, numbering"),
    ("manage_forms", "Form builder: choose which inputs each form shows, add custom fields"),
    ("manage_integrations", "Timesheet / Notes / file-server connectors"),
    ("manage_users", "Create users and assign roles"),
]
CAPABILITY_KEYS = [c[0] for c in CAPABILITIES]


class AccessRole(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)
    rank = models.PositiveSmallIntegerField(default=50, help_text="Lower = higher in the hierarchy (Partners 10, Admins 90).")
    capabilities = models.JSONField(default=list, blank=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="access_roles")
    is_system = models.BooleanField(default=False, help_text="Seeded role; can be edited but not deleted.")

    class Meta:
        ordering = ["rank", "name"]

    def __str__(self):
        return self.name

    def has(self, cap: str) -> bool:
        return cap in (self.capabilities or [])

    @property
    def capability_labels(self):
        labels = dict(CAPABILITIES)
        return [labels[c] for c in self.capabilities if c in labels]


def user_capabilities(user) -> set:
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(CAPABILITY_KEYS)
    caps = set()
    for role in user.access_roles.all():
        caps.update(role.capabilities or [])
    return caps


# ---------------------------------------------------------------------------
# Appearance themes
# ---------------------------------------------------------------------------
class Theme(models.Model):
    """A saved look: CSS variables + optional custom CSS. One theme is active."""

    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=200, blank=True)
    based_on = models.CharField(max_length=30, blank=True, help_text="Preset key this theme was copied from.")
    variables = models.JSONField(default=dict, blank=True, help_text="Light-mode values.")
    dark_variables = models.JSONField(default=dict, blank=True, help_text="Dark-mode values (applied when the page is in dark mode).")
    default_mode = models.CharField(max_length=5, choices=[("dark", "Dark"), ("light", "Light")], default="dark")
    custom_css = models.TextField(blank=True, help_text="Extra CSS appended after the theme variables.")
    is_active = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_active:
            Theme.objects.exclude(pk=self.pk).update(is_active=False)

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True).first()

    def css(self) -> str:
        from .themes import DEFAULT_PRESET, PRESETS

        base = dict(PRESETS[DEFAULT_PRESET]["vars"])
        base.update(self.variables or {})
        light = ";".join(f"--{k}:{v}" for k, v in base.items() if v)
        dark = dict(base)
        dark.update(PRESETS.get(self.based_on, PRESETS[DEFAULT_PRESET]).get("dark", {}))
        dark.update(self.dark_variables or {})
        darkd = ";".join(f"--{k}:{v}" for k, v in dark.items() if v)
        return f":root{{{light}}}\n:root[data-mode=dark]{{{darkd};color-scheme:dark}}\n{self.custom_css or ''}"

    def export(self) -> dict:
        return {"name": self.name, "description": self.description, "based_on": self.based_on, "variables": self.variables, "dark_variables": self.dark_variables, "default_mode": self.default_mode, "custom_css": self.custom_css}


# ---------------------------------------------------------------------------
# Form builder: which inputs each form shows, plus custom fields
# ---------------------------------------------------------------------------
FORM_KEYS = [
    ("proposal", "Proposal (overview)"), ("proposal_create", "New proposal"), ("client", "Client"), ("contact", "Contact"),
    ("employee", "Employee"), ("project_sheet", "Project sheet"), ("task", "Schedule task"), ("fee_item", "Fee work item"),
]


class FieldRule(models.Model):
    """Per-form, per-field overrides: hide, make required, relabel, reorder."""

    form_key = models.CharField(max_length=40, choices=FORM_KEYS)
    field_name = models.CharField(max_length=60)
    label = models.CharField(max_length=120, blank=True)
    help_text = models.CharField(max_length=255, blank=True)
    visible = models.BooleanField(default=True)
    required = models.BooleanField(null=True, blank=True, help_text="Blank = keep the form's default.")
    order = models.PositiveIntegerField(default=100)

    class Meta:
        unique_together = [("form_key", "field_name")]
        ordering = ["form_key", "order", "field_name"]

    def __str__(self):
        return f"{self.form_key}.{self.field_name}"


class CustomField(models.Model):
    """Extra inputs added to a form by an admin; values are stored in the object's `extra` JSON."""

    class Type(models.TextChoices):
        TEXT = "text", "Short text"
        LONG = "long", "Long text"
        NUMBER = "number", "Number"
        DATE = "date", "Date"
        BOOL = "bool", "Yes / no"
        CHOICE = "choice", "Choice"

    form_key = models.CharField(max_length=40, choices=FORM_KEYS)
    key = models.SlugField(max_length=40)
    label = models.CharField(max_length=120)
    type = models.CharField(max_length=8, choices=Type.choices, default=Type.TEXT)
    choices = models.CharField(max_length=500, blank=True, help_text="For Choice: comma-separated options.")
    help_text = models.CharField(max_length=255, blank=True)
    required = models.BooleanField(default=False)
    show_in_export = models.BooleanField(default=False, help_text="Print on proposal / project sheet documents.")
    order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("form_key", "key")]
        ordering = ["form_key", "order", "label"]

    def __str__(self):
        return f"{self.form_key}.{self.key}"

    @property
    def choice_list(self):
        return [c.strip() for c in self.choices.split(",") if c.strip()]


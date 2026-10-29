import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from core.models import CompanyProfile, Currency, Region
from crm.models import Client, Contact
from tags.models import Taggable

ZERO = Decimal("0")


class ServiceType(models.TextChoices):
    DESIGN = "design", "Design services"
    CONSTRUCTION = "construction", "Construction support"
    BOTH = "both", "Design + construction support"
    OTHER = "other", "Other / studies"


class Service(Taggable):
    """Catalogue of services the firm offers (used as scope checklists)."""

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=ServiceType.choices, default=ServiceType.DESIGN)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "sort_order", "name"]

    def __str__(self):
        return self.name


class StaffRole(models.Model):
    """Billing roles with default hourly rates (in the base currency)."""

    title = models.CharField(max_length=120, unique=True)
    default_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class Employee(models.Model):
    """A named person with their own billing rate (base currency). Fee lines and
    timesheet actuals can be attributed to an employee for granular estimates."""

    name = models.CharField(max_length=120)
    initials = models.CharField(max_length=6, blank=True)
    role = models.ForeignKey(StaffRole, on_delete=models.PROTECT, related_name="employees")
    rate = models.DecimalField(max_digits=8, decimal_places=2, help_text="Billing rate per hour, base currency.")
    cost_rate = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Internal cost per hour (optional, for margin analysis).",
    )
    email = models.EmailField(blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="employee")
    external_id = models.CharField(max_length=60, blank=True, help_text="ID in Office Timesheets / HR system, for sync.")
    extra = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.initials:
            self.initials = "".join(p[0] for p in self.name.split() if p)[:4].upper()
        super().save(*args, **kwargs)


class ProposalTemplate(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    service_type = models.CharField(max_length=20, choices=ServiceType.choices, default=ServiceType.DESIGN)
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
    template = models.ForeignKey(ProposalTemplate, on_delete=models.CASCADE, related_name="sections")
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, help_text="Supports placeholders like {{client_name}}.")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class Proposal(Taggable):
    class Status(models.TextChoices):
        LEAD = "lead", "Lead"
        DRAFTING = "drafting", "Drafting"
        REVIEW = "review", "In review"
        SUBMITTED = "submitted", "Submitted"
        SHORTLISTED = "shortlisted", "Shortlisted / accepted"
        WON = "won", "Won"
        LOST = "lost", "Lost"
        NO_BID = "no_bid", "No bid"

    class ProjectStatus(models.TextChoices):
        NONE = "", "—"
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On hold"
        COMPLETE = "complete", "Complete"

    class Phase(models.TextChoices):
        B = "B", "B — Business development"
        C = "C", "C — Consulting"
        D = "D", "D — Design development"
        E = "E", "E — Execution / construction"

    PHASE_NAMES = {"B": "Business Development", "C": "Consulting", "D": "Design Development", "E": "Execution"}
    OPEN_STATUSES = ("lead", "drafting", "review", "submitted", "shortlisted")

    number = models.CharField(max_length=20, unique=True, blank=True)
    # ---- official project number = region + sequence + phase ----------------
    region = models.ForeignKey(Region, on_delete=models.PROTECT, null=True, blank=True, related_name="proposals", help_text="Province / state (2 letters) or country (3 letters).")
    sequence = models.PositiveIntegerField(null=True, blank=True, help_text="Sequence number; assigned by the app, kept through all phases.")
    phase = models.CharField(max_length=1, choices=Phase.choices, default=Phase.B)
    project_number = models.CharField(
        max_length=30, blank=True, null=True, unique=True, editable=False,
        help_text="Derived from region, sequence and phase (e.g. B-ON601, then 601C).",
    )
    project_status = models.CharField(max_length=12, choices=ProjectStatus.choices, blank=True, default="")
    title = models.CharField(max_length=250)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="proposals", null=True, blank=True)
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, related_name="proposals", null=True, blank=True)
    service_type = models.CharField(max_length=20, choices=ServiceType.choices, default=ServiceType.DESIGN)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.LEAD)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="proposals",
        help_text="Senior associate leading this pursuit.",
    )
    template = models.ForeignKey(ProposalTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    services = models.ManyToManyField(Service, blank=True, related_name="proposals")
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True, related_name="proposals")
    location = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True, help_text="One-paragraph project summary.")
    due_date = models.DateField(null=True, blank=True, help_text="Submission deadline.")
    probability = models.PositiveSmallIntegerField(default=50, help_text="Chance of winning, 0–100 %.")
    contingency_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Contingency added on top of labour + expenses, %.")
    manual_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Override the computed fee when the estimate is not built up yet.",
    )
    closing_words = models.TextField(blank=True, default="We appreciate the opportunity to submit this proposal and would welcome the chance to discuss our approach with you.", help_text="Short closing paragraph before the signature.")
    signatory = models.ForeignKey("Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="signed_proposals", help_text="Who signs. Defaults to the owner's employee record or the company default.")
    include_fee_breakdown = models.BooleanField(default=True, help_text="Attach the detailed fee breakdown.")
    include_schedule = models.BooleanField(default=True, help_text="Attach the schedule (if tasks exist).")
    include_terms = models.BooleanField(default=True, help_text="Attach terms & validity.")
    include_capabilities = models.BooleanField(default=True, help_text="Attach the capabilities statement and service list.")
    extra = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, help_text="Internal notes (not printed).")
    submitted_at = models.DateField(null=True, blank=True)
    decided_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # ----- numbering / validation --------------------------------------------
    def compute_project_number(self):
        if self.sequence is None:
            return None
        company = CompanyProfile.get_solo()
        return company.format_number(self.region.code if self.region_id else "", self.sequence, self.phase)

    def clean(self):
        company = CompanyProfile.get_solo()
        if self.sequence is not None and not self.region_id:
            raise ValidationError({"region": "Pick a region before assigning a project number."})
        if self.status == self.Status.WON and company.require_project_number_when_won and self.sequence is None:
            raise ValidationError("Assign a project number (region + sequence) before marking the proposal won.")
        computed = self.compute_project_number()
        if computed:
            clash = Proposal.objects.filter(project_number=computed).exclude(pk=self.pk).first()
            if clash:
                raise ValidationError(f"Project number {computed} is already used by {clash.number}.")

    @classmethod
    def next_sequence(cls) -> int:
        company = CompanyProfile.get_solo()
        last = cls.objects.filter(sequence__isnull=False).order_by("-sequence").values_list("sequence", flat=True).first()
        return max(company.sequence_start, (last or 0) + 1)

    def assign_project_number(self, region=None, user=None):
        """Give this pursuit the next sequence number in its region (phase B)."""
        if region is not None:
            self.region = region
        if not self.region_id:
            raise ValidationError("A region is required to assign a project number.")
        if self.sequence is None:
            self.sequence = self.next_sequence()
        self.save()
        PhaseChange.objects.create(proposal=self, phase=self.phase, note=f"Number {self.project_number} assigned", by=user)
        return self.project_number

    def advance_phase(self, new_phase: str, user=None, note: str = ""):
        if new_phase not in self.Phase.values:
            raise ValidationError("Unknown phase.")
        if self.sequence is None:
            raise ValidationError("Assign a project number before changing phase.")
        old = self.phase
        self.phase = new_phase
        if new_phase != "B" and self.status != self.Status.WON:
            self.status = self.Status.WON
        self.save()
        PhaseChange.objects.create(proposal=self, phase=new_phase, note=note or f"{old} → {new_phase}", by=user)

    @property
    def phase_name(self):
        return self.PHASE_NAMES.get(self.phase, "")

    @property
    def smb_path(self):
        if not self.project_number:
            return ""
        from files.models import FileRoot

        root = FileRoot.for_proposal(self)
        if root:
            return root.full_path(self)
        tpl = CompanyProfile.get_solo().smb_path_template
        if not tpl:
            return ""
        return tpl.format(project_number=self.project_number, phase=self.phase, phase_name=self.phase_name, region=self.region.code if self.region_id else "", seq=self.sequence)

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.next_number()
        if not self.currency_id:
            self.currency = CompanyProfile.get_solo().base_currency
        self.project_number = self.compute_project_number()
        if self.status == self.Status.WON and self.phase == self.Phase.B and self.sequence is not None:
            self.phase = self.Phase.C
            self.project_number = self.compute_project_number()
        if self.status == self.Status.SUBMITTED and not self.submitted_at:
            self.submitted_at = timezone.localdate()
        if self.status in (self.Status.WON, self.Status.LOST) and not self.decided_at:
            self.decided_at = timezone.localdate()
        if self.status == self.Status.WON and not self.project_status:
            self.project_status = self.ProjectStatus.ACTIVE
        super().save(*args, **kwargs)

    @classmethod
    def next_number(cls):
        prefix = CompanyProfile.get_solo().proposal_prefix or "P"
        year = timezone.localdate().year
        stem = f"{prefix}-{year}-"
        last = cls.objects.filter(number__startswith=stem).order_by("-number").values_list("number", flat=True).first()
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{stem}{seq:03d}"

    # ----- money ----------------------------------------------------------------
    @property
    def cur(self) -> Currency:
        return self.currency or CompanyProfile.get_solo().base_currency

    def _lines(self):
        return FeeLine.objects.filter(item__proposal=self)

    @property
    def labour_total(self) -> Decimal:
        return sum((l.amount for l in self._lines().filter(kind=FeeLine.Kind.LABOUR)), ZERO)

    @property
    def expense_total(self) -> Decimal:
        return sum((l.amount for l in self._lines().exclude(kind=FeeLine.Kind.LABOUR)), ZERO)

    @property
    def subtotal(self) -> Decimal:
        return self.labour_total + self.expense_total

    @property
    def contingency_amount(self) -> Decimal:
        return self.subtotal * Decimal(self.contingency_percent or 0) / 100

    @property
    def computed_total(self) -> Decimal:
        return self.subtotal + self.contingency_amount

    @property
    def fee_total(self) -> Decimal:
        if self.manual_value is not None:
            return Decimal(self.manual_value)
        return self.computed_total

    @property
    def fee_total_base(self) -> Decimal:
        return self.cur.to_base(self.fee_total)

    @property
    def weighted_value(self) -> Decimal:
        return self.fee_total * Decimal(self.probability) / 100

    @property
    def weighted_value_base(self) -> Decimal:
        return self.cur.to_base(self.weighted_value)

    @property
    def total_hours(self) -> Decimal:
        return Decimal(self._lines().filter(kind=FeeLine.Kind.LABOUR).aggregate(t=Sum("hours"))["t"] or 0)

    def money(self, amount, decimals=0) -> str:
        return self.cur.format(amount, decimals)

    @property
    def fee_display(self):
        return self.money(self.fee_total)

    def rollup_by_kind(self):
        rows = {}
        for l in self._lines().select_related("item"):
            r = rows.setdefault(l.kind, {"label": l.get_kind_display(), "hours": ZERO, "amount": ZERO})
            r["hours"] += l.hours or 0
            r["amount"] += l.amount
        return list(rows.values())

    def rollup_by_person(self):
        rows = {}
        for l in self._lines().filter(kind=FeeLine.Kind.LABOUR).select_related("employee", "role"):
            key = ("e", l.employee_id) if l.employee_id else ("r", l.role_id)
            label = l.employee.name if l.employee_id else (l.role.title if l.role_id else "Unassigned")
            r = rows.setdefault(key, {"label": label, "hours": ZERO, "amount": ZERO, "rate": l.unit_cost})
            r["hours"] += l.hours or 0
            r["amount"] += l.amount
        return sorted(rows.values(), key=lambda r: -r["amount"])

    # ----- actuals (from timesheets) ----------------------------------------
    @property
    def actual_hours(self) -> Decimal:
        return Decimal(self.actuals.aggregate(t=Sum("hours"))["t"] or 0)

    @property
    def actual_cost_base(self) -> Decimal:
        return Decimal(self.actuals.aggregate(t=Sum("cost"))["t"] or 0)

    @property
    def actual_cost(self) -> Decimal:
        return self.cur.from_base(self.actual_cost_base)

    @property
    def hours_variance_pct(self):
        est = self.total_hours
        return None if not est else round(float((self.actual_hours - est) / est * 100), 1)

    @property
    def cost_variance_pct(self):
        est = self.computed_total
        return None if not est else round(float((self.actual_cost - est) / est * 100), 1)

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
        company = CompanyProfile.get_solo()
        return {
            "client_name": self.client.name if self.client else "[Client]",
            "contact_name": self.contact.name if self.contact else "[Contact]",
            "project_name": self.title,
            "project_location": self.location or "[Location]",
            "proposal_number": self.number,
            "project_number": self.project_number or "[Project no.]",
            "phase": self.phase,
            "company_name": company.name,
            "date": timezone.localdate().strftime("%B %d, %Y"),
            "owner_name": (self.owner.get_full_name() or self.owner.get_username()) if self.owner else "[Lead]",
            "fee_total": self.money(self.fee_total),
            "currency": self.cur.code,
        }

    def render_text(self, text: str) -> str:
        ctx = self.placeholder_context()
        return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: str(ctx.get(m.group(1), m.group(0))), text or "")

    @property
    def rendered_summary(self) -> str:
        return self.render_text(self.summary)

    @property
    def signature(self):
        """(name, title) for the signature block."""
        company = CompanyProfile.get_solo()
        if self.signatory_id:
            return self.signatory.name, self.signatory.role.title
        if self.owner_id:
            emp = getattr(self.owner, "employee", None)
            if emp:
                return emp.name, emp.role.title
            return (self.owner.get_full_name() or self.owner.username), company.signature_title
        return company.signature_name or company.name, company.signature_title

    @property
    def validity_line(self):
        terms = CompanyProfile.get_solo().proposal_terms or ""
        for line in terms.splitlines():
            if line.lower().startswith("validity"):
                return line.split(":", 1)[-1].strip()
        return ""

    def suggested_sheets(self, limit=12):
        from projects.models import PastProject

        attached = set(self.attachments.filter(project__isnull=False).values_list("project_id", flat=True))
        scored = []
        for sheet in PastProject.objects.filter(is_published=True).prefetch_related("services", "client"):
            score, reasons = sheet.relevance_for(self)
            scored.append({"sheet": sheet, "score": score, "reasons": reasons, "attached": sheet.pk in attached})
        scored.sort(key=lambda r: (-r["attached"], -r["score"], r["sheet"].name))
        return scored[:limit] if limit else scored

    def apply_template(self, template: ProposalTemplate):
        start = self.sections.count()
        for i, s in enumerate(template.sections.all()):
            ProposalSection.objects.create(proposal=self, order=start + i, title=s.title, body=s.body)
        self.template = template
        self.save(update_fields=["template"])


class PhaseChange(models.Model):
    """Audit trail of numbering and phase transitions."""

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="phase_changes")
    phase = models.CharField(max_length=1, choices=Proposal.Phase.choices)
    note = models.CharField(max_length=200, blank=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.proposal.number} → {self.phase} ({self.at:%Y-%m-%d})"


class ProjectRecord(Taggable):
    """Execution-phase records that live on the file server: site visit reports,
    photo dumps, instrumentation data, progress rates. Registering them here
    (with their SMB path) is the first step toward mining them for predictions."""

    class Kind(models.TextChoices):
        SITE_VISIT = "site_visit", "Site visit report"
        PHOTOS = "photos", "Photo dump"
        MONITORING = "monitoring", "Instrumentation & monitoring data"
        PROGRESS = "progress", "Progress rate"
        PRESENTATION = "presentation", "Technical presentation"
        CALC = "calc", "Calculation / model"
        OTHER = "other", "Other"

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="records")
    kind = models.CharField(max_length=14, choices=Kind.choices, default=Kind.SITE_VISIT)
    date = models.DateField()
    title = models.CharField(max_length=200)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="For progress rates / readings.")
    unit = models.CharField(max_length=30, blank=True, help_text="e.g. m/day, rings/shift, mm")
    path = models.CharField(max_length=500, blank=True, help_text="File-server path or URL of the document / folder.")
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.date} {self.title}"


class ProposalAttachment(models.Model):
    """Appendices after the main body: project sheets, drawings, calculations, other files."""

    class Kind(models.TextChoices):
        PROJECT_SHEET = "sheet", "Project sheet"
        DRAWING = "drawing", "Drawing"
        CALC = "calc", "Calculation"
        FILE = "file", "Other document"

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="attachments")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PROJECT_SHEET)
    project = models.ForeignKey("projects.PastProject", on_delete=models.CASCADE, null=True, blank=True, related_name="attached_to")
    calc_run = models.ForeignKey("calcs.CalcRun", on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(upload_to="attachments/", blank=True, null=True, help_text="PDF or image appended to the export.")
    title = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("proposal", "project")]

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        if self.project_id:
            return self.project.name
        if self.calc_run_id:
            return self.calc_run.title
        return self.title or (self.file.name.rsplit("/", 1)[-1] if self.file else self.get_kind_display())


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


class FeeItem(models.Model):
    """A work-breakdown line: a task, deliverable, drawing set, report… Each item
    holds granular fee lines (people × hours, expenses, software, subs)."""

    class Kind(models.TextChoices):
        PHASE = "phase", "Phase"
        TASK = "task", "Design task"
        DRAWING = "drawing", "Drawings"
        REPORT = "report", "Report"
        CALC = "calc", "Calculations / analysis"
        MEETING = "meeting", "Meetings & coordination"
        SITE = "site", "Site / construction support"
        PM = "pm", "Project management & QA"
        OTHER = "other", "Other"

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="items")
    code = models.CharField(max_length=20, blank=True, help_text="WBS code, e.g. 2.3")
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.TASK)
    task = models.ForeignKey("scheduling.Task", on_delete=models.SET_NULL, null=True, blank=True, related_name="fee_items", help_text="Link to a schedule bar.")
    notes = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.code} {self.name}".strip()

    @property
    def hours(self) -> Decimal:
        return Decimal(self.lines.filter(kind=FeeLine.Kind.LABOUR).aggregate(t=Sum("hours"))["t"] or 0)

    @property
    def labour_total(self) -> Decimal:
        return sum((l.amount for l in self.lines.filter(kind=FeeLine.Kind.LABOUR)), ZERO)

    @property
    def expense_total(self) -> Decimal:
        return sum((l.amount for l in self.lines.exclude(kind=FeeLine.Kind.LABOUR)), ZERO)

    @property
    def total(self) -> Decimal:
        return sum((l.amount for l in self.lines.all()), ZERO)

    @property
    def actual_hours(self) -> Decimal:
        return Decimal(self.actuals.aggregate(t=Sum("hours"))["t"] or 0)

    @property
    def actual_cost(self) -> Decimal:
        return self.proposal.cur.from_base(Decimal(self.actuals.aggregate(t=Sum("cost"))["t"] or 0))


class FeeLine(models.Model):
    class Kind(models.TextChoices):
        LABOUR = "labour", "Labour"
        EXPENSE = "expense", "Expense"
        SOFTWARE = "software", "Software licence"
        SUB = "sub", "Subconsultant"
        TRAVEL = "travel", "Travel"
        OTHER = "other", "Other"

    item = models.ForeignKey(FeeItem, on_delete=models.CASCADE, related_name="lines")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.LABOUR)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="fee_lines")
    role = models.ForeignKey(StaffRole, on_delete=models.PROTECT, null=True, blank=True, related_name="fee_lines")
    description = models.CharField(max_length=200, blank=True)
    hours = models.DecimalField(max_digits=9, decimal_places=1, null=True, blank=True)
    quantity = models.DecimalField(max_digits=9, decimal_places=2, default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Hourly rate for labour, unit price otherwise (proposal currency).")
    markup_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.label

    @property
    def label(self):
        if self.kind == self.Kind.LABOUR:
            return self.employee.name if self.employee_id else (self.role.title if self.role_id else "Labour")
        return self.description or self.get_kind_display()

    @property
    def amount(self) -> Decimal:
        if self.kind == self.Kind.LABOUR:
            return Decimal(self.hours or 0) * Decimal(self.unit_cost or 0)
        return Decimal(self.quantity or 0) * Decimal(self.unit_cost or 0) * (1 + Decimal(self.markup_percent or 0) / 100)

    def default_rate(self) -> Decimal:
        """Rate from the employee or role card, converted into the proposal currency."""
        base = None
        if self.employee_id:
            base = self.employee.rate
        elif self.role_id:
            base = self.role.default_rate
        if base is None:
            return ZERO
        return self.item.proposal.cur.from_base(base).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        if self.kind == self.Kind.LABOUR:
            if self.employee_id and not self.role_id:
                self.role = self.employee.role
            if not self.unit_cost:
                self.unit_cost = self.default_rate()
            self.quantity = 1
            self.markup_percent = 0
        else:
            self.hours = None
            self.employee = None
            self.role = None
        super().save(*args, **kwargs)

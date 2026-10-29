from django import forms
from django.contrib.auth import get_user_model

from core.models import Currency, Region
from crm.models import Contact

from .models import (
    Employee, FeeItem, FeeLine, Proposal, ProposalSection, ProposalTemplate, Service, StaffRole, TemplateSection,
)

User = get_user_model()


class DateInput(forms.DateInput):
    input_type = "date"


class ProposalForm(forms.ModelForm):
    class Meta:
        model = Proposal
        fields = [
            "title", "region", "client", "contact", "service_type", "owner", "status", "project_status", "due_date",
            "probability", "currency", "location", "summary", "services", "notes",
            "manual_value", "submitted_at", "decided_at",
        ]
        widgets = {
            "due_date": DateInput(), "submitted_at": DateInput(), "decided_at": DateInput(),
            "summary": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "services": forms.CheckboxSelectMultiple(),
            "probability": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(is_active=True).order_by("first_name", "username")
        self.fields["owner"].label_from_instance = lambda u: u.get_full_name() or u.username
        if "services" in self.fields:
            self.fields["services"].queryset = Service.objects.filter(is_active=True)
        if "currency" in self.fields:
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
            self.fields["currency"].required = False
        if "region" in self.fields:
            self.fields["region"].queryset = Region.objects.filter(is_active=True)
            self.fields["region"].required = False
        client_id = None
        if self.data.get("client"):
            client_id = self.data.get("client")
        elif self.instance.pk and self.instance.client_id:
            client_id = self.instance.client_id
        self.fields["contact"].queryset = Contact.objects.filter(client_id=client_id) if client_id else Contact.objects.none()
        self.fields["contact"].required = False


class ProposalCreateForm(ProposalForm):
    template = forms.ModelChoiceField(
        queryset=ProposalTemplate.objects.all(), required=False,
        help_text="Sections from the template are copied into the new proposal.",
    )

    class Meta(ProposalForm.Meta):
        fields = ["title", "region", "client", "contact", "service_type", "owner", "due_date", "currency", "location", "summary", "template"]

    assign_number = forms.BooleanField(required=False, initial=True, label="Assign the next project number now (needs a region)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        default = ProposalTemplate.objects.filter(is_default=True).first()
        if default and not self.is_bound:
            self.fields["template"].initial = default.pk


class ProposalSectionForm(forms.ModelForm):
    class Meta:
        model = ProposalSection
        fields = ["title", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 8})}


class FeeSettingsForm(forms.ModelForm):
    class Meta:
        model = Proposal
        fields = ["currency", "contingency_percent", "manual_value"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
        self.fields["currency"].required = False


class FeeItemForm(forms.ModelForm):
    class Meta:
        model = FeeItem
        fields = ["code", "name", "kind", "task", "notes"]

    def __init__(self, *args, proposal=None, **kwargs):
        super().__init__(*args, **kwargs)
        from scheduling.models import Task

        proposal = proposal or (self.instance.proposal if self.instance.pk else None)
        self.fields["task"].queryset = Task.objects.filter(proposal=proposal) if proposal else Task.objects.none()
        self.fields["task"].required = False
        self.fields["code"].widget.attrs["placeholder"] = "1.1"
        self.fields["name"].widget.attrs["placeholder"] = "e.g. Lining design drawings"


class FeeLineForm(forms.ModelForm):
    class Meta:
        model = FeeLine
        fields = ["kind", "employee", "role", "description", "hours", "quantity", "unit_cost", "markup_percent"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(is_active=True).select_related("role")
        self.fields["role"].queryset = StaffRole.objects.filter(is_active=True)
        for f in ("employee", "role", "hours", "quantity", "unit_cost", "markup_percent", "description"):
            self.fields[f].required = False
        self.fields["unit_cost"].widget.attrs["placeholder"] = "auto"
        self.fields["employee"].label_from_instance = lambda e: f"{e.name} ({e.role})"

    def clean(self):
        data = super().clean()
        if data.get("kind") == FeeLine.Kind.LABOUR:
            if not data.get("employee") and not data.get("role"):
                self.add_error("employee", "Pick an employee or a role.")
            if data.get("hours") is None:
                data["hours"] = 0
        else:
            if data.get("quantity") is None:
                data["quantity"] = 1
            if not data.get("description"):
                self.add_error("description", "Describe the expense.")
        if data.get("unit_cost") is None:
            data["unit_cost"] = 0
        if data.get("markup_percent") is None:
            data["markup_percent"] = 0
        return data


class TemplateForm(forms.ModelForm):
    class Meta:
        model = ProposalTemplate
        fields = ["name", "service_type", "description", "is_default"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class TemplateSectionForm(forms.ModelForm):
    class Meta:
        model = TemplateSection
        fields = ["title", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 8})}


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "category", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class StaffRoleForm(forms.ModelForm):
    class Meta:
        model = StaffRole
        fields = ["title", "default_rate", "is_active"]


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["name", "initials", "role", "rate", "cost_rate", "email", "external_id", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = StaffRole.objects.filter(is_active=True)
        self.fields["initials"].required = False


class ProjectRecordForm(forms.ModelForm):
    class Meta:
        model = __import__("proposals.models", fromlist=["ProjectRecord"]).ProjectRecord
        fields = ["kind", "date", "title", "value", "unit", "path", "notes"]
        widgets = {"date": DateInput()}

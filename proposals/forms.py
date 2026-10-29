from django import forms
from django.contrib.auth import get_user_model

from crm.models import Contact

from .models import (
    Proposal,
    ProposalSection,
    ProposalStaffing,
    ProposalTemplate,
    Service,
    StaffRole,
    TemplateSection,
)

User = get_user_model()


class DateInput(forms.DateInput):
    input_type = "date"


class ProposalForm(forms.ModelForm):
    class Meta:
        model = Proposal
        fields = [
            "title", "client", "contact", "service_type", "owner", "status", "due_date",
            "probability", "location", "summary", "services", "notes",
            "manual_value", "submitted_at", "decided_at",
        ]
        widgets = {
            "due_date": DateInput(),
            "submitted_at": DateInput(),
            "decided_at": DateInput(),
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
        client_id = None
        if self.data.get("client"):
            client_id = self.data.get("client")
        elif self.instance.pk and self.instance.client_id:
            client_id = self.instance.client_id
        self.fields["contact"].queryset = (
            Contact.objects.filter(client_id=client_id) if client_id else Contact.objects.none()
        )
        self.fields["contact"].required = False


class ProposalCreateForm(ProposalForm):
    template = forms.ModelChoiceField(
        queryset=ProposalTemplate.objects.all(),
        required=False,
        help_text="Sections from the template are copied into the new proposal.",
    )

    class Meta(ProposalForm.Meta):
        fields = ["title", "client", "contact", "service_type", "owner", "due_date", "location", "summary", "template"]

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


class StaffingForm(forms.ModelForm):
    class Meta:
        model = ProposalStaffing
        fields = ["role", "task", "hours", "rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = StaffRole.objects.filter(is_active=True)
        self.fields["rate"].required = False
        self.fields["rate"].help_text = "Leave blank to use the role's default rate."


class FeeSettingsForm(forms.ModelForm):
    class Meta:
        model = Proposal
        fields = ["expenses", "markup_percent", "manual_value"]


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

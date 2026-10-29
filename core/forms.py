from django import forms

from .models import CompanyProfile, Currency


class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = [
            "name", "tagline", "logo", "address", "phone", "email", "website",
            "primary_color", "accent_color", "proposal_prefix", "proposal_footer", "default_currency",
            "project_number_pattern", "project_number_example", "project_number_help", "require_project_number_when_won",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "primary_color": forms.TextInput(attrs={"type": "color"}),
            "accent_color": forms.TextInput(attrs={"type": "color"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["default_currency"].queryset = Currency.objects.filter(is_active=True)

    def clean(self):
        data = super().clean()
        import re

        try:
            pat = re.compile(data.get("project_number_pattern") or "")
        except re.error as e:
            self.add_error("project_number_pattern", f"Invalid regular expression: {e}")
            return data
        ex = data.get("project_number_example") or ""
        if ex and not pat.match(ex):
            self.add_error("project_number_example", "The example does not match the pattern.")
        return data


class CurrencyForm(forms.ModelForm):
    class Meta:
        model = Currency
        fields = ["code", "name", "symbol", "rate_to_base", "is_active"]

    def clean_code(self):
        return self.cleaned_data["code"].upper().strip()

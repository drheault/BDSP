from django import forms
from django.contrib.auth import get_user_model

from .models import CAPABILITIES, AccessRole, CompanyProfile, Currency, Region

User = get_user_model()


class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = [
            "name", "tagline", "logo", "address", "phone", "email", "website",
            "primary_color", "accent_color", "proposal_prefix", "proposal_footer", "default_currency",
            "number_digits", "sequence_start", "bd_number_format", "phase_number_format", "require_project_number_when_won",
            "smb_path_template", "notes_server", "notes_database",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "primary_color": forms.TextInput(attrs={"type": "color"}),
            "accent_color": forms.TextInput(attrs={"type": "color"}),
            "number_digits": forms.NumberInput(attrs={"min": 3, "max": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["default_currency"].queryset = Currency.objects.filter(is_active=True)

    def clean(self):
        data = super().clean()
        for f in ("bd_number_format", "phase_number_format"):
            try:
                (data.get(f) or "").format(region="ON", seq="601", phase="B")
            except (KeyError, IndexError, ValueError) as e:
                self.add_error(f, f"Only {{region}}, {{seq}} and {{phase}} are allowed: {e}")
        try:
            (data.get("smb_path_template") or "").format(project_number="x", phase="B", phase_name="x", region="x", seq=1)
        except (KeyError, IndexError, ValueError) as e:
            self.add_error("smb_path_template", f"Unknown placeholder: {e}")
        return data


class CurrencyForm(forms.ModelForm):
    class Meta:
        model = Currency
        fields = ["code", "name", "symbol", "rate_to_base", "is_active"]

    def clean_code(self):
        return self.cleaned_data["code"].upper().strip()


class RegionForm(forms.ModelForm):
    class Meta:
        model = Region
        fields = ["code", "name", "kind", "is_active"]


class AccessRoleForm(forms.ModelForm):
    capabilities = forms.MultipleChoiceField(choices=CAPABILITIES, required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = AccessRole
        fields = ["name", "description", "rank", "capabilities"]


class UserForm(forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput, help_text="Leave blank to keep the current password.")
    roles = forms.ModelMultipleChoiceField(queryset=AccessRole.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active", "is_staff"]
        labels = {"is_staff": "Can use the Django admin"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["roles"].initial = self.instance.access_roles.all()
        else:
            self.fields["password"].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        pw = self.cleaned_data.get("password")
        if pw:
            user.set_password(pw)
        if commit:
            user.save()
            user.access_roles.set(self.cleaned_data["roles"])
        return user

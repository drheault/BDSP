from django import forms
from django.contrib.auth import get_user_model

from .models import CAPABILITIES, AccessRole, CompanyProfile, CustomField, Currency, FieldRule, Region, Theme
from .themes import VAR_KEYS

User = get_user_model()


class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = [
            "name", "tagline", "logo", "address", "phone", "email", "website",
            "primary_color", "accent_color", "proposal_prefix", "proposal_footer", "default_currency",
            "number_digits", "sequence_start", "bd_number_format", "phase_number_format", "require_project_number_when_won",
            "smb_path_template", "notes_server", "notes_database",
            "proposal_terms", "capabilities_statement", "signature_name", "signature_title",
            "landing_visual", "landing_photo",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "proposal_terms": forms.Textarea(attrs={"rows": 7}),
            "capabilities_statement": forms.Textarea(attrs={"rows": 3}),
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
        fields = ["code", "name", "kind", "country", "is_active"]


class AccessRoleForm(forms.ModelForm):
    capabilities = forms.MultipleChoiceField(choices=CAPABILITIES, required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = AccessRole
        fields = ["name", "description", "rank", "capabilities"]


class UserForm(forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput, help_text="Leave blank to keep the current password.")
    roles = forms.ModelMultipleChoiceField(queryset=AccessRole.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)
    office = forms.ModelChoiceField(queryset=None, required=False)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active", "is_staff"]
        labels = {"is_staff": "Can use the Django admin"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Office

        self.fields["office"].queryset = Office.objects.filter(is_active=True)
        if self.instance.pk:
            self.fields["roles"].initial = self.instance.access_roles.all()
            prof = getattr(self.instance, "profile", None)
            if prof:
                self.fields["office"].initial = prof.office_id
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
            from community.models import Profile

            prof, _ = Profile.objects.get_or_create(user=user)
            prof.office = self.cleaned_data.get("office")
            prof.save()
        return user


class ThemeForm(forms.ModelForm):
    """Edits a theme: one field per CSS variable plus custom CSS."""

    class Meta:
        model = Theme
        fields = ["name", "description", "default_mode", "custom_css"]
        widgets = {"custom_css": forms.Textarea(attrs={"rows": 6, "class": "mono", "placeholder": ".card { box-shadow: none; }"})}

    COLOR_KEYS = {"navy", "navy-700", "navy-100", "accent", "accent-100", "ink", "ink-2", "ink-3", "line", "line-2", "bg", "card", "sidebar-bg", "sidebar-ink", "sidebar-muted"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        vals = self.instance.variables or {}
        from .themes import PRESETS, DEFAULT_PRESET

        dark_defaults = dict(PRESETS.get(self.instance.based_on, PRESETS[DEFAULT_PRESET]).get("dark", {}))
        dark_defaults.update(self.instance.dark_variables or {})
        for key in VAR_KEYS:
            color = key in self.COLOR_KEYS
            self.fields[f"var_{key}"] = forms.CharField(label=key, required=False, initial=vals.get(key, ""), widget=forms.TextInput(attrs={"type": "color"}) if color and str(vals.get(key, "")).startswith("#") else forms.TextInput())
            if color:
                dv = dark_defaults.get(key, "")
                self.fields[f"dark_{key}"] = forms.CharField(label=key, required=False, initial=dv, widget=forms.TextInput(attrs={"type": "color"}) if str(dv).startswith("#") else forms.TextInput())

    def save(self, commit=True):
        theme = super().save(commit=False)
        theme.variables = {k: self.cleaned_data.get(f"var_{k}", "") for k in VAR_KEYS if self.cleaned_data.get(f"var_{k}")}
        theme.dark_variables = {k: self.cleaned_data.get(f"dark_{k}", "") for k in self.COLOR_KEYS if self.cleaned_data.get(f"dark_{k}")}
        if commit:
            theme.save()
        return theme

    def var_fields(self):
        return [self[f"var_{k}"] for k in VAR_KEYS]

    def dark_fields(self):
        return [self[f"dark_{k}"] for k in VAR_KEYS if k in self.COLOR_KEYS]


class ThemeImportForm(forms.Form):
    file = forms.FileField(help_text="A theme JSON file exported from this page.")


class FieldRuleForm(forms.ModelForm):
    class Meta:
        model = FieldRule
        fields = ["form_key", "field_name", "label", "help_text", "visible", "required", "order"]
        widgets = {"required": forms.Select(choices=[("", "Default"), ("true", "Required"), ("false", "Optional")])}

    def clean_required(self):
        v = self.data.get("required")
        return None if v in ("", None) else v == "true"


class CustomFieldForm(forms.ModelForm):
    class Meta:
        model = CustomField
        fields = ["form_key", "key", "label", "type", "choices", "help_text", "required", "show_in_export", "order", "is_active"]


class OfficeForm(forms.ModelForm):
    class Meta:
        model = __import__("core.models", fromlist=["Office"]).Office
        fields = ["code", "name", "city", "country", "latitude", "longitude", "timezone", "is_hq", "notes", "order", "is_active"]

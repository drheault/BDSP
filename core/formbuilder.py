"""Apply admin-defined field rules and custom fields to a ModelForm.

Usage: class ProposalForm(ConfigurableFormMixin, forms.ModelForm): form_key = "proposal"
Rules (FieldRule) can hide, require, relabel and reorder built-in fields.
Custom fields (CustomField) are added as `cf_<key>` and stored in instance.extra.
"""

from django import forms

from .models import CustomField, FieldRule


class ConfigurableFormMixin:
    form_key = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.form_key:
            return
        rules = {r.field_name: r for r in FieldRule.objects.filter(form_key=self.form_key)}
        order = []
        for name in list(self.fields.keys()):
            rule = rules.get(name)
            if rule is None:
                order.append((100, name))
                continue
            if not rule.visible:
                self.fields.pop(name)
                continue
            f = self.fields[name]
            if rule.label:
                f.label = rule.label
            if rule.help_text:
                f.help_text = rule.help_text
            if rule.required is not None:
                f.required = rule.required
            order.append((rule.order, name))
        extra = getattr(self.instance, "extra", None) or {}
        self.custom_fields = list(CustomField.objects.filter(form_key=self.form_key, is_active=True))
        for cf in self.custom_fields:
            name = f"cf_{cf.key}"
            common = {"label": cf.label, "help_text": cf.help_text, "required": cf.required, "initial": extra.get(cf.key)}
            if cf.type == "long":
                field = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **common)
            elif cf.type == "number":
                field = forms.FloatField(**common)
            elif cf.type == "date":
                field = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **common)
            elif cf.type == "bool":
                field = forms.BooleanField(**{**common, "required": False})
            elif cf.type == "choice":
                field = forms.ChoiceField(choices=[("", "—")] + [(c, c) for c in cf.choice_list], **common)
            else:
                field = forms.CharField(max_length=255, **common)
            self.fields[name] = field
            order.append((cf.order + 1000, name))
        self.order_fields([n for _, n in sorted(order, key=lambda t: t[0])])

    def save(self, commit=True):
        obj = super().save(commit=False)
        if hasattr(obj, "extra") and getattr(self, "custom_fields", None):
            extra = dict(obj.extra or {})
            for cf in self.custom_fields:
                val = self.cleaned_data.get(f"cf_{cf.key}")
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                extra[cf.key] = val
            obj.extra = extra
        if commit:
            obj.save()
            if hasattr(self, "save_m2m"):
                self.save_m2m()
            if hasattr(obj, "set_tags") and "tags" in self.cleaned_data:
                obj.set_tags(self.cleaned_data.get("tags", []))
        return obj

    def custom_field_values(self):
        return [(cf, (getattr(self.instance, "extra", None) or {}).get(cf.key)) for cf in getattr(self, "custom_fields", [])]

from django import forms

from tags.forms import TaggableFormMixin

from .models import Tool


class ToolUploadForm(TaggableFormMixin, forms.ModelForm):
    class Meta:
        model = Tool
        fields = ["name", "category", "summary", "description", "file", "url", "version"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5, "placeholder": "Method, assumptions, references, when to use it."})}

    def clean(self):
        data = super().clean()
        if not data.get("file") and not data.get("url"):
            self.add_error("file", "Upload a file or give a link.")
        return data


def engine_form(engine, data=None, initial=None):
    """Build a plain Form from an engine's declared inputs (with slider ranges and parameter links)."""
    fields = {}
    initial = initial or {}
    for i in engine.inputs:
        init = initial.get(i.name, i.default)
        if i.choices:
            fields[i.name] = forms.TypedChoiceField(choices=[(str(c[0]), c[1]) for c in i.choices], coerce=float, initial=str(init), label=i.label, help_text=i.help)
        else:
            attrs = {"step": i.step or "any", "class": "live"}
            if i.min is not None and i.max is not None:
                attrs.update({"data-min": i.min, "data-max": i.max})
            if i.param:
                attrs["data-param"] = i.param
            fields[i.name] = forms.FloatField(initial=init, label=f"{i.label}{' (' + i.unit + ')' if i.unit else ''}", help_text=i.help, widget=forms.NumberInput(attrs=attrs))
    return type("EngineForm", (forms.Form,), fields)(data)


class SpecToolForm(TaggableFormMixin, forms.ModelForm):
    spec_text = forms.CharField(label="Tool definition (JSON)", widget=forms.Textarea(attrs={"rows": 18, "class": "mono"}), help_text="Inputs, formulas, outputs, checks and chart. Start from the example and edit.")

    class Meta:
        model = Tool
        fields = ["name", "category", "summary", "description", "version"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def clean_spec_text(self):
        import json

        from .spec import SpecError, validate_spec

        try:
            spec = json.loads(self.cleaned_data["spec_text"])
            validate_spec(spec)
        except (ValueError, SpecError) as e:
            raise forms.ValidationError(str(e))
        return spec

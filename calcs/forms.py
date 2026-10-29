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


def engine_form(engine, data=None):
    """Build a plain Form from an engine's declared inputs."""
    fields = {}
    for i in engine.inputs:
        if i.choices:
            fields[i.name] = forms.TypedChoiceField(choices=[(str(c[0]), c[1]) for c in i.choices], coerce=float, initial=str(i.default), label=i.label, help_text=i.help)
        else:
            fields[i.name] = forms.FloatField(initial=i.default, label=f"{i.label}{' (' + i.unit + ')' if i.unit else ''}", help_text=i.help, widget=forms.NumberInput(attrs={"step": i.step or "any"}))
    return type("EngineForm", (forms.Form,), fields)(data)

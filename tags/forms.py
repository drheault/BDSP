from django import forms

from .models import Tag


class TagInput(forms.TextInput):
    """Comma-separated tag input with a datalist of existing tags."""

    template_name = "django/forms/widgets/text.html"

    def __init__(self, attrs=None):
        attrs = {"class": "tag-input", "placeholder": "e.g. SEM, soft ground, metro, Plaxis — comma separated", "list": "tag-datalist", "autocomplete": "off", **(attrs or {})}
        super().__init__(attrs)


class TagsField(forms.CharField):
    widget = TagInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("label", "Tags")
        kwargs.setdefault("help_text", "Comma-separated. New tags are created in the General category; organise them under Tags.")
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        return [v.strip() for v in (value or "").split(",") if v.strip()]

    def prepare_value(self, value):
        if isinstance(value, (list, tuple)):
            return ", ".join(value)
        return value


class TaggableFormMixin:
    """Add a `tags` field to a ModelForm for a Taggable model and save it."""

    tags = TagsField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"] = TagsField()
        if self.instance.pk and not self.is_bound:
            self.fields["tags"].initial = [t.name for t in self.instance.tags]

    def save(self, commit=True):
        obj = super().save(commit=commit)
        if commit:
            obj.set_tags(self.cleaned_data.get("tags", []))
        return obj


def tag_datalist():
    return Tag.objects.select_related("category").order_by("name")

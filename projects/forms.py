from django import forms

from core.formbuilder import ConfigurableFormMixin
from proposals.models import Service
from tags.forms import TaggableFormMixin

from .models import PastProject, ProjectImage


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(d, initial) for d in data]
        return single_clean(data, initial)


class PastProjectForm(TaggableFormMixin, ConfigurableFormMixin, forms.ModelForm):
    form_key = "project_sheet"

    class Meta:
        model = PastProject
        fields = [
            "name", "kind", "client", "client_name", "location", "role", "year_completed",
            "construction_value", "fee_value", "duration_months", "key_dimensions", "services",
            "description", "challenges", "contribution", "value_added", "highlights",
            "source_path", "reference_contact", "is_featured", "is_published",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}), "challenges": forms.Textarea(attrs={"rows": 3}),
            "contribution": forms.Textarea(attrs={"rows": 3}), "value_added": forms.Textarea(attrs={"rows": 3}),
            "highlights": forms.Textarea(attrs={"rows": 3, "placeholder": "One highlight per line"}),
            "services": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "services" in self.fields:
            self.fields["services"].queryset = Service.objects.filter(is_active=True)


class ImageUploadForm(forms.Form):
    images = MultipleFileField(required=True)
    caption = forms.CharField(max_length=250, required=False)


class ImageCaptionForm(forms.ModelForm):
    class Meta:
        model = ProjectImage
        fields = ["caption"]

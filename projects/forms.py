from django import forms

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


class PastProjectForm(forms.ModelForm):
    class Meta:
        model = PastProject
        fields = [
            "name", "kind", "client", "client_name", "location", "role", "year_completed",
            "construction_value", "key_dimensions", "description", "highlights", "is_featured",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "highlights": forms.Textarea(attrs={"rows": 4, "placeholder": "One highlight per line"}),
        }


class ImageUploadForm(forms.Form):
    images = MultipleFileField(required=True)
    caption = forms.CharField(max_length=250, required=False)


class ImageCaptionForm(forms.ModelForm):
    class Meta:
        model = ProjectImage
        fields = ["caption"]

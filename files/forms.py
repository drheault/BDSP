from django import forms

from .models import FileRoot


class FileRootForm(forms.ModelForm):
    class Meta:
        model = FileRoot
        fields = ["name", "kind", "path", "username", "password", "domain", "project_folder_template", "allow_upload", "is_active"]
        widgets = {"password": forms.PasswordInput(render_value=True)}

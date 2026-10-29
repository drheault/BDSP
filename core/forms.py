from django import forms

from .models import CompanyProfile


class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = [
            "name", "tagline", "logo", "address", "phone", "email", "website",
            "primary_color", "accent_color", "proposal_prefix", "proposal_footer",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "primary_color": forms.TextInput(attrs={"type": "color"}),
            "accent_color": forms.TextInput(attrs={"type": "color"}),
        }

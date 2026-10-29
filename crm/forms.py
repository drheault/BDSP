from django import forms

from .models import Client, Contact


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "sector", "address", "website", "notes"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2}), "notes": forms.Textarea(attrs={"rows": 3})}


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["name", "title", "email", "phone", "is_primary", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

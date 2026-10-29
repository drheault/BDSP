from django import forms

from core.formbuilder import ConfigurableFormMixin

from .models import Client, Contact


class ClientForm(ConfigurableFormMixin, forms.ModelForm):
    form_key = "client"

    class Meta:
        model = Client
        fields = ["name", "sector", "address", "website", "notes"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2}), "notes": forms.Textarea(attrs={"rows": 3})}


class ContactForm(ConfigurableFormMixin, forms.ModelForm):
    form_key = "contact"

    class Meta:
        model = Contact
        fields = ["name", "title", "email", "phone", "is_primary", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

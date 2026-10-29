from django import forms

from .models import Request, RequestKind


class RequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ["kind", "title", "details", "priority"]
        widgets = {"details": forms.Textarea(attrs={"rows": 5, "placeholder": "What do you need, and why? Include links or numbers where useful."})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].queryset = RequestKind.objects.filter(is_active=True)


class TriageForm(forms.ModelForm):
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Note for the requester (optional)"}))

    class Meta:
        model = Request
        fields = ["status", "priority", "assignee", "resolution"]
        widgets = {"resolution": forms.Textarea(attrs={"rows": 3})}

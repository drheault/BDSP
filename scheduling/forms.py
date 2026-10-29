from django import forms

from .models import Task


class DateInput(forms.DateInput):
    input_type = "date"


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["name", "phase", "start", "end", "is_milestone", "percent_complete", "predecessor"]
        widgets = {
            "start": DateInput(),
            "end": DateInput(),
            "percent_complete": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 5}),
        }

    def __init__(self, *args, proposal=None, **kwargs):
        super().__init__(*args, **kwargs)
        proposal = proposal or (self.instance.proposal if self.instance.pk else None)
        qs = Task.objects.filter(proposal=proposal) if proposal else Task.objects.none()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["predecessor"].queryset = qs
        self.fields["predecessor"].required = False
        self.fields["end"].required = False
        self.fields["percent_complete"].required = False

    def clean(self):
        data = super().clean()
        if data.get("is_milestone") and data.get("start"):
            data["end"] = data["start"]
        if not data.get("end") and data.get("start"):
            data["end"] = data["start"]
        if data.get("percent_complete") is None:
            data["percent_complete"] = 0
        if data.get("start") and data.get("end") and data["end"] < data["start"]:
            self.add_error("end", "End must be on or after start.")
        return data

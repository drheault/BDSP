from django import forms

from proposals.models import Employee, FeeItem

from .models import ActualEntry


class DateInput(forms.DateInput):
    input_type = "date"


class ActualEntryForm(forms.ModelForm):
    class Meta:
        model = ActualEntry
        fields = ["date", "employee", "item", "hours", "cost", "description"]
        widgets = {"date": DateInput()}

    def __init__(self, *args, proposal=None, **kwargs):
        super().__init__(*args, **kwargs)
        proposal = proposal or (self.instance.proposal if self.instance.pk else None)
        self.fields["item"].queryset = FeeItem.objects.filter(proposal=proposal) if proposal else FeeItem.objects.none()
        self.fields["item"].required = False
        self.fields["employee"].queryset = Employee.objects.filter(is_active=True)
        self.fields["cost"].required = False
        self.fields["cost"].help_text = "Base currency; blank = hours × employee rate."


class CsvImportForm(forms.Form):
    file = forms.FileField(help_text="CSV with columns: date, employee, hours and optionally project_number, task, cost, description, id.")
    source = forms.ChoiceField(choices=[("csv", "CSV import"), ("ots", "Office Timesheets export")], initial="csv")

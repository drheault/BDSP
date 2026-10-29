from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from proposals.models import Proposal

from .forms import ActualEntryForm, CsvImportForm
from .importer import import_csv
from .models import ActualEntry


def _rows(proposal):
    """Estimate vs actual per fee item and per employee."""
    items = []
    for it in proposal.items.all():
        est_h, act_h = it.hours, it.actual_hours
        items.append({"item": it, "est_hours": est_h, "act_hours": act_h, "est_cost": it.total, "act_cost": it.actual_cost,
                      "pct": (float(act_h / est_h * 100) if est_h else None)})
    unmapped = proposal.actuals.filter(item__isnull=True)
    if unmapped.exists():
        from django.db.models import Sum

        agg = unmapped.aggregate(h=Sum("hours"), c=Sum("cost"))
        items.append({"item": None, "est_hours": 0, "act_hours": agg["h"] or 0, "est_cost": 0, "act_cost": proposal.cur.from_base(agg["c"] or 0), "pct": None})
    people = {}
    for l in proposal._lines().filter(kind="labour").select_related("employee", "role"):
        key = l.employee.name if l.employee_id else (l.role.title if l.role_id else "Unassigned")
        p = people.setdefault(key, {"label": key, "est": 0, "act": 0})
        p["est"] += l.hours or 0
    for a in proposal.actuals.select_related("employee"):
        key = a.employee.name if a.employee_id else (a.employee_name or "Unmatched")
        p = people.setdefault(key, {"label": key, "est": 0, "act": 0})
        p["act"] += a.hours
    return items, sorted(people.values(), key=lambda p: -(p["est"] + p["act"]))


@login_required
def proposal_actuals(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    items, people = _rows(proposal)
    return render(
        request, "timesheets/proposal_actuals.html",
        {
            "proposal": proposal, "tab": "actuals", "items": items, "people": people,
            "entries": proposal.actuals.select_related("employee", "item")[:60],
            "entries_total": proposal.actuals.count(),
            "entry_form": ActualEntryForm(proposal=proposal, initial={"date": timezone.localdate()}),
            "import_form": CsvImportForm(),
        },
    )


@login_required
@require_POST
def actual_add(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    form = ActualEntryForm(request.POST, proposal=proposal)
    if form.is_valid():
        e = form.save(commit=False)
        e.proposal = proposal
        e.save()
        messages.success(request, "Time entry added.")
    else:
        messages.error(request, f"Could not add entry: {form.errors.as_text()}")
    return redirect("proposal_actuals", pk=pk)


@login_required
@require_POST
def actual_delete(request, pk):
    e = get_object_or_404(ActualEntry, pk=pk)
    e.delete()
    return redirect("proposal_actuals", pk=e.proposal_id)


@login_required
@require_POST
def actual_import(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    form = CsvImportForm(request.POST, request.FILES)
    if form.is_valid():
        result = import_csv(form.cleaned_data["file"], source=form.cleaned_data["source"], default_proposal=proposal)
        messages.success(request, f"Imported {result['created']} entries, skipped {result['skipped']} duplicates.")
        for err in result["errors"][:5]:
            messages.warning(request, err)
    else:
        messages.error(request, "Please choose a CSV file.")
    return redirect("proposal_actuals", pk=pk)

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required

from core.permissions import require_cap
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from proposals.models import Proposal
from proposals.utils import move_item

from .forms import TaskForm
from .gantt import build_gantt, create_default_tasks, summary_item
from .models import Task


def _panel(request, proposal, form=None, status=200):
    tasks = proposal.tasks.select_related("predecessor")
    return render(
        request,
        "scheduling/_schedule_panel.html",
        {
            "proposal": proposal,
            "tasks": tasks,
            "gantt": build_gantt(tasks),
            "task_form": form or TaskForm(proposal=proposal, initial={"start": timezone.localdate()}),
            "phases": Task.Phase.choices,
            "phase_colors": Task.PHASE_COLORS,
        },
        status=status,
    )


@login_required
def proposal_schedule(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    tasks = proposal.tasks.select_related("predecessor")
    return render(
        request,
        "scheduling/proposal_schedule.html",
        {
            "proposal": proposal,
            "tab": "schedule",
            "tasks": tasks,
            "gantt": build_gantt(tasks),
            "task_form": TaskForm(proposal=proposal, initial={"start": timezone.localdate()}),
            "phases": Task.Phase.choices,
            "phase_colors": Task.PHASE_COLORS,
            "today": timezone.localdate(),
        },
    )


@login_required
@require_cap("edit_proposals")
@require_POST
def task_add(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    form = TaskForm(request.POST, proposal=proposal)
    if form.is_valid():
        task = form.save(commit=False)
        task.proposal = proposal
        task.order = proposal.tasks.count()
        task.save()
        return _panel(request, proposal)
    return _panel(request, proposal, form, 422)


@login_required
@require_cap("edit_proposals")
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            return _panel(request, task.proposal)
    else:
        form = TaskForm(instance=task)
    return render(request, "scheduling/_task_edit_row.html", {"task": task, "form": form})


@login_required
def task_row(request, pk):
    task = get_object_or_404(Task, pk=pk)
    return render(request, "scheduling/_task_row.html", {"t": task})


@login_required
@require_cap("edit_proposals")
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    proposal = task.proposal
    task.delete()
    return _panel(request, proposal)


@login_required
@require_cap("edit_proposals")
@require_POST
def task_move(request, pk, direction):
    task = get_object_or_404(Task, pk=pk)
    move_item(task, direction, task.proposal.tasks.all())
    return _panel(request, task.proposal)


@login_required
@require_cap("edit_proposals")
@require_POST
def task_shift(request, pk):
    task = get_object_or_404(Task, pk=pk)
    try:
        days = int(request.POST.get("days", 0))
    except ValueError:
        days = 0
    if request.POST.get("cascade"):
        _shift_with_successors(task, days)
    else:
        task.shift(days)
    return _panel(request, task.proposal)


def _shift_with_successors(task, days, seen=None):
    seen = seen or set()
    if task.pk in seen:
        return
    seen.add(task.pk)
    task.shift(days)
    for s in task.successors.all():
        _shift_with_successors(s, days, seen)


@login_required
@require_cap("edit_proposals")
@require_POST
def schedule_defaults(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    start_raw = request.POST.get("start")
    try:
        start = timezone.datetime.strptime(start_raw, "%Y-%m-%d").date() if start_raw else timezone.localdate()
    except ValueError:
        start = timezone.localdate()
    if request.POST.get("replace"):
        proposal.tasks.all().delete()
    created = create_default_tasks(proposal, start)
    messages.success(request, f"Added {len(created)} default schedule items.")
    return redirect("proposal_schedule", pk=pk)


@login_required
@require_cap("edit_proposals")
@require_POST
def schedule_shift_all(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    try:
        days = int(request.POST.get("days", 0))
    except ValueError:
        days = 0
    for t in proposal.tasks.all():
        t.shift(days)
    return _panel(request, proposal)


@login_required
def programme(request):
    """Portfolio view: one bar per open proposal, plus upcoming milestones."""
    proposals = Proposal.objects.filter(status__in=Proposal.OPEN_STATUSES).prefetch_related("tasks")
    include_won = request.GET.get("won") == "1"
    if include_won:
        proposals = Proposal.objects.filter(status__in=list(Proposal.OPEN_STATUSES) + ["won"]).prefetch_related("tasks")
    items = [i for i in (summary_item(p, p.tasks.all()) for p in proposals) if i]
    items.sort(key=lambda i: i.start)
    today = timezone.localdate()
    milestones = (
        Task.objects.filter(is_milestone=True, start__gte=today, start__lte=today + timedelta(days=90))
        .filter(proposal__in=proposals)
        .select_related("proposal")
        .order_by("start")
    )
    return render(
        request,
        "scheduling/programme.html",
        {"gantt": build_gantt(items), "items": items, "milestones": milestones, "include_won": include_won},
    )

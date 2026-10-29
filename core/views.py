from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from proposals.models import Proposal
from scheduling.models import Task

from .forms import CompanyProfileForm
from .models import CompanyProfile


@login_required
def dashboard(request):
    today = timezone.localdate()
    proposals = Proposal.objects.select_related("client", "owner")
    open_qs = proposals.filter(status__in=Proposal.OPEN_STATUSES)

    status_counts = {
        row["status"]: row["n"] for row in proposals.values("status").annotate(n=Count("id"))
    }
    pipeline = [
        {"key": key, "label": label, "count": status_counts.get(key, 0)}
        for key, label in Proposal.Status.choices
    ]

    open_list = list(open_qs)
    pipeline_value = sum((p.fee_total for p in open_list), 0)
    weighted_value = sum((p.weighted_value for p in open_list), 0)

    won = status_counts.get("won", 0)
    lost = status_counts.get("lost", 0)
    win_rate = round(100 * won / (won + lost)) if (won + lost) else None

    due_soon = open_qs.filter(due_date__gte=today, due_date__lte=today + timedelta(days=30)).order_by(
        "due_date"
    )
    overdue = open_qs.filter(due_date__lt=today).order_by("due_date")
    recent = proposals[:6]
    upcoming_milestones = (
        Task.objects.filter(is_milestone=True, start__gte=today, proposal__status__in=Proposal.OPEN_STATUSES)
        .select_related("proposal")
        .order_by("start")[:6]
    )

    return render(
        request,
        "core/dashboard.html",
        {
            "pipeline": pipeline,
            "open_count": len(open_list),
            "pipeline_value": pipeline_value,
            "weighted_value": weighted_value,
            "win_rate": win_rate,
            "won": won,
            "lost": lost,
            "due_soon": due_soon,
            "overdue": overdue,
            "recent": recent,
            "upcoming_milestones": upcoming_milestones,
        },
    )


@login_required
def company_settings(request):
    profile = CompanyProfile.get_solo()
    if request.method == "POST":
        form = CompanyProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            if request.POST.get("remove_logo"):
                profile.logo.delete(save=False)
                form.instance.logo = None
            form.save()
            messages.success(request, "Company profile saved.")
            return redirect("company_settings")
    else:
        form = CompanyProfileForm(instance=profile)
    return render(request, "core/settings.html", {"form": form, "profile": profile})


@login_required
def metrics(request):
    """Early BD analytics: win rate by sector, service type, and owner."""
    proposals = Proposal.objects.select_related("client", "owner")
    decided = proposals.filter(status__in=["won", "lost"])

    def breakdown(group_attr, label_fn):
        buckets = {}
        for p in decided:
            key = group_attr(p)
            b = buckets.setdefault(key, {"label": label_fn(p), "won": 0, "lost": 0, "value_won": 0})
            if p.status == "won":
                b["won"] += 1
                b["value_won"] += p.fee_total
            else:
                b["lost"] += 1
        rows = []
        for b in buckets.values():
            total = b["won"] + b["lost"]
            b["total"] = total
            b["rate"] = round(100 * b["won"] / total) if total else 0
            rows.append(b)
        return sorted(rows, key=lambda r: -r["total"])

    by_sector = breakdown(
        lambda p: p.client.sector if p.client else "none",
        lambda p: p.client.get_sector_display() if p.client else "No client",
    )
    by_service = breakdown(lambda p: p.service_type, lambda p: p.get_service_type_display())
    by_owner = breakdown(
        lambda p: p.owner_id,
        lambda p: (p.owner.get_full_name() or p.owner.username) if p.owner else "Unassigned",
    )

    monthly = (
        proposals.filter(submitted_at__isnull=False)
        .values("submitted_at__year", "submitted_at__month")
        .annotate(n=Count("id"))
        .order_by("submitted_at__year", "submitted_at__month")
    )
    max_month = max((m["n"] for m in monthly), default=1)

    return render(
        request,
        "core/metrics.html",
        {
            "by_sector": by_sector,
            "by_service": by_service,
            "by_owner": by_owner,
            "monthly": monthly,
            "max_month": max_month,
            "decided_count": decided.count(),
            "total_value_won": sum((p.fee_total for p in decided if p.status == "won"), 0),
        },
    )

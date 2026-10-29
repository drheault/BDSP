from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from proposals.models import Proposal
from scheduling.models import Task

from .forms import AccessRoleForm, CompanyProfileForm, CurrencyForm, RegionForm, UserForm
from .models import CAPABILITIES, AccessRole, CompanyProfile, Currency, Region
from .permissions import require_cap

User = get_user_model()

ZERO = Decimal(0)


@login_required
def dashboard(request):
    today = timezone.localdate()
    company = CompanyProfile.get_solo()
    base = company.base_currency
    proposals = Proposal.objects.select_related("client", "owner", "currency")
    open_qs = proposals.filter(status__in=Proposal.OPEN_STATUSES)

    status_counts = {row["status"]: row["n"] for row in proposals.values("status").annotate(n=Count("id"))}
    pipeline = [{"key": key, "label": label, "count": status_counts.get(key, 0)} for key, label in Proposal.Status.choices]

    open_list = list(open_qs)
    pipeline_value = sum((p.fee_total_base for p in open_list), ZERO)
    weighted_value = sum((p.weighted_value_base for p in open_list), ZERO)

    won = status_counts.get("won", 0)
    lost = status_counts.get("lost", 0)
    win_rate = round(100 * won / (won + lost)) if (won + lost) else None

    due_soon = open_qs.filter(due_date__gte=today, due_date__lte=today + timedelta(days=30)).order_by("due_date")
    overdue = open_qs.filter(due_date__lt=today).order_by("due_date")
    recent = proposals[:6]
    upcoming_milestones = (
        Task.objects.filter(is_milestone=True, start__gte=today, proposal__status__in=Proposal.OPEN_STATUSES)
        .select_related("proposal").order_by("start")[:6]
    )
    active_projects = proposals.filter(status="won").exclude(project_status="complete")[:5]

    return render(
        request, "core/dashboard.html",
        {
            "base": base, "pipeline": pipeline, "open_count": len(open_list), "pipeline_value": pipeline_value,
            "weighted_value": weighted_value, "win_rate": win_rate, "won": won, "lost": lost,
            "due_soon": due_soon, "overdue": overdue, "recent": recent, "upcoming_milestones": upcoming_milestones,
            "active_projects": active_projects,
        },
    )


@login_required
@require_cap("manage_settings")
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
    return render(request, "core/settings.html", {"form": form, "profile": profile, "currencies": Currency.objects.all(), "currency_form": CurrencyForm(), "regions": Region.objects.all(), "region_form": RegionForm()})


# ---- currencies (htmx) ---------------------------------------------------------
def _currency_list(request, form=None, status=200):
    return render(request, "core/_currency_list.html", {"currencies": Currency.objects.all(), "currency_form": form or CurrencyForm(), "profile": CompanyProfile.get_solo()}, status=status)


@login_required
@require_cap("manage_settings")
@require_POST
def currency_add(request):
    form = CurrencyForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.sort_order = Currency.objects.count()
        c.save()
        return _currency_list(request)
    return _currency_list(request, form, 422)


@login_required
@require_cap("manage_settings")
def currency_edit(request, pk):
    cur = get_object_or_404(Currency, pk=pk)
    if request.method == "POST":
        form = CurrencyForm(request.POST, instance=cur)
        if form.is_valid():
            form.save()
            return _currency_list(request)
    else:
        form = CurrencyForm(instance=cur)
    return render(request, "core/_currency_edit.html", {"currency": cur, "form": form})


@login_required
@require_cap("manage_settings")
@require_POST
def currency_delete(request, pk):
    cur = get_object_or_404(Currency, pk=pk)
    profile = CompanyProfile.get_solo()
    if cur.proposals.exists() or profile.default_currency_id == cur.pk:
        cur.is_active = False
        cur.save()
    else:
        cur.delete()
    return _currency_list(request)


@login_required
@require_cap("manage_settings")
@require_POST
def currency_make_default(request, pk):
    cur = get_object_or_404(Currency, pk=pk)
    profile = CompanyProfile.get_solo()
    profile.default_currency = cur
    profile.save()
    return _currency_list(request)


# ---- regions (htmx) ----------------------------------------------------------
def _region_list(request, form=None, status=200):
    return render(request, "core/_region_list.html", {"regions": Region.objects.all(), "region_form": form or RegionForm()}, status=status)


@login_required
@require_cap("manage_settings")
@require_POST
def region_add(request):
    form = RegionForm(request.POST)
    if form.is_valid():
        form.save()
        return _region_list(request)
    return _region_list(request, form, 422)


@login_required
@require_cap("manage_settings")
def region_edit(request, pk):
    region = get_object_or_404(Region, pk=pk)
    if request.method == "POST":
        form = RegionForm(request.POST, instance=region)
        if form.is_valid():
            form.save()
            return _region_list(request)
    else:
        form = RegionForm(instance=region)
    return render(request, "core/_region_edit.html", {"region": region, "form": form})


@login_required
@require_cap("manage_settings")
@require_POST
def region_delete(request, pk):
    region = get_object_or_404(Region, pk=pk)
    if region.proposals.exists():
        region.is_active = False
        region.save()
    else:
        region.delete()
    return _region_list(request)


# ---- access roles & users ------------------------------------------------------
@login_required
@require_cap("manage_users")
def roles(request):
    return render(request, "core/roles.html", {"roles": AccessRole.objects.prefetch_related("users"), "capabilities": CAPABILITIES})


@login_required
@require_cap("manage_users")
def role_form(request, pk=None):
    role = get_object_or_404(AccessRole, pk=pk) if pk else None
    form = AccessRoleForm(request.POST or None, instance=role)
    if request.method == "POST" and form.is_valid():
        r = form.save()
        messages.success(request, f"Role “{r}” saved.")
        return redirect("roles")
    return render(request, "core/role_form.html", {"form": form, "role": role})


@login_required
@require_cap("manage_users")
@require_POST
def role_delete(request, pk):
    role = get_object_or_404(AccessRole, pk=pk)
    if role.is_system:
        messages.error(request, "Seeded roles can be edited but not deleted.")
    else:
        role.delete()
        messages.success(request, "Role deleted.")
    return redirect("roles")


@login_required
@require_cap("manage_users")
def users(request):
    return render(request, "core/users.html", {"users": User.objects.prefetch_related("access_roles").order_by("-is_active", "first_name", "username")})


@login_required
@require_cap("manage_users")
def user_form(request, pk=None):
    user = get_object_or_404(User, pk=pk) if pk else None
    form = UserForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        u = form.save()
        messages.success(request, f"User “{u.username}” saved.")
        return redirect("users")
    return render(request, "core/user_form.html", {"form": form, "obj": user})


@login_required
@require_cap("view_metrics")
def metrics(request):
    """BD analytics: win rate by sector/service/owner, and estimate accuracy on won work."""
    base = CompanyProfile.get_solo().base_currency
    proposals = Proposal.objects.select_related("client", "owner", "currency")
    decided = proposals.filter(status__in=["won", "lost"])

    def breakdown(group_attr, label_fn):
        buckets = {}
        for p in decided:
            key = group_attr(p)
            b = buckets.setdefault(key, {"label": label_fn(p), "won": 0, "lost": 0, "value_won": ZERO})
            if p.status == "won":
                b["won"] += 1
                b["value_won"] += p.fee_total_base
            else:
                b["lost"] += 1
        rows = []
        for b in buckets.values():
            total = b["won"] + b["lost"]
            b["total"] = total
            b["rate"] = round(100 * b["won"] / total) if total else 0
            rows.append(b)
        return sorted(rows, key=lambda r: -r["total"])

    by_sector = breakdown(lambda p: p.client.sector if p.client else "none", lambda p: p.client.get_sector_display() if p.client else "No client")
    by_service = breakdown(lambda p: p.service_type, lambda p: p.get_service_type_display())
    by_owner = breakdown(lambda p: p.owner_id, lambda p: (p.owner.get_full_name() or p.owner.username) if p.owner else "Unassigned")

    monthly = (
        proposals.filter(submitted_at__isnull=False)
        .values("submitted_at__year", "submitted_at__month").annotate(n=Count("id"))
        .order_by("submitted_at__year", "submitted_at__month")
    )
    max_month = max((m["n"] for m in monthly), default=1)

    # estimate accuracy on won projects with booked hours
    accuracy = []
    for p in proposals.filter(status="won"):
        if p.actual_hours and p.total_hours:
            accuracy.append({"p": p, "est_h": p.total_hours, "act_h": p.actual_hours, "hv": p.hours_variance_pct, "est_c": p.computed_total, "act_c": p.actual_cost, "cv": p.cost_variance_pct})
    avg_hv = (sum(a["hv"] for a in accuracy) / len(accuracy)) if accuracy else None

    return render(
        request, "core/metrics.html",
        {
            "base": base, "by_sector": by_sector, "by_service": by_service, "by_owner": by_owner, "monthly": monthly, "max_month": max_month,
            "decided_count": decided.count(), "total_value_won": sum((p.fee_total_base for p in decided if p.status == "won"), ZERO),
            "accuracy": accuracy, "avg_hv": avg_hv,
        },
    )

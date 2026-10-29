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

from .forms import AccessRoleForm, CompanyProfileForm, CurrencyForm, CustomFieldForm, FieldRuleForm, RegionForm, ThemeForm, ThemeImportForm, UserForm
from .models import CAPABILITIES, FORM_KEYS, AccessRole, CompanyProfile, CustomField, Currency, FieldRule, Region, Theme
from .themes import DEFAULT_PRESET, PRESETS
from .permissions import require_cap

User = get_user_model()

ZERO = Decimal(0)


@login_required
def dashboard(request):
    from .widgets import REGISTRY, widgets_for

    widgets, scope, keys = widgets_for(request)
    available = [{**w, "on": w["key"] in keys} for w in REGISTRY.values() if not w["cap"] or w["cap"] in scope.caps or request.user.is_superuser]
    return render(request, "core/dashboard.html", {"widgets": widgets, "scope": scope, "available": available, "keys": keys})


@login_required
@require_POST
def dashboard_customize(request):
    """Save the user's widget selection and order (or reset to role defaults)."""
    from community.models import Profile

    prof, _ = Profile.objects.get_or_create(user=request.user)
    if request.POST.get("reset"):
        prof.dashboard = []
    else:
        ordered = [k for k in request.POST.get("order", "").split(",") if k]
        chosen = set(request.POST.getlist("widget"))
        prof.dashboard = [k for k in ordered if k in chosen] + [k for k in chosen if k not in ordered]
    prof.save()
    messages.success(request, "Dashboard updated.")
    return redirect("dashboard")


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


# ---- appearance / themes ---------------------------------------------------------
@login_required
@require_cap("manage_settings")
def appearance(request):
    return render(request, "core/appearance.html", {"presets": PRESETS, "themes": Theme.objects.all(), "active": Theme.active(), "import_form": ThemeImportForm()})


@login_required
@require_cap("manage_settings")
@require_POST
def theme_from_preset(request, key):
    preset = PRESETS.get(key)
    if not preset:
        messages.error(request, "Unknown preset.")
        return redirect("appearance")
    name = preset["name"]
    i = 2
    while Theme.objects.filter(name=name).exists():
        name = f"{preset['name']} {i}"
        i += 1
    theme = Theme.objects.create(name=name, description=preset["description"], based_on=key, variables=dict(preset["vars"]), dark_variables=dict(preset.get("dark", {})), is_active=request.POST.get("activate") == "1")
    messages.success(request, f"Theme “{theme.name}” created{' and applied' if theme.is_active else ''}.")
    return redirect("theme_edit", pk=theme.pk) if request.POST.get("edit") else redirect("appearance")


@login_required
@require_cap("manage_settings")
@require_POST
def theme_activate(request, pk):
    theme = get_object_or_404(Theme, pk=pk)
    theme.is_active = True
    theme.save()
    messages.success(request, f"“{theme.name}” is now the active look.")
    return redirect("appearance")


@login_required
@require_cap("manage_settings")
@require_POST
def theme_reset(request):
    Theme.objects.update(is_active=False)
    messages.success(request, "Back to the built-in default look.")
    return redirect("appearance")


@login_required
@require_cap("manage_settings")
def theme_edit(request, pk):
    theme = get_object_or_404(Theme, pk=pk)
    form = ThemeForm(request.POST or None, instance=theme)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Theme saved.")
        return redirect("theme_edit", pk=pk)
    return render(request, "core/theme_form.html", {"form": form, "theme": theme, "preview_css": theme.css()})


@login_required
@require_cap("manage_settings")
@require_POST
def theme_delete(request, pk):
    theme = get_object_or_404(Theme, pk=pk)
    theme.delete()
    messages.success(request, "Theme deleted.")
    return redirect("appearance")


@login_required
@require_cap("manage_settings")
def theme_export(request, pk):
    import json

    from django.http import JsonResponse

    theme = get_object_or_404(Theme, pk=pk)
    resp = JsonResponse(theme.export(), json_dumps_params={"indent": 2})
    resp["Content-Disposition"] = f'attachment; filename="theme-{theme.name.lower().replace(" ", "-")}.json"'
    return resp


@login_required
@require_cap("manage_settings")
@require_POST
def theme_import(request):
    import json

    form = ThemeImportForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Choose a JSON file.")
        return redirect("appearance")
    try:
        data = json.loads(form.cleaned_data["file"].read().decode("utf-8-sig"))
        name = str(data.get("name") or "Imported theme")[:80]
        variables = {k: str(v)[:200] for k, v in (data.get("variables") or {}).items() if isinstance(k, str)}
        dark = {k: str(v)[:200] for k, v in (data.get("dark_variables") or {}).items() if isinstance(k, str)}
        theme, created = Theme.objects.update_or_create(
            name=name, defaults={"description": str(data.get("description") or "")[:200], "based_on": str(data.get("based_on") or "")[:30], "variables": variables, "dark_variables": dark, "default_mode": "light" if data.get("default_mode") == "light" else "dark", "custom_css": str(data.get("custom_css") or "")[:20000]}
        )
        messages.success(request, f"Theme “{theme.name}” {'imported' if created else 'updated'}.")
    except (ValueError, AttributeError) as e:
        messages.error(request, f"Could not read theme file: {e}")
    return redirect("appearance")


# ---- form builder ---------------------------------------------------------------
FORM_FIELDS = {
    "proposal": ["title", "region", "client", "contact", "service_type", "owner", "status", "project_status", "due_date", "probability", "currency", "location", "summary", "services", "closing_words", "signatory", "tags", "notes", "manual_value", "submitted_at", "decided_at", "include_fee_breakdown", "include_schedule", "include_terms", "include_capabilities"],
    "proposal_create": ["title", "region", "client", "contact", "service_type", "owner", "due_date", "currency", "location", "summary", "template", "tags", "assign_number"],
    "client": ["name", "sector", "address", "website", "notes"],
    "contact": ["name", "title", "email", "phone", "is_primary", "notes"],
    "employee": ["name", "initials", "role", "rate", "cost_rate", "email", "external_id", "is_active"],
    "project_sheet": ["name", "kind", "client", "client_name", "location", "role", "year_completed", "construction_value", "fee_value", "duration_months", "key_dimensions", "services", "description", "challenges", "contribution", "value_added", "highlights", "source_path", "reference_contact", "tags", "is_featured", "is_published"],
    "task": ["name", "phase", "start", "end", "is_milestone", "percent_complete", "predecessor"],
    "fee_item": ["code", "name", "kind", "task", "notes"],
}


@login_required
@require_cap("manage_forms")
def form_builder(request, form_key="proposal"):
    if form_key not in dict(FORM_KEYS):
        form_key = "proposal"
    rules = {r.field_name: r for r in FieldRule.objects.filter(form_key=form_key)}
    rows = []
    for i, name in enumerate(FORM_FIELDS.get(form_key, [])):
        r = rules.get(name)
        rows.append({"name": name, "rule": r, "visible": r.visible if r else True, "required": (r.required if r and r.required is not None else None), "label": r.label if r else "", "help": r.help_text if r else "", "order": r.order if r else 100 + i})
    rows.sort(key=lambda x: x["order"])
    return render(request, "core/form_builder.html", {"form_keys": FORM_KEYS, "form_key": form_key, "rows": rows, "custom": CustomField.objects.filter(form_key=form_key), "cf_form": CustomFieldForm(initial={"form_key": form_key})})


@login_required
@require_cap("manage_forms")
@require_POST
def form_builder_save(request, form_key):
    """Save the whole table of rules in one go."""
    names = FORM_FIELDS.get(form_key, [])
    for i, name in enumerate(names):
        visible = request.POST.get(f"visible_{name}") == "on"
        req = request.POST.get(f"required_{name}", "")
        label = request.POST.get(f"label_{name}", "").strip()
        help_text = request.POST.get(f"help_{name}", "").strip()
        try:
            order = int(request.POST.get(f"order_{name}", 100 + i))
        except ValueError:
            order = 100 + i
        FieldRule.objects.update_or_create(form_key=form_key, field_name=name, defaults={"visible": visible, "required": None if req == "" else req == "true", "label": label, "help_text": help_text, "order": order})
    messages.success(request, "Form layout saved. It applies the next time the form opens.")
    return redirect("form_builder", form_key=form_key)


@login_required
@require_cap("manage_forms")
@require_POST
def custom_field_save(request):
    pk = request.POST.get("pk")
    inst = CustomField.objects.filter(pk=pk).first() if pk else None
    form = CustomFieldForm(request.POST, instance=inst)
    if form.is_valid():
        cf = form.save()
        messages.success(request, f"Custom field “{cf.label}” saved.")
        return redirect("form_builder", form_key=cf.form_key)
    messages.error(request, form.errors.as_text())
    return redirect("form_builder", form_key=request.POST.get("form_key", "proposal"))


@login_required
@require_cap("manage_forms")
@require_POST
def custom_field_delete(request, pk):
    cf = get_object_or_404(CustomField, pk=pk)
    key = cf.form_key
    cf.delete()
    return redirect("form_builder", form_key=key)


@login_required
@require_cap("manage_forms")
@require_POST
def form_builder_reset(request, form_key):
    FieldRule.objects.filter(form_key=form_key).delete()
    messages.success(request, "Layout reset to defaults.")
    return redirect("form_builder", form_key=form_key)


# ---- landing / mode ---------------------------------------------------------------
def landing(request):
    if request.user.is_authenticated:
        return dashboard(request)
    from .models import Office

    return render(request, "core/landing.html", {"offices": Office.objects.filter(is_active=True)})


@login_required
@require_POST
def view_as(request):
    """Admins preview the app as a role; the panel keeps a way back."""
    real = __import__("core.models", fromlist=["user_capabilities"]).user_capabilities(request.user)
    if "manage_users" not in real and not request.user.is_superuser:
        messages.error(request, "Only administrators can preview as a role.")
        return redirect(request.POST.get("next") or "/")
    role = request.POST.get("role")
    if role:
        request.session["view_as_role"] = int(role)
        messages.info(request, "Previewing as a role. Open the configuration panel to go back to your own access.")
    else:
        request.session.pop("view_as_role", None)
    return redirect(request.POST.get("next") or "/")


# ---- offices & news sources ------------------------------------------------------
@login_required
@require_cap("manage_settings")
def offices(request):
    from .forms import OfficeForm
    from .models import NewsSource, Office

    if request.method == "POST":
        inst = Office.objects.filter(pk=request.POST.get("pk")).first() if request.POST.get("pk") else None
        form = OfficeForm(request.POST, instance=inst)
        if form.is_valid():
            form.save()
            messages.success(request, "Office saved.")
            return redirect("offices")
        messages.error(request, form.errors.as_text())
    return render(request, "core/offices.html", {"offices": Office.objects.all(), "form": OfficeForm(), "sources": NewsSource.objects.all()})


@login_required
@require_cap("manage_settings")
@require_POST
def office_delete(request, pk):
    from .models import Office

    o = get_object_or_404(Office, pk=pk)
    if o.people.exists() or o.proposals.exists() or o.employees.exists():
        o.is_active = False
        o.save()
    else:
        o.delete()
    return redirect("offices")


@login_required
@require_cap("manage_settings")
@require_POST
def news_source_save(request):
    from .models import NewsSource

    name, url = request.POST.get("name", "").strip(), request.POST.get("url", "").strip()
    if request.POST.get("delete"):
        NewsSource.objects.filter(pk=request.POST["delete"]).delete()
    elif name and url:
        NewsSource.objects.get_or_create(url=url, defaults={"name": name})
    if request.POST.get("fetch"):
        from .news import fetch_all

        res = fetch_all()
        messages.info(request, f"Fetched {res['items']} items from {res['ok']} feed(s); {res['failed']} failed.")
    return redirect("offices")

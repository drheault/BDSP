from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import Region
from core.permissions import has_cap, require_cap
from crm.models import Contact

from .forms import (
    EmployeeForm,
    FeeItemForm,
    FeeLineForm,
    FeeSettingsForm,
    ProjectRecordForm,
    ProposalCreateForm,
    ProposalForm,
    ProposalSectionForm,
    ServiceForm,
    StaffRoleForm,
    TemplateForm,
    TemplateSectionForm,
)
from .models import (
    Employee,
    FeeItem,
    FeeLine,
    PhaseChange,
    ProjectRecord,
    Proposal,
    ProposalSection,
    ProposalTemplate,
    Service,
    StaffRole,
    TemplateSection,
)
from django.core.exceptions import ValidationError
from .suggestions import suggest_for_item
from .utils import move_item

User = get_user_model()


# =============================================================================
# Proposals: list / board / CRUD
# =============================================================================
def _filtered_proposals(request):
    qs = Proposal.objects.select_related("client", "owner")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    owner = request.GET.get("owner", "")
    service = request.GET.get("service", "")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(number__icontains=q) | Q(client__name__icontains=q))
    if status == "open":
        qs = qs.filter(status__in=Proposal.OPEN_STATUSES)
    elif status:
        qs = qs.filter(status=status)
    if owner:
        qs = qs.filter(owner_id=owner)
    if service:
        qs = qs.filter(service_type=service)
    return qs


@login_required
def proposal_list(request):
    proposals = _filtered_proposals(request)
    ctx = {
        "proposals": proposals,
        "statuses": Proposal.Status.choices,
        "owners": User.objects.filter(is_active=True).order_by("first_name", "username"),
        "service_types": Proposal._meta.get_field("service_type").choices,
        "filters": request.GET,
    }
    if request.htmx:
        return render(request, "proposals/_proposal_rows.html", ctx)
    return render(request, "proposals/proposal_list.html", ctx)


@login_required
def proposal_board(request):
    proposals = _filtered_proposals(request)
    columns = []
    for key, label in Proposal.Status.choices:
        items = [p for p in proposals if p.status == key]
        columns.append({"key": key, "label": label, "items": items, "value": sum((p.fee_total for p in items), 0)})
    return render(request, "proposals/proposal_board.html", {"columns": columns})


@login_required
@require_cap("edit_proposals")
def proposal_create(request):
    form = ProposalCreateForm(request.POST or None, initial={"owner": request.user.pk})
    if request.method == "POST" and form.is_valid():
        proposal = form.save(commit=False)
        proposal.status = Proposal.Status.LEAD
        proposal.save()
        form.save_m2m()
        template = form.cleaned_data.get("template")
        if template:
            proposal.apply_template(template)
        if form.cleaned_data.get("assign_number") and proposal.region_id and has_cap(request.user, "approve_won"):
            proposal.assign_project_number(user=request.user)
            messages.success(request, f"Proposal {proposal.number} created with project number {proposal.project_number}.")
        else:
            messages.success(request, f"Proposal {proposal.number} created.")
        return redirect("proposal_detail", pk=proposal.pk)
    return render(request, "proposals/proposal_create.html", {"form": form})


def _proposal_ctx(proposal, tab):
    return {"proposal": proposal, "tab": tab}


@login_required
def proposal_detail(request, pk):
    proposal = get_object_or_404(Proposal.objects.select_related("client", "contact", "owner"), pk=pk)
    if request.method == "POST":
        form = ProposalForm(request.POST, instance=proposal)
        if form.is_valid():
            form.save()
            messages.success(request, "Proposal saved.")
            return redirect("proposal_detail", pk=pk)
    else:
        form = ProposalForm(instance=proposal)
    ctx = _proposal_ctx(proposal, "overview")
    ctx["form"] = form
    ctx["regions"] = Region.objects.filter(is_active=True)
    ctx["next_sequence"] = Proposal.next_sequence()
    ctx["phase_changes"] = proposal.phase_changes.select_related("by")[:8]
    ctx["phases"] = Proposal.Phase.choices
    return render(request, "proposals/proposal_detail.html", ctx)


@login_required
@require_cap("approve_won")
@require_POST
def assign_number(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    region = Region.objects.filter(pk=request.POST.get("region")).first() or proposal.region
    try:
        proposal.assign_project_number(region=region, user=request.user)
        messages.success(request, f"Project number {proposal.project_number} assigned.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("proposal_detail", pk=pk)


@login_required
@require_cap("change_phase")
@require_POST
def change_phase(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    try:
        proposal.advance_phase(request.POST.get("phase", ""), user=request.user, note=request.POST.get("note", ""))
        messages.success(request, f"Project is now in phase {proposal.phase} — {proposal.project_number}.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("proposal_detail", pk=pk)


# =============================================================================
# Project records (execution phase: site reports, photos, monitoring, progress)
# =============================================================================
@login_required
def proposal_records(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    ctx = _proposal_ctx(proposal, "records")
    ctx["records"] = proposal.records.select_related("created_by")
    ctx["form"] = ProjectRecordForm(initial={"date": __import__("django.utils.timezone", fromlist=["localdate"]).localdate()})
    kinds = {}
    for r in ctx["records"]:
        kinds.setdefault(r.get_kind_display(), 0)
        kinds[r.get_kind_display()] += 1
    ctx["kind_counts"] = kinds
    rates = [r for r in ctx["records"] if r.kind == "progress" and r.value is not None]
    ctx["avg_rate"] = (sum(r.value for r in rates) / len(rates)) if rates else None
    ctx["rate_unit"] = rates[0].unit if rates else ""
    return render(request, "proposals/proposal_records.html", ctx)


@login_required
@require_cap("edit_proposals")
@require_POST
def record_add(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    form = ProjectRecordForm(request.POST)
    if form.is_valid():
        rec = form.save(commit=False)
        rec.proposal = proposal
        rec.created_by = request.user
        rec.save()
        messages.success(request, "Record added.")
    else:
        messages.error(request, f"Could not add record: {form.errors.as_text()}")
    return redirect("proposal_records", pk=pk)


@login_required
@require_cap("edit_proposals")
@require_POST
def record_delete(request, pk):
    rec = get_object_or_404(ProjectRecord, pk=pk)
    rec.delete()
    return redirect("proposal_records", pk=rec.proposal_id)


@login_required
def contact_options(request):
    """htmx: options for the contact <select>, filtered by the chosen client."""
    client_id = request.GET.get("client")
    contacts = Contact.objects.filter(client_id=client_id) if client_id else Contact.objects.none()
    return render(request, "proposals/_contact_options.html", {"contacts": contacts})


@login_required
@require_POST
def proposal_status(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    status = request.POST.get("status")
    if status in dict(Proposal.Status.choices):
        if status in ("won", "lost", "no_bid") and not has_cap(request.user, "approve_won"):
            messages.error(request, "Only users with the 'approve won' capability can decide a proposal.")
        else:
            try:
                proposal.status = status
                proposal.full_clean(exclude=["number", "project_number"])
                proposal.save()
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
                proposal.refresh_from_db()
    if request.htmx:
        target = request.POST.get("render", "badge")
        if target == "row":
            return render(request, "proposals/_proposal_row.html", {"p": proposal})
        if target == "header":
            return render(request, "proposals/_status_control.html", {"proposal": proposal})
        return render(request, "proposals/_status_badge.html", {"proposal": proposal})
    return redirect("proposal_detail", pk=pk)


@login_required
@require_cap("edit_proposals")
@require_POST
def proposal_delete(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    proposal.delete()
    messages.success(request, f"Proposal {proposal.number} deleted.")
    return redirect("proposal_list")


@login_required
@require_cap("edit_proposals")
@require_POST
def proposal_duplicate(request, pk):
    src = get_object_or_404(Proposal, pk=pk)
    new = Proposal.objects.create(
        title=f"{src.title} (copy)",
        client=src.client,
        contact=src.contact,
        service_type=src.service_type,
        owner=src.owner,
        template=src.template,
        location=src.location,
        summary=src.summary,
        probability=src.probability,
        currency=src.currency,
        contingency_percent=src.contingency_percent,
    )
    new.services.set(src.services.all())
    for s in src.sections.all():
        ProposalSection.objects.create(proposal=new, order=s.order, title=s.title, body=s.body)
    task_map = {}
    for t in src.tasks.all():
        old = t.pk
        t.pk = None
        t.proposal = new
        t.predecessor = None
        t.save()
        task_map[old] = t
    for it in src.items.prefetch_related("lines"):
        lines = list(it.lines.all())
        it.pk = None
        it.proposal = new
        it.task = task_map.get(it.task_id)
        it.save()
        for l in lines:
            l.pk = None
            l.item = it
            l.save()
    messages.success(request, f"Duplicated as {new.number}.")
    return redirect("proposal_detail", pk=new.pk)


# =============================================================================
# Proposal content sections (htmx)
# =============================================================================
@login_required
def proposal_sections(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    ctx = _proposal_ctx(proposal, "content")
    ctx["templates"] = ProposalTemplate.objects.all()
    ctx["placeholders"] = proposal.placeholder_context()
    return render(request, "proposals/proposal_sections.html", ctx)


@login_required
@require_cap("edit_proposals")
@require_POST
def section_add(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    order = proposal.sections.count()
    section = ProposalSection.objects.create(
        proposal=proposal, order=order, title=request.POST.get("title") or "New section"
    )
    form = ProposalSectionForm(instance=section)
    return render(request, "proposals/_section_edit.html", {"section": section, "form": form})


@login_required
@require_cap("edit_proposals")
def section_edit(request, pk):
    section = get_object_or_404(ProposalSection, pk=pk)
    if request.method == "POST":
        form = ProposalSectionForm(request.POST, instance=section)
        if form.is_valid():
            form.save()
            return render(request, "proposals/_section_card.html", {"section": section})
    else:
        form = ProposalSectionForm(instance=section)
    return render(request, "proposals/_section_edit.html", {"section": section, "form": form})


@login_required
def section_card(request, pk):
    section = get_object_or_404(ProposalSection, pk=pk)
    return render(request, "proposals/_section_card.html", {"section": section})


@login_required
@require_cap("edit_proposals")
@require_POST
def section_delete(request, pk):
    section = get_object_or_404(ProposalSection, pk=pk)
    section.delete()
    return HttpResponse("")


@login_required
@require_cap("edit_proposals")
@require_POST
def section_move(request, pk, direction):
    section = get_object_or_404(ProposalSection, pk=pk)
    move_item(section, direction, section.proposal.sections.all())
    return render(request, "proposals/_section_list.html", {"proposal": section.proposal})


@login_required
@require_cap("edit_proposals")
@require_POST
def apply_template(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    template = get_object_or_404(ProposalTemplate, pk=request.POST.get("template"))
    if request.POST.get("replace"):
        proposal.sections.all().delete()
    proposal.apply_template(template)
    messages.success(request, f"Applied template “{template.name}”.")
    return redirect("proposal_sections", pk=pk)


# =============================================================================
# Fee estimate: work items × granular lines (htmx)
# =============================================================================
def _fee_ctx(proposal, item_form=None):
    return {
        "proposal": proposal,
        "items": proposal.items.select_related("task").prefetch_related("lines__employee", "lines__role"),
        "item_form": item_form or FeeItemForm(proposal=proposal),
        "line_form": FeeLineForm(),
        "by_kind": proposal.rollup_by_kind(),
        "by_person": proposal.rollup_by_person(),
    }


@login_required
def proposal_fee(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    if request.method == "POST":
        fee_form = FeeSettingsForm(request.POST, instance=proposal)
        if fee_form.is_valid():
            fee_form.save()
            messages.success(request, "Fee settings saved.")
            return redirect("proposal_fee", pk=pk)
    else:
        fee_form = FeeSettingsForm(instance=proposal)
    ctx = _proposal_ctx(proposal, "fee")
    ctx.update(_fee_ctx(proposal))
    ctx["fee_form"] = fee_form
    ctx["employees"] = Employee.objects.filter(is_active=True)
    return render(request, "proposals/proposal_fee.html", ctx)


def _fee_panel(request, proposal, item_form=None, status=200):
    return render(request, "proposals/_fee_panel.html", _fee_ctx(proposal, item_form), status=status)


@login_required
def fee_summary(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    return render(request, "proposals/_fee_summary.html", _fee_ctx(proposal))


@login_required
@require_cap("edit_proposals")
@require_POST
def item_add(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    form = FeeItemForm(request.POST, proposal=proposal)
    if form.is_valid():
        item = form.save(commit=False)
        item.proposal = proposal
        item.order = proposal.items.count()
        if not item.code:
            item.code = str(item.order + 1)
        item.save()
        return _fee_panel(request, proposal)
    return _fee_panel(request, proposal, form, 422)


@login_required
@require_cap("edit_proposals")
def item_edit(request, pk):
    item = get_object_or_404(FeeItem, pk=pk)
    if request.method == "POST":
        form = FeeItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return _fee_panel(request, item.proposal)
    else:
        form = FeeItemForm(instance=item)
    return render(request, "proposals/_item_edit.html", {"item": item, "form": form})


@login_required
def item_card(request, pk):
    item = get_object_or_404(FeeItem, pk=pk)
    return render(request, "proposals/_item_card.html", {"item": item, "proposal": item.proposal, "line_form": FeeLineForm()})


@login_required
@require_cap("edit_proposals")
@require_POST
def item_delete(request, pk):
    item = get_object_or_404(FeeItem, pk=pk)
    proposal = item.proposal
    item.delete()
    return _fee_panel(request, proposal)


@login_required
@require_cap("edit_proposals")
@require_POST
def item_move(request, pk, direction):
    item = get_object_or_404(FeeItem, pk=pk)
    move_item(item, direction, item.proposal.items.all())
    return _fee_panel(request, item.proposal)


@login_required
@require_cap("edit_proposals")
@require_POST
def item_duplicate(request, pk):
    item = get_object_or_404(FeeItem, pk=pk)
    lines = list(item.lines.all())
    item.pk = None
    item.name = f"{item.name} (copy)"
    item.order = item.proposal.items.count()
    item.save()
    for l in lines:
        l.pk = None
        l.item = item
        l.save()
    return _fee_panel(request, item.proposal)


@login_required
@require_cap("edit_proposals")
@require_POST
def line_add(request, pk):
    item = get_object_or_404(FeeItem, pk=pk)
    form = FeeLineForm(request.POST)
    if form.is_valid():
        line = form.save(commit=False)
        line.item = item
        line.order = item.lines.count()
        line.save()
        return _fee_panel(request, item.proposal)
    return render(request, "proposals/_item_card.html", {"item": item, "proposal": item.proposal, "line_form": form}, status=422)


@login_required
@require_cap("edit_proposals")
def line_edit(request, pk):
    line = get_object_or_404(FeeLine, pk=pk)
    if request.method == "POST":
        form = FeeLineForm(request.POST, instance=line)
        if form.is_valid():
            form.save()
            return _fee_panel(request, line.item.proposal)
    else:
        form = FeeLineForm(instance=line)
    return render(request, "proposals/_line_edit_row.html", {"line": line, "form": form})


@login_required
def line_row(request, pk):
    line = get_object_or_404(FeeLine, pk=pk)
    return render(request, "proposals/_line_row.html", {"line": line, "proposal": line.item.proposal})


@login_required
@require_cap("edit_proposals")
@require_POST
def line_delete(request, pk):
    line = get_object_or_404(FeeLine, pk=pk)
    proposal = line.item.proposal
    line.delete()
    return _fee_panel(request, proposal)


@login_required
def rate_lookup(request):
    """htmx: default rate (proposal currency) for an employee or role."""
    proposal = get_object_or_404(Proposal, pk=request.GET.get("proposal"))
    line = FeeLine(item=FeeItem(proposal=proposal))
    emp, role = request.GET.get("employee"), request.GET.get("role")
    if emp:
        line.employee = Employee.objects.filter(pk=emp).first()
    elif role:
        line.role = StaffRole.objects.filter(pk=role).first()
    return HttpResponse(f"{line.default_rate():.2f}")


@login_required
def fee_suggest(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    q = request.GET.get("name", "").strip()
    kind = request.GET.get("kind") or None
    data = suggest_for_item(q, exclude_proposal=proposal, kind=kind)
    from core.models import CompanyProfile

    return render(request, "proposals/_suggestions.html", {"proposal": proposal, "q": q, "base": CompanyProfile.get_solo().base_currency, **data})


@login_required
@require_cap("edit_proposals")
@require_POST
def item_apply_suggestion(request, pk):
    """Create a fee item from a past item: copies its labour lines scaled to the suggested hours."""
    proposal = get_object_or_404(Proposal, pk=pk)
    src = get_object_or_404(FeeItem, pk=request.POST.get("source"))
    item = FeeItem.objects.create(proposal=proposal, name=request.POST.get("name") or src.name, kind=src.kind, order=proposal.items.count(), code=str(proposal.items.count() + 1))
    for l in src.lines.all():
        l.pk = None
        l.item = item
        if l.kind == FeeLine.Kind.LABOUR:
            l.unit_cost = 0  # re-price at today's rate for this proposal's currency
        else:
            l.unit_cost = proposal.cur.from_base(src.proposal.cur.to_base(l.unit_cost))
        l.save()
    return _fee_panel(request, proposal)


# =============================================================================
# Export
# =============================================================================
@login_required
def proposal_export(request, pk, fmt):
    from .export import build_docx, build_pdf

    proposal = get_object_or_404(Proposal, pk=pk)
    filename = f"{proposal.number}-{proposal.title[:40].replace(' ', '_')}"
    if fmt == "docx":
        data, ctype, ext = build_docx(proposal), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    else:
        data, ctype, ext = build_pdf(proposal), "application/pdf", "pdf"
    resp = HttpResponse(data, content_type=ctype)
    resp["Content-Disposition"] = f'attachment; filename="{filename}.{ext}"'
    return resp


# =============================================================================
# Preview / print
# =============================================================================
@login_required
def proposal_preview(request, pk):
    proposal = get_object_or_404(Proposal.objects.select_related("client", "contact", "owner"), pk=pk)
    from scheduling.gantt import build_gantt

    ctx = _proposal_ctx(proposal, "preview")
    ctx["gantt"] = build_gantt(proposal.tasks.all())
    ctx["print_mode"] = request.GET.get("print") == "1"
    return render(request, "proposals/proposal_preview.html", ctx)


# =============================================================================
# Templates
# =============================================================================
@login_required
def template_list(request):
    templates = ProposalTemplate.objects.prefetch_related("sections")
    return render(request, "proposals/template_list.html", {"templates": templates})


@login_required
@require_cap("manage_projects_library")
def template_create(request):
    form = TemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        t = form.save()
        messages.success(request, "Template created. Add sections below.")
        return redirect("template_detail", pk=t.pk)
    return render(request, "proposals/template_form.html", {"form": form, "title": "New template"})


@login_required
def template_detail(request, pk):
    template = get_object_or_404(ProposalTemplate, pk=pk)
    form = TemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Template settings saved.")
        return redirect("template_detail", pk=pk)
    return render(request, "proposals/template_detail.html", {"template": template, "form": form})


@login_required
@require_cap("manage_projects_library")
@require_POST
def template_delete(request, pk):
    template = get_object_or_404(ProposalTemplate, pk=pk)
    template.delete()
    messages.success(request, "Template deleted.")
    return redirect("template_list")


@login_required
@require_cap("manage_projects_library")
@require_POST
def template_duplicate(request, pk):
    src = get_object_or_404(ProposalTemplate, pk=pk)
    new = ProposalTemplate.objects.create(
        name=f"{src.name} (copy)", description=src.description, service_type=src.service_type, is_default=False
    )
    for s in src.sections.all():
        TemplateSection.objects.create(template=new, order=s.order, title=s.title, body=s.body)
    return redirect("template_detail", pk=new.pk)


@login_required
@require_cap("manage_projects_library")
@require_POST
def tsection_add(request, pk):
    template = get_object_or_404(ProposalTemplate, pk=pk)
    section = TemplateSection.objects.create(
        template=template, order=template.sections.count(), title=request.POST.get("title") or "New section"
    )
    return render(request, "proposals/_tsection_edit.html", {"section": section, "form": TemplateSectionForm(instance=section)})


@login_required
@require_cap("manage_projects_library")
def tsection_edit(request, pk):
    section = get_object_or_404(TemplateSection, pk=pk)
    if request.method == "POST":
        form = TemplateSectionForm(request.POST, instance=section)
        if form.is_valid():
            form.save()
            return render(request, "proposals/_tsection_card.html", {"section": section})
    else:
        form = TemplateSectionForm(instance=section)
    return render(request, "proposals/_tsection_edit.html", {"section": section, "form": form})


@login_required
def tsection_card(request, pk):
    section = get_object_or_404(TemplateSection, pk=pk)
    return render(request, "proposals/_tsection_card.html", {"section": section})


@login_required
@require_cap("manage_projects_library")
@require_POST
def tsection_delete(request, pk):
    get_object_or_404(TemplateSection, pk=pk).delete()
    return HttpResponse("")


@login_required
@require_cap("manage_projects_library")
@require_POST
def tsection_move(request, pk, direction):
    section = get_object_or_404(TemplateSection, pk=pk)
    move_item(section, direction, section.template.sections.all())
    return render(request, "proposals/_tsection_list.html", {"template": section.template})


# =============================================================================
# Library: services & staff roles (htmx inline editors)
# =============================================================================
@login_required
def library(request):
    return render(
        request,
        "proposals/library.html",
        {
            "services": Service.objects.all(),
            "roles": StaffRole.objects.all(),
            "employees": Employee.objects.select_related("role"),
            "service_form": ServiceForm(),
            "role_form": StaffRoleForm(),
            "employee_form": EmployeeForm(),
        },
    )


def _service_list(request, form=None, status=200):
    return render(request, "proposals/_service_list.html", {"services": Service.objects.all(), "service_form": form or ServiceForm()}, status=status)


def _role_list(request, form=None, status=200):
    return render(request, "proposals/_role_list.html", {"roles": StaffRole.objects.all(), "role_form": form or StaffRoleForm()}, status=status)


@login_required
@require_cap("manage_projects_library")
@require_POST
def service_add(request):
    form = ServiceForm(request.POST)
    if form.is_valid():
        s = form.save(commit=False)
        s.sort_order = Service.objects.count()
        s.save()
        return _service_list(request)
    return _service_list(request, form, 422)


@login_required
@require_cap("manage_projects_library")
def service_edit(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == "POST":
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            return _service_list(request)
    else:
        form = ServiceForm(instance=service)
    return render(request, "proposals/_service_edit.html", {"service": service, "form": form})


@login_required
@require_cap("manage_projects_library")
@require_POST
def service_delete(request, pk):
    get_object_or_404(Service, pk=pk).delete()
    return _service_list(request)


@login_required
@require_cap("edit_rates")
@require_POST
def role_add(request):
    form = StaffRoleForm(request.POST)
    if form.is_valid():
        r = form.save(commit=False)
        r.sort_order = StaffRole.objects.count()
        r.save()
        return _role_list(request)
    return _role_list(request, form, 422)


@login_required
@require_cap("edit_rates")
def role_edit(request, pk):
    role = get_object_or_404(StaffRole, pk=pk)
    if request.method == "POST":
        form = StaffRoleForm(request.POST, instance=role)
        if form.is_valid():
            form.save()
            return _role_list(request)
    else:
        form = StaffRoleForm(instance=role)
    return render(request, "proposals/_role_edit.html", {"role": role, "form": form})


@login_required
@require_cap("edit_rates")
@require_POST
def role_delete(request, pk):
    role = get_object_or_404(StaffRole, pk=pk)
    if role.fee_lines.exists() or role.employees.exists():
        role.is_active = False
        role.save()
    else:
        role.delete()
    return _role_list(request)


def _employee_list(request, form=None, status=200):
    return render(request, "proposals/_employee_list.html", {"employees": Employee.objects.select_related("role"), "employee_form": form or EmployeeForm()}, status=status)


@login_required
@require_cap("edit_rates")
@require_POST
def employee_add(request):
    form = EmployeeForm(request.POST)
    if form.is_valid():
        form.save()
        return _employee_list(request)
    return _employee_list(request, form, 422)


@login_required
@require_cap("edit_rates")
def employee_edit(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=emp)
        if form.is_valid():
            form.save()
            return _employee_list(request)
    else:
        form = EmployeeForm(instance=emp)
    return render(request, "proposals/_employee_edit.html", {"employee": emp, "form": form})


@login_required
@require_cap("edit_rates")
@require_POST
def employee_delete(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    if emp.fee_lines.exists() or emp.actuals.exists():
        emp.is_active = False
        emp.save()
    else:
        emp.delete()
    return _employee_list(request)

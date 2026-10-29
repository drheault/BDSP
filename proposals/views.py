from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from crm.models import Contact

from .forms import (
    FeeSettingsForm,
    ProposalCreateForm,
    ProposalForm,
    ProposalSectionForm,
    ServiceForm,
    StaffingForm,
    StaffRoleForm,
    TemplateForm,
    TemplateSectionForm,
)
from .models import (
    Proposal,
    ProposalSection,
    ProposalStaffing,
    ProposalTemplate,
    Service,
    StaffRole,
    TemplateSection,
)
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
            for s in template.sections.none():  # placeholder for future scope copy
                pass
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
    return render(request, "proposals/proposal_detail.html", ctx)


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
        proposal.status = status
        proposal.save()
    if request.htmx:
        target = request.POST.get("render", "badge")
        if target == "row":
            return render(request, "proposals/_proposal_row.html", {"p": proposal})
        if target == "header":
            return render(request, "proposals/_status_control.html", {"proposal": proposal})
        return render(request, "proposals/_status_badge.html", {"proposal": proposal})
    return redirect("proposal_detail", pk=pk)


@login_required
@require_POST
def proposal_delete(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    proposal.delete()
    messages.success(request, f"Proposal {proposal.number} deleted.")
    return redirect("proposal_list")


@login_required
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
        expenses=src.expenses,
        markup_percent=src.markup_percent,
    )
    new.services.set(src.services.all())
    for s in src.sections.all():
        ProposalSection.objects.create(proposal=new, order=s.order, title=s.title, body=s.body)
    for s in src.staffing.all():
        ProposalStaffing.objects.create(proposal=new, role=s.role, task=s.task, hours=s.hours, rate=s.rate, order=s.order)
    for t in src.tasks.all():
        t.pk = None
        t.proposal = new
        t.predecessor = None
        t.save()
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
@require_POST
def section_delete(request, pk):
    section = get_object_or_404(ProposalSection, pk=pk)
    section.delete()
    return HttpResponse("")


@login_required
@require_POST
def section_move(request, pk, direction):
    section = get_object_or_404(ProposalSection, pk=pk)
    move_item(section, direction, section.proposal.sections.all())
    return render(request, "proposals/_section_list.html", {"proposal": section.proposal})


@login_required
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
# Fee estimate (htmx)
# =============================================================================
@login_required
def proposal_fee(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    if request.method == "POST":
        fee_form = FeeSettingsForm(request.POST, instance=proposal)
        if fee_form.is_valid():
            fee_form.save()
            if request.htmx:
                return render(request, "proposals/_fee_summary.html", {"proposal": proposal})
            return redirect("proposal_fee", pk=pk)
    else:
        fee_form = FeeSettingsForm(instance=proposal)
    ctx = _proposal_ctx(proposal, "fee")
    ctx.update({"fee_form": fee_form, "staffing_form": StaffingForm(), "roles": StaffRole.objects.filter(is_active=True)})
    return render(request, "proposals/proposal_fee.html", ctx)


@login_required
@require_POST
def staffing_add(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    form = StaffingForm(request.POST)
    if form.is_valid():
        line = form.save(commit=False)
        line.proposal = proposal
        line.order = proposal.staffing.count()
        line.save()
        return render(request, "proposals/_staffing_table.html", {"proposal": proposal, "staffing_form": StaffingForm()})
    return render(request, "proposals/_staffing_table.html", {"proposal": proposal, "staffing_form": form}, status=422)


@login_required
def staffing_edit(request, pk):
    line = get_object_or_404(ProposalStaffing, pk=pk)
    if request.method == "POST":
        form = StaffingForm(request.POST, instance=line)
        if form.is_valid():
            form.save()
            return render(request, "proposals/_staffing_table.html", {"proposal": line.proposal, "staffing_form": StaffingForm()})
    else:
        form = StaffingForm(instance=line)
    return render(request, "proposals/_staffing_edit_row.html", {"line": line, "form": form})


@login_required
def staffing_row(request, pk):
    line = get_object_or_404(ProposalStaffing, pk=pk)
    return render(request, "proposals/_staffing_row.html", {"line": line})


@login_required
@require_POST
def staffing_delete(request, pk):
    line = get_object_or_404(ProposalStaffing, pk=pk)
    proposal = line.proposal
    line.delete()
    return render(request, "proposals/_staffing_table.html", {"proposal": proposal, "staffing_form": StaffingForm()})


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
@require_POST
def template_delete(request, pk):
    template = get_object_or_404(ProposalTemplate, pk=pk)
    template.delete()
    messages.success(request, "Template deleted.")
    return redirect("template_list")


@login_required
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
@require_POST
def tsection_add(request, pk):
    template = get_object_or_404(ProposalTemplate, pk=pk)
    section = TemplateSection.objects.create(
        template=template, order=template.sections.count(), title=request.POST.get("title") or "New section"
    )
    return render(request, "proposals/_tsection_edit.html", {"section": section, "form": TemplateSectionForm(instance=section)})


@login_required
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
@require_POST
def tsection_delete(request, pk):
    get_object_or_404(TemplateSection, pk=pk).delete()
    return HttpResponse("")


@login_required
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
            "service_form": ServiceForm(),
            "role_form": StaffRoleForm(),
        },
    )


def _service_list(request, form=None, status=200):
    return render(request, "proposals/_service_list.html", {"services": Service.objects.all(), "service_form": form or ServiceForm()}, status=status)


def _role_list(request, form=None, status=200):
    return render(request, "proposals/_role_list.html", {"roles": StaffRole.objects.all(), "role_form": form or StaffRoleForm()}, status=status)


@login_required
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
@require_POST
def service_delete(request, pk):
    get_object_or_404(Service, pk=pk).delete()
    return _service_list(request)


@login_required
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
@require_POST
def role_delete(request, pk):
    role = get_object_or_404(StaffRole, pk=pk)
    if role.proposalstaffing_set.exists():
        role.is_active = False
        role.save()
    else:
        role.delete()
    return _role_list(request)

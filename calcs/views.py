from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from community.models import Rating, Reaction
from core.permissions import require_cap
from proposals.models import Proposal

from .engines import REGISTRY
from .forms import SpecToolForm, ToolUploadForm, engine_form
from .models import CalcRun, ProjectParams, Tool, ToolState
from .params import PARAMS, PARAM_KEYS, grouped


def ensure_builtins():
    for key, eng in REGISTRY.items():
        Tool.objects.get_or_create(key=key, defaults={"name": eng.name, "kind": "builtin", "category": eng.category, "summary": eng.summary, "description": eng.description})


@login_required
@require_cap("use_tools")
def tool_list(request):
    ensure_builtins()
    q = request.GET.get("q", "").strip()
    tools = Tool.objects.filter(is_published=True).select_related("author")
    if q:
        tools = tools.filter(name__icontains=q) | tools.filter(summary__icontains=q) | tools.filter(category__icontains=q)
    rows = []
    for t in tools.distinct():
        r = Reaction.score(t)
        rt = Rating.summary(t)
        rows.append({"tool": t, "score": r["score"], "up": r["up"], "down": r["down"], "rating": rt, "rank": r["score"] * 2 + rt["avg"] * rt["n"] + t.runs / 25})
    rows.sort(key=lambda x: (-x["rank"], x["tool"].name))
    cats = {}
    for r in rows:
        cats.setdefault(r["tool"].category, []).append(r)
    return render(request, "calcs/tool_list.html", {"cats": cats, "q": q, "form": ToolUploadForm(), "my_runs": CalcRun.objects.filter(user=request.user)[:8]})


def _initial_inputs(request, tool, eng, proposal=None):
    """Start from the user's last inputs, then overlay project parameters when a project is chosen."""
    state = ToolState.objects.filter(tool=tool, user=request.user).first()
    init = dict(state.inputs) if state else {}
    if proposal is not None:
        params = getattr(proposal, "params", None)
        if params:
            for i in eng.inputs:
                if i.param and params.values.get(i.param) not in (None, ""):
                    init[i.name] = float(params.values[i.param])
    return init


@login_required
@require_cap("use_tools")
def tool_detail(request, key):
    ensure_builtins()
    tool = get_object_or_404(Tool, key=key)
    eng = tool.engine
    form, result = None, None
    proposal = Proposal.objects.filter(pk=request.GET.get("proposal") or request.POST.get("proposal")).first()
    if eng:
        form = engine_form(eng, request.POST or None, initial=_initial_inputs(request, tool, eng, proposal))
        if request.method == "POST" and form.is_valid():
            values = {k: float(v) for k, v in form.cleaned_data.items()}
            result = eng.run(values)
            Tool.objects.filter(pk=tool.pk).update(runs=tool.runs + 1)
            ToolState.objects.update_or_create(tool=tool, user=request.user, defaults={"inputs": values, "proposal": proposal})
            if request.POST.get("save_title"):
                run = CalcRun.objects.create(tool=tool, user=request.user, title=request.POST["save_title"], inputs=values, outputs={"results": result["results"], "checks": result["checks"], "headline": result.get("headline", "")}, proposal=proposal)
                messages.success(request, f"Calculation “{run.title}” saved{' to ' + run.proposal.number if run.proposal else ''}.")
            if request.POST.get("save_params") and proposal is not None:
                pp, _ = ProjectParams.objects.get_or_create(proposal=proposal)
                for i in eng.inputs:
                    if i.param:
                        pp.values[i.param] = values[i.name]
                pp.updated_by = request.user
                pp.save()
                messages.success(request, f"Project parameters on {proposal.number} updated from this tool.")
        elif request.method == "GET" and not request.GET.get("defaults"):
            # live-render the last state so the page opens with results
            try:
                values = {i.name: float(form.initial.get(i.name, i.default)) for i in eng.inputs}
                result = eng.run(values)
            except Exception:
                result = None
    mine = Rating.objects.filter(content_type=ContentType.objects.get_for_model(tool), object_id=tool.pk, user=request.user).first()
    return render(request, "calcs/tool_detail.html", {
        "tool": tool, "engine": eng, "form": form, "result": result, "rating": Rating.summary(tool), "my_rating": mine, "proposal": proposal,
        "linked_params": [(i, dict((p[0], p) for p in PARAMS).get(i.param)) for i in (eng.inputs if eng else []) if i.param],
        "reviews": Rating.objects.filter(content_type=ContentType.objects.get_for_model(tool), object_id=tool.pk).exclude(review="").select_related("user")[:10],
        "proposals": Proposal.objects.filter(status__in=list(Proposal.OPEN_STATUSES) + ["won"]).order_by("-created_at")[:30],
        "runs": CalcRun.objects.filter(tool=tool).select_related("user", "proposal")[:10],
    })


@login_required
@require_POST
def tool_upload(request):
    form = ToolUploadForm(request.POST, request.FILES)
    if form.is_valid():
        tool = form.save(commit=False)
        tool.kind = "upload" if form.cleaned_data.get("file") else "link"
        base = slugify(tool.name)[:50] or "tool"
        key, i = base, 2
        while Tool.objects.filter(key=key).exists():
            key = f"{base}-{i}"
            i += 1
        tool.key = key
        tool.author = request.user
        tool.save()
        form.save_m2m()
        tool.set_tags(form.cleaned_data.get("tags", []))
        messages.success(request, f"“{tool.name}” shared. Colleagues can now rate it and leave feedback.")
        return redirect("tool_detail", key=tool.key)
    messages.error(request, form.errors.as_text())
    return redirect("tool_list")


@login_required
@require_POST
def tool_delete(request, key):
    tool = get_object_or_404(Tool, key=key)
    if tool.kind == "builtin" or (tool.author_id != request.user.pk and not request.user.is_superuser):
        messages.error(request, "Only the author or an administrator can remove an uploaded tool.")
        return redirect("tool_detail", key=key)
    tool.delete()
    messages.success(request, "Tool removed.")
    return redirect("tool_list")


@login_required
def run_detail(request, pk):
    run = get_object_or_404(CalcRun.objects.select_related("tool", "user", "proposal"), pk=pk)
    return render(request, "calcs/run_detail.html", {"run": run})


@login_required
@require_POST
def run_delete(request, pk):
    run = get_object_or_404(CalcRun, pk=pk)
    if run.user_id == request.user.pk or request.user.is_superuser:
        run.delete()
    return redirect("tool_list")


@login_required
@require_cap("use_tools")
@require_POST
def tool_live(request, key):
    """htmx: recalculate as inputs change; also autosaves the user's state."""
    tool = get_object_or_404(Tool, key=key)
    eng = tool.engine
    if not eng:
        return HttpResponse("")
    form = engine_form(eng, request.POST)
    if not form.is_valid():
        return render(request, "calcs/_results.html", {"result": None, "errors": form.errors})
    values = {k: float(v) for k, v in form.cleaned_data.items()}
    try:
        result = eng.run(values)
    except Exception as e:
        return render(request, "calcs/_results.html", {"result": None, "errors": {"calculation": [str(e)]}})
    ToolState.objects.update_or_create(tool=tool, user=request.user, defaults={"inputs": values})
    return render(request, "calcs/_results.html", {"result": result})


@login_required
@require_cap("use_tools")
def project_params(request, pk):
    """Edit the shared parameters of a proposal; tools read and write these."""
    proposal = get_object_or_404(Proposal, pk=pk)
    pp, _ = ProjectParams.objects.get_or_create(proposal=proposal)
    if request.method == "POST":
        vals = dict(pp.values)
        for key in PARAM_KEYS:
            raw = request.POST.get(key, "")
            if raw == "":
                vals.pop(key, None)
            else:
                try:
                    vals[key] = float(raw)
                except ValueError:
                    pass
        pp.values = vals
        pp.updated_by = request.user
        pp.save()
        messages.success(request, "Project parameters saved. Every tool opened with this project now starts from them.")
        return redirect("project_params", pk=pk)
    tools = [t for t in Tool.objects.filter(is_published=True) if t.engine and any(i.param for i in t.engine.inputs)]
    return render(request, "calcs/project_params.html", {"proposal": proposal, "tab": "params", "groups": grouped(pp.values), "pp": pp, "tools": tools})


@login_required
@require_cap("use_tools")
def spec_builder(request, key=None):
    """Create or edit a no-code calculator."""
    import json

    from .spec import EXAMPLE_SPEC

    tool = get_object_or_404(Tool, key=key, kind="spec") if key else None
    if tool and tool.author_id != request.user.pk and not request.user.is_superuser:
        messages.error(request, "Only the author can edit this tool.")
        return redirect("tool_detail", key=key)
    initial = {"spec_text": json.dumps(tool.spec if tool else EXAMPLE_SPEC, indent=2, ensure_ascii=False)}
    form = SpecToolForm(request.POST or None, instance=tool, initial=initial)
    if request.method == "POST" and form.is_valid():
        t = form.save(commit=False)
        t.kind = "spec"
        t.spec = form.cleaned_data["spec_text"]
        if not t.key:
            base = slugify(t.name)[:50] or "tool"
            k, i = base, 2
            while Tool.objects.filter(key=k).exists():
                k = f"{base}-{i}"
                i += 1
            t.key = k
        if not t.author_id:
            t.author = request.user
        t.save()
        form.save_m2m()
        t.set_tags(form.cleaned_data.get("tags", []))
        messages.success(request, f"“{t.name}” is live. Colleagues can use, rate and discuss it.")
        return redirect("tool_detail", key=t.key)
    return render(request, "calcs/spec_builder.html", {"form": form, "tool": tool, "params": PARAMS})

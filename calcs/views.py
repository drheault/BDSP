from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from community.models import Rating, Reaction
from proposals.models import Proposal

from .engines import REGISTRY
from .forms import ToolUploadForm, engine_form
from .models import CalcRun, Tool


def ensure_builtins():
    for key, eng in REGISTRY.items():
        Tool.objects.get_or_create(key=key, defaults={"name": eng.name, "kind": "builtin", "category": eng.category, "summary": eng.summary, "description": eng.description})


@login_required
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


@login_required
def tool_detail(request, key):
    ensure_builtins()
    tool = get_object_or_404(Tool, key=key)
    eng = tool.engine
    form, result = None, None
    if eng:
        form = engine_form(eng, request.POST or None)
        if request.method == "POST" and form.is_valid():
            values = {k: float(v) for k, v in form.cleaned_data.items()}
            result = eng.run(values)
            Tool.objects.filter(pk=tool.pk).update(runs=tool.runs + 1)
            if request.POST.get("save_title"):
                run = CalcRun.objects.create(tool=tool, user=request.user, title=request.POST["save_title"], inputs=values, outputs={"results": result["results"], "checks": result["checks"], "headline": result.get("headline", "")},
                                             proposal=Proposal.objects.filter(pk=request.POST.get("proposal")).first())
                messages.success(request, f"Calculation “{run.title}” saved{' to ' + run.proposal.number if run.proposal else ''}.")
    mine = Rating.objects.filter(content_type=ContentType.objects.get_for_model(tool), object_id=tool.pk, user=request.user).first()
    return render(request, "calcs/tool_detail.html", {
        "tool": tool, "engine": eng, "form": form, "result": result, "rating": Rating.summary(tool), "my_rating": mine,
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

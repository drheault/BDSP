from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.permissions import require_cap

from .models import Tag, TagCategory, TaggedItem, suggest_tags


@login_required
def tag_index(request):
    q = request.GET.get("q", "").strip()
    cats = TagCategory.objects.prefetch_related("tags")
    tags = Tag.objects.select_related("category").annotate(n=Count("items"))
    if q:
        tags = tags.filter(name__icontains=q)
    return render(request, "tags/index.html", {"categories": cats, "tags": tags, "q": q, "total": TaggedItem.objects.count()})


@login_required
def tag_detail(request, slug):
    tag = get_object_or_404(Tag.objects.select_related("category"), slug=slug)
    groups = {}
    for item in tag.items.select_related("content_type"):
        obj = item.content_object
        if obj is None:
            continue
        label = item.content_type.model_class()._meta.verbose_name_plural.title()
        groups.setdefault(label, []).append(obj)
    return render(request, "tags/detail.html", {"tag": tag, "groups": groups})


@login_required
def tag_suggest(request):
    """JSON: autocomplete and auto-tag suggestions for a text."""
    q = request.GET.get("q", "").strip()
    text = request.GET.get("text", "")
    out = {"matches": [], "suggested": []}
    if q:
        out["matches"] = [{"name": t.name, "category": t.category.name} for t in Tag.objects.filter(name__istartswith=q).select_related("category")[:10]]
    if text:
        out["suggested"] = [{"name": t.name, "category": t.category.name} for t in suggest_tags(text)]
    return JsonResponse(out)


@login_required
@require_cap("manage_settings")
@require_POST
def tag_save(request):
    """Create or rename a tag / move it to a category."""
    name = request.POST.get("name", "").strip()
    cat = TagCategory.objects.filter(pk=request.POST.get("category")).first()
    pk = request.POST.get("pk")
    if not name or not cat:
        messages.error(request, "Name and category are required.")
        return redirect("tag_index")
    if pk:
        tag = get_object_or_404(Tag, pk=pk)
        tag.name, tag.category, tag.aliases = name, cat, request.POST.get("aliases", "")
        tag.save()
    else:
        Tag.objects.get_or_create(name=name, category=cat, defaults={"aliases": request.POST.get("aliases", "")})
    messages.success(request, f"Tag “{name}” saved.")
    return redirect("tag_index")


@login_required
@require_cap("manage_settings")
@require_POST
def tag_delete(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    tag.delete()
    messages.success(request, "Tag deleted.")
    return redirect("tag_index")


@login_required
@require_cap("manage_settings")
@require_POST
def category_save(request):
    name = request.POST.get("name", "").strip()
    if name:
        TagCategory.objects.get_or_create(name=name, defaults={"color": request.POST.get("color") or "#6b7f99", "weight": request.POST.get("weight") or 1})
    return redirect("tag_index")

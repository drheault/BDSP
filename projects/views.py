from django.contrib import messages
from django.contrib.auth.decorators import login_required

from core.permissions import require_cap
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ImageCaptionForm, ImageUploadForm, PastProjectForm
from .models import PastProject, ProjectImage


@login_required
def project_list(request):
    q = request.GET.get("q", "").strip()
    kind = request.GET.get("kind", "")
    projects = PastProject.objects.prefetch_related("images").select_related("client")
    if q:
        projects = projects.filter(Q(name__icontains=q) | Q(client_name__icontains=q) | Q(client__name__icontains=q) | Q(location__icontains=q))
    if kind:
        projects = projects.filter(kind=kind)
    ctx = {"projects": projects, "q": q, "kind": kind, "kinds": PastProject.Kind.choices}
    if request.htmx:
        return render(request, "projects/_project_grid.html", ctx)
    return render(request, "projects/project_list.html", ctx)


@login_required
def project_detail(request, pk):
    project = get_object_or_404(PastProject.objects.prefetch_related("images"), pk=pk)
    return render(
        request,
        "projects/project_detail.html",
        {"project": project, "upload_form": ImageUploadForm(), "print_mode": request.GET.get("print") == "1"},
    )


@login_required
@require_cap("manage_projects_library")
def project_create(request):
    form = PastProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save()
        messages.success(request, "Project sheet created. Add images below.")
        return redirect("project_detail", pk=project.pk)
    return render(request, "projects/project_form.html", {"form": form, "title": "New project sheet"})


@login_required
@require_cap("manage_projects_library")
def project_edit(request, pk):
    project = get_object_or_404(PastProject, pk=pk)
    form = PastProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Project sheet updated.")
        return redirect("project_detail", pk=project.pk)
    return render(request, "projects/project_form.html", {"form": form, "title": f"Edit {project}", "project": project})


@login_required
@require_cap("manage_projects_library")
@require_POST
def project_delete(request, pk):
    project = get_object_or_404(PastProject, pk=pk)
    project.delete()
    messages.success(request, "Project sheet deleted.")
    return redirect("project_list")


@login_required
@require_cap("manage_projects_library")
@require_POST
def image_add(request, pk):
    project = get_object_or_404(PastProject, pk=pk)
    form = ImageUploadForm(request.POST, request.FILES)
    if form.is_valid():
        start = project.images.count()
        for i, f in enumerate(request.FILES.getlist("images")):
            ProjectImage.objects.create(project=project, image=f, caption=form.cleaned_data["caption"], order=start + i)
    return render(request, "projects/_image_gallery.html", {"project": project, "upload_form": ImageUploadForm()})


@login_required
@require_cap("manage_projects_library")
@require_POST
def image_caption(request, pk):
    image = get_object_or_404(ProjectImage, pk=pk)
    form = ImageCaptionForm(request.POST, instance=image)
    if form.is_valid():
        form.save()
    return render(request, "projects/_image_card.html", {"img": image})


@login_required
@require_cap("manage_projects_library")
@require_POST
def image_delete(request, pk):
    image = get_object_or_404(ProjectImage, pk=pk)
    image.image.delete(save=False)
    image.delete()
    return HttpResponse("")


@login_required
@require_cap("manage_projects_library")
@require_POST
def image_cover(request, pk):
    """Make this image the cover by moving it to the front."""
    image = get_object_or_404(ProjectImage, pk=pk)
    project = image.project
    others = project.images.exclude(pk=image.pk)
    image.order = 0
    image.save(update_fields=["order"])
    for i, o in enumerate(others, start=1):
        o.order = i
        o.save(update_fields=["order"])
    return render(request, "projects/_image_gallery.html", {"project": project, "upload_form": ImageUploadForm()})

import mimetypes
import posixpath

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.permissions import has_cap, require_cap
from proposals.models import ProjectRecord, Proposal

from .backends import BackendError, backend_for
from .forms import FileRootForm
from .models import FileRoot, SyncLog

RECORD_KIND_BY_FOLDER = [("site", "site_visit"), ("visit", "site_visit"), ("photo", "photos"), ("monitor", "monitoring"), ("instrument", "monitoring"), ("progress", "progress"), ("present", "presentation"), ("calc", "calc"), ("model", "calc")]


def _crumbs(rel):
    parts = [p for p in rel.split("/") if p]
    out, acc = [], ""
    for p in parts:
        acc = posixpath.join(acc, p)
        out.append((p, acc))
    return out


@login_required
def file_home(request):
    roots = FileRoot.objects.filter(is_active=True)
    status = []
    for r in roots:
        try:
            ok = backend_for(r).available()
        except BackendError:
            ok = False
        status.append((r, ok))
    return render(request, "files/home.html", {"roots": status, "form": FileRootForm(), "all_roots": FileRoot.objects.all(), "logs": SyncLog.objects.select_related("root", "proposal", "user")[:10]})


@login_required
def browse(request, root_id, rel=""):
    root = get_object_or_404(FileRoot, pk=root_id, is_active=True)
    try:
        b = backend_for(root)
        entries = b.listdir(rel)
        error = ""
    except BackendError as e:
        entries, error = [], str(e)
    return render(request, "files/browse.html", {"root": root, "rel": rel.strip("/"), "entries": entries, "crumbs": _crumbs(rel), "error": error, "parent": posixpath.dirname(rel.strip("/"))})


@login_required
def download(request, root_id, rel):
    root = get_object_or_404(FileRoot, pk=root_id, is_active=True)
    try:
        f, name, size = backend_for(root).open(rel)
    except BackendError as e:
        raise Http404(str(e))
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    resp = FileResponse(f, content_type=ctype, as_attachment=request.GET.get("inline") != "1", filename=name)
    return resp


@login_required
@require_POST
def upload(request, root_id):
    root = get_object_or_404(FileRoot, pk=root_id, is_active=True)
    rel = request.POST.get("rel", "")
    if not root.allow_upload:
        messages.error(request, "Uploads are disabled for this root.")
        return redirect("file_browse", root_id=root.pk, rel=rel)
    b = backend_for(root)
    n = 0
    try:
        for f in request.FILES.getlist("files"):
            b.save(rel, f.name, f)
            n += 1
        if request.POST.get("folder"):
            b.mkdir(rel, request.POST["folder"])
            messages.success(request, f"Folder “{request.POST['folder']}” created.")
    except BackendError as e:
        messages.error(request, str(e))
    if n:
        messages.success(request, f"Uploaded {n} file{'s' if n != 1 else ''}.")
    return redirect("file_browse", root_id=root.pk, rel=rel)


def _project_rel(root, proposal):
    tpl = root.project_folder_template or "{project_number}"
    return tpl.format(project_number=proposal.project_number or proposal.number, phase=proposal.phase, phase_name=proposal.phase_name, region=proposal.region.code if proposal.region_id else "", seq=proposal.sequence or "").strip("/")


@login_required
def project_folder(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    root = FileRoot.objects.filter(is_active=True).first()
    if not root:
        messages.error(request, "No file root is configured. Add one under Files.")
        return redirect("proposal_records", pk=pk)
    return redirect("file_browse", root_id=root.pk, rel=_project_rel(root, proposal))


@login_required
@require_cap("edit_proposals")
@require_POST
def sync_project(request, pk):
    """Index the project's folder: every file becomes a ProjectRecord (by subfolder name), once."""
    proposal = get_object_or_404(Proposal, pk=pk)
    root = get_object_or_404(FileRoot, pk=request.POST.get("root") or FileRoot.objects.filter(is_active=True).values_list("pk", flat=True).first())
    rel = _project_rel(root, proposal)
    log = SyncLog.objects.create(root=root, proposal=proposal, user=request.user)
    seen, created = 0, 0
    try:
        b = backend_for(root)
        existing = set(proposal.records.values_list("path", flat=True))
        for e in b.walk(rel):
            seen += 1
            path = f"{root.path.rstrip('/\\\\')}/{e.rel}".replace("/", "\\") if root.kind == "smb" else f"{root.path.rstrip('/')}/{e.rel}"
            if path in existing:
                continue
            folder = e.rel.lower()
            kind = next((k for needle, k in RECORD_KIND_BY_FOLDER if needle in folder), "other")
            ProjectRecord.objects.create(proposal=proposal, kind=kind, date=(e.modified or proposal.created_at).date(), title=e.name, path=path, created_by=request.user, notes=f"Indexed from {root.name}")
            created += 1
        log.message = f"OK: {seen} files seen, {created} records created from {rel}"
    except BackendError as ex:
        log.message = f"Failed: {ex}"
        messages.error(request, str(ex))
    log.files_seen, log.records_created = seen, created
    log.save()
    if created or seen:
        messages.success(request, f"Indexed {seen} files; {created} new records.")
    return redirect("proposal_records", pk=pk)


@login_required
@require_cap("manage_integrations")
@require_POST
def root_save(request):
    pk = request.POST.get("pk")
    inst = FileRoot.objects.filter(pk=pk).first() if pk else None
    form = FileRootForm(request.POST, instance=inst)
    if form.is_valid():
        form.save()
        messages.success(request, "File root saved.")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("file_home")


@login_required
@require_cap("manage_integrations")
@require_POST
def root_delete(request, pk):
    get_object_or_404(FileRoot, pk=pk).delete()
    return redirect("file_home")

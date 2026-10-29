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


def _classify(exc: Exception) -> dict:
    """Turn a connection problem into something a person can act on."""
    msg = str(exc)
    low = msg.lower()
    if any(k in low for k in ("timed out", "timeout", "unreachable", "no route", "name or service", "getaddrinfo", "connection refused", "errno 111", "errno 113", "errno 110", "not reachable", "is the share mounted", "nodename nor servname")):
        return {"kind": "network", "title": "The file server can't be reached from here", "advice": "This usually means you are not on the office network. Connect to the VPN (or plug into the dr-sauer domain) and try again. If you are already connected, the share may be offline or the server address may have changed."}
    if any(k in low for k in ("access", "denied", "logon", "password", "credential", "status_logon_failure", "permission")):
        return {"kind": "auth", "title": "The file server refused the login", "advice": "The stored username or password for this location is wrong or has expired. An IT or integrations user can update it under File server → Add or edit a share."}
    if "not found" in low or "no such" in low:
        return {"kind": "missing", "title": "That folder doesn't exist on the share", "advice": "The project folder may not have been created yet, or the folder rule for this location needs adjusting."}
    return {"kind": "other", "title": "The file server returned an error", "advice": "Try again in a moment. If it keeps happening, send the message below to IT."}


def _safe_backend(root):
    try:
        return backend_for(root), None
    except Exception as e:  # smbprotocol raises its own types on connect
        return None, e
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
        b, err = _safe_backend(r)
        try:
            ok = bool(b and b.available())
        except Exception:
            ok = False
        status.append((r, ok))
    return render(request, "files/home.html", {"roots": status, "form": FileRootForm(), "all_roots": FileRoot.objects.all(), "logs": SyncLog.objects.select_related("root", "proposal", "user")[:10]})


@login_required
def browse(request, root_id, rel=""):
    root = get_object_or_404(FileRoot, pk=root_id, is_active=True)
    b, err = _safe_backend(root)
    entries, problem = [], None
    if err is None:
        try:
            entries = b.listdir(rel)
        except Exception as e:
            err = e
    if err is not None:
        problem = {**_classify(err), "detail": str(err)[:300]}
        return render(request, "files/unreachable.html", {"root": root, "rel": rel.strip("/"), "problem": problem, "crumbs": _crumbs(rel)}, status=200)
    return render(request, "files/browse.html", {"root": root, "rel": rel.strip("/"), "entries": entries, "crumbs": _crumbs(rel), "error": "", "parent": posixpath.dirname(rel.strip("/"))})


@login_required
def download(request, root_id, rel):
    root = get_object_or_404(FileRoot, pk=root_id, is_active=True)
    try:
        f, name, size = backend_for(root).open(rel)
    except Exception as e:
        problem = {**_classify(e), "detail": str(e)[:300]}
        return render(request, "files/unreachable.html", {"root": root, "rel": rel, "problem": problem, "crumbs": _crumbs(rel)})
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
    b, err = _safe_backend(root)
    if err is not None:
        problem = {**_classify(err), "detail": str(err)[:300]}
        return render(request, "files/unreachable.html", {"root": root, "rel": rel, "problem": problem, "crumbs": _crumbs(rel)})
    n = 0
    try:
        for f in request.FILES.getlist("files"):
            b.save(rel, f.name, f)
            n += 1
        if request.POST.get("folder"):
            b.mkdir(rel, request.POST["folder"])
            messages.success(request, f"Folder “{request.POST['folder']}” created.")
    except Exception as e:
        messages.error(request, _classify(e)["title"] + ": " + str(e)[:200])
    if n:
        messages.success(request, f"Uploaded {n} file{'s' if n != 1 else ''}.")
    return redirect("file_browse", root_id=root.pk, rel=rel)


def _project_rel(root, proposal):
    return root.relative_folder(proposal)


@login_required
def project_folder(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    root = FileRoot.for_proposal(proposal) or FileRoot.objects.filter(is_active=True).first()
    if not root:
        messages.error(request, "No file location is configured. Add one under File server.")
        return redirect("proposal_records", pk=pk)
    return redirect("file_browse", root_id=root.pk, rel=_project_rel(root, proposal))


@login_required
@require_cap("edit_proposals")
@require_POST
def sync_project(request, pk):
    """Index the project's folder: every file becomes a ProjectRecord (by subfolder name), once."""
    proposal = get_object_or_404(Proposal, pk=pk)
    default_root = FileRoot.for_proposal(proposal)
    root = get_object_or_404(FileRoot, pk=request.POST.get("root") or (default_root.pk if default_root else FileRoot.objects.filter(is_active=True).values_list("pk", flat=True).first()))
    rel = _project_rel(root, proposal)
    log = SyncLog.objects.create(root=root, proposal=proposal, user=request.user)
    seen, created = 0, 0
    try:
        b, err = _safe_backend(root)
        if err is not None:
            raise BackendError(str(err))
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
    except Exception as ex:
        c = _classify(ex)
        log.message = f"Failed: {ex}"
        messages.error(request, f"{c['title']}. {c['advice']}")
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

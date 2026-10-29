from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import effective_caps

from .forms import RequestForm, TriageForm
from .models import Notification, Request, RequestEvent, RequestKind, notify

User = get_user_model()


def _is_handler(user, req=None):
    if user.is_superuser or "manage_users" in effective_caps_safe(user):
        return True
    if req is not None:
        return req.handlers().filter(pk=user.pk).exists()
    return RequestKind.objects.filter(handled_by__users=user).exists()


def effective_caps_safe(user):
    from core.models import user_capabilities

    return user_capabilities(user)


@login_required
def request_list(request):
    handler = _is_handler(request.user)
    qs = Request.objects.select_related("kind", "requester", "assignee")
    mine = qs.filter(Q(requester=request.user) | Q(on_behalf_of=request.user))
    if handler:
        handled_kinds = RequestKind.objects.filter(handled_by__users=request.user)
        queue = qs if request.user.is_superuser else qs.filter(kind__in=handled_kinds)
    else:
        queue = qs.none()
    status = request.GET.get("status", "open")
    if status == "open":
        queue = queue.filter(status__in=["open", "progress"])
    elif status:
        queue = queue.filter(status=status)
    return render(request, "tickets/list.html", {"mine": mine[:20], "queue": queue[:100], "handler": handler, "status": status, "form": RequestForm(), "kinds": RequestKind.objects.filter(is_active=True)})


@login_required
@require_POST
def request_create(request):
    form = RequestForm(request.POST)
    if form.is_valid():
        req = form.save(commit=False)
        req.requester = request.user
        behalf = request.POST.get("on_behalf_of")
        if behalf:
            req.on_behalf_of = User.objects.filter(pk=behalf).first()
        payload = {k[3:]: v for k, v in request.POST.items() if k.startswith("pl_") and v}
        if payload:
            req.payload = payload
        req.save()
        RequestEvent.objects.create(request=req, user=request.user, note="Request opened", status="open")
        notify(req.handlers().exclude(pk=request.user.pk), f"New request R-{req.number}: {req.title}", f"/requests/{req.pk}/", email_subject=f"[TunnelVision] New request R-{req.number}")
        messages.success(request, f"Request R-{req.number} sent to {req.kind.handled_by or 'the administrators'}.")
        return redirect("request_detail", pk=req.pk)
    messages.error(request, form.errors.as_text())
    return redirect(request.POST.get("next") or "request_list")


@login_required
def request_detail(request, pk):
    req = get_object_or_404(Request.objects.select_related("kind", "requester", "assignee", "on_behalf_of"), pk=pk)
    handler = _is_handler(request.user, req)
    if not handler and req.requester_id != request.user.pk and req.on_behalf_of_id != request.user.pk:
        messages.error(request, "You can only see your own requests.")
        return redirect("request_list")
    form = TriageForm(instance=req)
    form.fields["assignee"].queryset = req.handlers()
    return render(request, "tickets/detail.html", {"req": req, "handler": handler, "form": form, "events": req.events.select_related("user")})


@login_required
@require_POST
def request_update(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if not _is_handler(request.user, req):
        messages.error(request, "Only the handling group can update this request.")
        return redirect("request_detail", pk=pk)
    form = TriageForm(request.POST, instance=req)
    form.fields["assignee"].queryset = req.handlers()
    if form.is_valid():
        req = form.save()
        note = form.cleaned_data.get("note", "")
        RequestEvent.objects.create(request=req, user=request.user, note=note, status=req.status)
        if req.status == "done" and req.kind.key == "profile" and req.payload and req.on_behalf_of_id:
            _apply_profile_payload(req)
        notify([req.requester] + ([req.on_behalf_of] if req.on_behalf_of_id and req.on_behalf_of_id != req.requester_id else []), f"R-{req.number} is now {req.get_status_display().lower()}{': ' + note if note else ''}", f"/requests/{req.pk}/")
        messages.success(request, "Request updated and the requester notified.")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("request_detail", pk=pk)


def _apply_profile_payload(req):
    """A done profile request applies the requested office / title automatically."""
    from community.models import Profile
    from core.models import Office

    prof, _ = Profile.objects.get_or_create(user=req.on_behalf_of)
    if req.payload.get("office"):
        o = Office.objects.filter(pk=req.payload["office"]).first() or Office.objects.filter(code=req.payload["office"]).first()
        if o:
            prof.office = o
    if req.payload.get("title"):
        prof.title = req.payload["title"]
    prof.save()


@login_required
@require_POST
def request_comment(request, pk):
    req = get_object_or_404(Request, pk=pk)
    note = request.POST.get("note", "").strip()
    if note:
        RequestEvent.objects.create(request=req, user=request.user, note=note)
        targets = set(req.handlers()) | {req.requester}
        targets.discard(request.user)
        notify(targets, f"R-{req.number}: {request.user.get_full_name() or request.user.username} commented", f"/requests/{req.pk}/")
    return redirect("request_detail", pk=pk)


# ---- notifications ---------------------------------------------------------
@login_required
def notifications(request):
    items = request.user.notifications.all()[:50]
    return render(request, "tickets/notifications.html", {"items": items})


@login_required
@require_POST
def notifications_read(request):
    request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
    return redirect(request.POST.get("next") or "notifications")


@login_required
def notifications_badge(request):
    n = request.user.notifications.filter(read_at__isnull=True).count()
    return JsonResponse({"unread": n})

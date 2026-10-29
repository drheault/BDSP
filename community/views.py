from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.permissions import has_cap

from .forms import CommentForm, EndorsementForm, ProfileForm, RatingForm, UserSkillForm
from .models import Comment, Endorsement, MentorMatch, Profile, Rating, Reaction, Skill, UserSkill, suggest_mentors

User = get_user_model()


def _target(ct_id, obj_id):
    ct = get_object_or_404(ContentType, pk=ct_id)
    obj = ct.get_object_for_this_type(pk=obj_id)
    return ct, obj


def _thread(request, ct, obj):
    comments = Comment.objects.filter(content_type=ct, object_id=obj.pk, parent__isnull=True).select_related("author", "author__profile").prefetch_related("replies__author")
    return render(request, "community/_thread.html", {"ct": ct, "obj": obj, "comments": comments, "form": CommentForm(), "reaction": Reaction.score(obj)})


@login_required
def thread(request, ct_id, obj_id):
    ct, obj = _target(ct_id, obj_id)
    return _thread(request, ct, obj)


@login_required
@require_POST
def comment_add(request, ct_id, obj_id):
    ct, obj = _target(ct_id, obj_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.content_type, c.object_id, c.author = ct, obj.pk, request.user
        parent = request.POST.get("parent")
        if parent:
            c.parent = Comment.objects.filter(pk=parent, content_type=ct, object_id=obj.pk).first()
        c.save()
    return _thread(request, ct, obj)


@login_required
@require_POST
def comment_delete(request, pk):
    c = get_object_or_404(Comment, pk=pk)
    if c.author_id != request.user.pk and not request.user.is_superuser and "manage_users" not in request.caps if hasattr(request, "caps") else c.author_id != request.user.pk and not request.user.is_superuser:
        return HttpResponseForbidden("Only the author or an administrator can delete a comment.")
    ct, obj_id = c.content_type, c.object_id
    c.delete()
    return _thread(request, ct, ct.get_object_for_this_type(pk=obj_id))


@login_required
@require_POST
def react(request, ct_id, obj_id, value):
    ct, obj = _target(ct_id, obj_id)
    val = Reaction.UP if value == "up" else Reaction.DOWN
    r, created = Reaction.objects.get_or_create(content_type=ct, object_id=obj.pk, user=request.user, defaults={"value": val})
    if not created:
        if r.value == val:
            r.delete()  # toggle off
        else:
            r.value = val
            r.save()
    return render(request, "community/_reactions.html", {"ct": ct, "obj": obj, "reaction": Reaction.score(obj), "mine": Reaction.objects.filter(content_type=ct, object_id=obj.pk, user=request.user).values_list("value", flat=True).first()})


@login_required
@require_POST
def rate(request, ct_id, obj_id):
    ct, obj = _target(ct_id, obj_id)
    form = RatingForm(request.POST)
    if form.is_valid():
        Rating.objects.update_or_create(content_type=ct, object_id=obj.pk, user=request.user, defaults={"stars": form.cleaned_data["stars"], "review": form.cleaned_data["review"]})
        messages.success(request, "Thanks — rating saved.")
    else:
        messages.error(request, "Pick 1 to 5 stars.")
    return redirect(request.POST.get("next") or "/")


# ---- people ------------------------------------------------------------------
@login_required
def people(request):
    q = request.GET.get("q", "").strip()
    skill = request.GET.get("skill", "")
    users = User.objects.filter(is_active=True).select_related("profile").prefetch_related("skills__skill", "access_roles").order_by("first_name", "username")
    if q:
        users = users.filter(first_name__icontains=q) | users.filter(last_name__icontains=q) | users.filter(username__icontains=q) | users.filter(skills__skill__name__icontains=q)
        users = users.distinct()
    if skill:
        users = users.filter(skills__skill_id=skill, skills__is_learning=False).distinct()
    skills = Skill.objects.annotate(n=Count("holders")).order_by("-n", "name")
    return render(request, "community/people.html", {"users": users, "q": q, "skill": skill, "skills": skills, "mentor_suggestions": suggest_mentors(request.user)})


@login_required
def person(request, pk):
    user = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    Profile.objects.get_or_create(user=user)
    skills = user.skills.select_related("skill")
    received = Endorsement.objects.filter(to_user=user).select_related("from_user", "skill")
    can_endorse = user.pk != request.user.pk
    endorse_form = EndorsementForm()
    endorse_form.fields["skill"].queryset = Skill.objects.filter(holders__user=user).distinct()
    return render(request, "community/person.html", {
        "person": user, "skills": skills, "received": received, "can_endorse": can_endorse, "endorse_form": endorse_form,
        "mentoring": MentorMatch.objects.filter(mentor=user).select_related("mentee", "skill"), "mentored": MentorMatch.objects.filter(mentee=user).select_related("mentor", "skill"),
        "tools": user.tools.all() if hasattr(user, "tools") else [], "proposals": user.proposals.all()[:8],
    })


def _profile_form_view(request, target, template="community/profile_form.html"):
    """Shared by 'my profile' and 'edit someone's profile'. Office is locked unless the editor may edit profiles."""
    profile, _ = Profile.objects.get_or_create(user=target)
    may_edit_others = has_cap(request, "edit_profiles") or request.user.is_superuser
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile, can_change_office=may_edit_others)
    if request.method == "POST" and form.is_valid():
        form.save()
        for f in ("first_name", "last_name", "email"):
            if f in request.POST:
                setattr(target, f, request.POST[f])
        target.save()
        messages.success(request, "Profile saved.")
        return redirect("person", pk=target.pk)
    from core.models import Office

    from tickets.models import RequestKind

    pk_kind = RequestKind.objects.filter(key="profile").values_list("pk", flat=True).first()
    return render(request, template, {"form": form, "profile": profile, "target": target, "is_self": target.pk == request.user.pk, "may_edit_others": may_edit_others, "profile_kind_id": pk_kind,
                                      "skill_form": UserSkillForm(), "skills": target.skills.select_related("skill"), "offices": Office.objects.filter(is_active=True)})


@login_required
def my_profile(request):
    return _profile_form_view(request, request.user)


@login_required
def person_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk != request.user.pk and not (has_cap(request, "edit_profiles") or request.user.is_superuser):
        messages.error(request, "You can edit your own profile; ask a partner or administrator to change someone else's, or raise a request.")
        return redirect("person", pk=pk)
    return _profile_form_view(request, target)


@login_required
@require_POST
def skill_add(request):
    target = request.user
    if request.GET.get("user") and (has_cap(request, "edit_profiles") or request.user.is_superuser):
        target = get_object_or_404(User, pk=request.GET["user"])
    form = UserSkillForm(request.POST)
    if form.is_valid():
        UserSkill.objects.update_or_create(user=target, skill=form.cleaned_data["skill"], defaults={"self_level": form.cleaned_data["self_level"], "is_learning": form.cleaned_data["is_learning"], "note": form.cleaned_data["note"]})
        messages.success(request, "Skill saved.")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("my_profile" if target == request.user else "person_edit", *([] if target == request.user else [target.pk]))


@login_required
@require_POST
def skill_remove(request, pk):
    us = get_object_or_404(UserSkill, pk=pk, user=request.user)
    us.delete()
    return redirect("my_profile")


@login_required
@require_POST
def endorse(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = EndorsementForm(request.POST)
    if form.is_valid():
        e = form.save(commit=False)
        e.from_user, e.to_user = request.user, target
        try:
            e.clean()
            Endorsement.objects.update_or_create(from_user=request.user, to_user=target, skill=e.skill, defaults={"level": e.level, "context": e.context})
            messages.success(request, f"You endorsed {target.get_full_name() or target.username} for {e.skill}.")
        except ValidationError as ex:
            messages.error(request, " ".join(ex.messages))
    else:
        messages.error(request, form.errors.as_text())
    return redirect("person", pk=pk)


@login_required
@require_POST
def mentor_propose(request, pk):
    mentor = get_object_or_404(User, pk=pk)
    skill = get_object_or_404(Skill, pk=request.POST.get("skill"))
    if mentor.pk == request.user.pk:
        messages.error(request, "You cannot mentor yourself.")
        return redirect("people")
    MentorMatch.objects.get_or_create(mentor=mentor, mentee=request.user, skill=skill, defaults={"proposed_by": request.user})
    messages.success(request, f"Mentoring request sent to {mentor.get_full_name() or mentor.username} for {skill}.")
    return redirect("person", pk=pk)


@login_required
@require_POST
def mentor_respond(request, pk, action):
    m = get_object_or_404(MentorMatch, pk=pk)
    if request.user.pk not in (m.mentor_id, m.mentee_id):
        return HttpResponseForbidden()
    m.status = {"accept": "active", "decline": "declined", "done": "done"}.get(action, m.status)
    m.save()
    return redirect("person", pk=request.user.pk)

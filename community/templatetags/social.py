from django import template
from django.contrib.contenttypes.models import ContentType

from community.models import Comment, Rating, Reaction

register = template.Library()


@register.inclusion_tag("community/_thread_box.html", takes_context=True)
def comments_for(context, obj, title="Comments"):
    ct = ContentType.objects.get_for_model(obj)
    return {"ct": ct, "obj": obj, "title": title, "n": Comment.objects.filter(content_type=ct, object_id=obj.pk).count(), "request": context.get("request")}


@register.inclusion_tag("community/_reactions.html", takes_context=True)
def reactions_for(context, obj):
    ct = ContentType.objects.get_for_model(obj)
    user = context["request"].user
    mine = Reaction.objects.filter(content_type=ct, object_id=obj.pk, user=user).values_list("value", flat=True).first() if user.is_authenticated else None
    return {"ct": ct, "obj": obj, "reaction": Reaction.score(obj), "mine": mine}


@register.simple_tag
def rating_summary(obj):
    return Rating.summary(obj)


@register.filter(name="ct_id")
def ct_id(obj):
    return ContentType.objects.get_for_model(obj).pk


@register.inclusion_tag("community/_avatar.html")
def avatar(user, size=32):
    profile = getattr(user, "profile", None)
    return {"user": user, "profile": profile, "size": size, "initials": profile.initials if profile else "".join(p[0] for p in (user.get_full_name() or user.username).split()[:2]).upper()}

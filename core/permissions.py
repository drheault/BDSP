"""Capability-based access control on top of AccessRole."""

from functools import wraps

from django.core.exceptions import PermissionDenied

from .models import AccessRole, user_capabilities


def effective_caps(request) -> set:
    """The user's capabilities, narrowed to a role when an admin is previewing as that role."""
    real = user_capabilities(request.user)
    session = getattr(request, "session", None)
    if session is not None and session.get("view_as_role") and ("manage_users" in real or request.user.is_superuser):
        role = AccessRole.objects.filter(pk=session["view_as_role"]).first()
        if role:
            return set(role.capabilities or [])
    return real


def has_cap(user_or_request, cap: str) -> bool:
    if hasattr(user_or_request, "session"):
        return cap in effective_caps(user_or_request)
    return cap in user_capabilities(user_or_request)


def require_cap(cap: str):
    def deco(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if cap not in effective_caps(request):
                raise PermissionDenied(f"You need the '{cap}' capability for this action.")
            return view(request, *args, **kwargs)

        return wrapper

    return deco

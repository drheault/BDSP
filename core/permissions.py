"""Capability-based access control on top of AccessRole."""

from functools import wraps

from django.core.exceptions import PermissionDenied

from .models import user_capabilities


def has_cap(user, cap: str) -> bool:
    return cap in user_capabilities(user)


def require_cap(cap: str):
    """View decorator: 403 unless the user's roles grant `cap`."""

    def deco(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not has_cap(request.user, cap):
                raise PermissionDenied(f"You need the '{cap}' capability for this action.")
            return view(request, *args, **kwargs)

        return wrapper

    return deco

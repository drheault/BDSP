from .models import AccessRole, CAPABILITIES, CompanyProfile, Theme, user_capabilities


def company(request):
    try:
        company = CompanyProfile.get_solo()
        theme = Theme.active()
    except Exception:  # pragma: no cover - e.g. before migrations
        company, theme = None, None
    user = getattr(request, "user", None)
    real_caps = user_capabilities(user)
    caps = set(real_caps)
    view_as = None
    session = getattr(request, "session", None)
    if session is not None and session.get("view_as_role") and ("manage_users" in real_caps or getattr(user, "is_superuser", False)):
        role = AccessRole.objects.filter(pk=session["view_as_role"]).first()
        if role:
            caps = set(role.capabilities or [])
            view_as = role
    if hasattr(request, "caps"):
        pass
    request.caps = caps
    return {
        "company": company, "caps": caps, "can": {c: True for c in caps}, "real_caps": real_caps,
        "is_privileged": bool(real_caps & {"manage_users", "manage_settings", "manage_forms", "manage_integrations"}) or getattr(user, "is_superuser", False),
        "view_as": view_as, "capability_labels": CAPABILITIES,
        "theme_css": theme.css() if theme else "", "theme_mode": theme.default_mode if theme else "dark",
        "config_roles": AccessRole.objects.all() if view_as or ("manage_users" in real_caps) else [],
    }

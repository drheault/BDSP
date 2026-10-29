from .models import CompanyProfile, Theme, user_capabilities


def company(request):
    try:
        company = CompanyProfile.get_solo()
        theme = Theme.active()
    except Exception:  # pragma: no cover - e.g. before migrations
        company, theme = None, None
    caps = user_capabilities(getattr(request, "user", None))
    return {"company": company, "caps": caps, "can": {c: True for c in caps}, "theme_css": theme.css() if theme else "", "theme_mode": theme.default_mode if theme else "dark"}

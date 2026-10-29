from .models import CompanyProfile, user_capabilities


def company(request):
    try:
        company = CompanyProfile.get_solo()
    except Exception:  # pragma: no cover - e.g. before migrations
        company = None
    caps = user_capabilities(getattr(request, "user", None))
    return {"company": company, "caps": caps, "can": {c: True for c in caps}}

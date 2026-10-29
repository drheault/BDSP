from .models import CompanyProfile


def company(request):
    try:
        return {"company": CompanyProfile.get_solo()}
    except Exception:  # pragma: no cover - e.g. before migrations
        return {"company": None}

from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except AttributeError:
        return None


@register.filter
def split(value, sep=","):
    return [v for v in str(value).split(sep) if v != ""]


@register.filter
def money(amount, currency=None):
    """{{ amount|money:currency }} → CA$12,345. Falls back to a bare number."""
    if currency is None or not hasattr(currency, "format"):
        from core.models import CompanyProfile

        currency = CompanyProfile.get_solo().base_currency
    return currency.format(amount or 0)


@register.filter
def money2(amount, currency=None):
    if currency is None or not hasattr(currency, "format"):
        from core.models import CompanyProfile

        currency = CompanyProfile.get_solo().base_currency
    return currency.format(amount or 0, 2)


@register.filter
def num(value, places=1):
    try:
        v = Decimal(value or 0)
    except Exception:
        return value
    return f"{v:,.{places}f}".rstrip("0").rstrip(".") if places else f"{v:,.0f}"


@register.filter
def pct_class(value):
    """Colour a variance percentage: within ±10% ok, ±25% warn, else bad."""
    if value is None:
        return ""
    v = abs(float(value))
    return "ok" if v <= 10 else ("warn" if v <= 25 else "bad")


@register.inclusion_tag("includes/pencil.html", takes_context=True)
def form_pencil(context, form_key, label="Edit this form"):
    """Small pencil for admins: opens the form builder for this form (hidden for everyone else)."""
    can = context.get("can") or {}
    return {"show": bool(can.get("manage_forms")), "form_key": form_key, "label": label}

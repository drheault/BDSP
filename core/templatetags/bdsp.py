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

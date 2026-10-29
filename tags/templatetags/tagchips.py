from django import template

from tags.forms import tag_datalist

register = template.Library()


@register.inclusion_tag("tags/_chips.html")
def tag_chips(obj, small=False):
    try:
        tags = list(obj.tags)
    except Exception:
        tags = []
    return {"tags": tags, "small": small}


@register.inclusion_tag("tags/_datalist.html")
def tag_datalist_tag():
    return {"tags": tag_datalist()}

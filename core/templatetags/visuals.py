from django import template

from core import visuals

register = template.Library()


@register.inclusion_tag("core/visuals/_mesh.html")
def fe_mesh():
    return visuals.mesh()


@register.inclusion_tag("core/visuals/_contours.html")
def fe_contours():
    return {"mesh": visuals.mesh(), "bands": visuals.contour_bands()}

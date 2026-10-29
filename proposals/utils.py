"""Small helpers shared by the htmx list editors."""


def move_item(item, direction, siblings):
    """Swap `order` with the previous/next sibling in an ordered queryset."""
    items = list(siblings.order_by("order", "id"))
    for i, it in enumerate(items):
        if it.order != i:
            it.order = i
            it.save(update_fields=["order"])
    idx = next(i for i, it in enumerate(items) if it.pk == item.pk)
    j = idx - 1 if direction == "up" else idx + 1
    if 0 <= j < len(items):
        a, b = items[idx], items[j]
        a.order, b.order = b.order, a.order
        a.save(update_fields=["order"])
        b.save(update_fields=["order"])

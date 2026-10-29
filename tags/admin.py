from django.contrib import admin

from .models import Tag, TagCategory, TaggedItem


@admin.register(TagCategory)
class TagCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "weight", "order", "color")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "usage")
    list_filter = ("category",)
    search_fields = ("name", "aliases")


@admin.register(TaggedItem)
class TaggedItemAdmin(admin.ModelAdmin):
    list_display = ("tag", "content_type", "object_id")

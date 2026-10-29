from django.urls import path

from . import views

urlpatterns = [
    path("", views.tag_index, name="tag_index"),
    path("suggest/", views.tag_suggest, name="tag_suggest"),
    path("save/", views.tag_save, name="tag_save"),
    path("category/", views.category_save, name="tag_category_save"),
    path("<int:pk>/delete/", views.tag_delete, name="tag_delete"),
    path("<slug:slug>/", views.tag_detail, name="tag_detail"),
]

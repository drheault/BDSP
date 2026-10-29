from django.urls import path

from . import views

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("new/", views.project_create, name="project_create"),
    path("<int:pk>/", views.project_detail, name="project_detail"),
    path("<int:pk>/edit/", views.project_edit, name="project_edit"),
    path("<int:pk>/delete/", views.project_delete, name="project_delete"),
    path("<int:pk>/images/add/", views.image_add, name="image_add"),
    path("images/<int:pk>/caption/", views.image_caption, name="image_caption"),
    path("images/<int:pk>/delete/", views.image_delete, name="image_delete"),
    path("images/<int:pk>/cover/", views.image_cover, name="image_cover"),
]

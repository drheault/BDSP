from django.urls import path

from . import views

urlpatterns = [
    path("", views.client_list, name="client_list"),
    path("new/", views.client_create, name="client_create"),
    path("<int:pk>/", views.client_detail, name="client_detail"),
    path("<int:pk>/edit/", views.client_edit, name="client_edit"),
    path("<int:pk>/delete/", views.client_delete, name="client_delete"),
    path("<int:client_pk>/contacts/add/", views.contact_add, name="contact_add"),
    path("contacts/<int:pk>/edit/", views.contact_edit, name="contact_edit"),
    path("contacts/<int:pk>/row/", views.contact_row, name="contact_row"),
    path("contacts/<int:pk>/delete/", views.contact_delete, name="contact_delete"),
]

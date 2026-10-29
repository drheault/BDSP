from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/", views.company_settings, name="company_settings"),
    path("settings/currencies/add/", views.currency_add, name="currency_add"),
    path("settings/currencies/<int:pk>/edit/", views.currency_edit, name="currency_edit"),
    path("settings/currencies/<int:pk>/delete/", views.currency_delete, name="currency_delete"),
    path("settings/currencies/<int:pk>/default/", views.currency_make_default, name="currency_make_default"),
    path("settings/regions/add/", views.region_add, name="region_add"),
    path("settings/regions/<int:pk>/edit/", views.region_edit, name="region_edit"),
    path("settings/regions/<int:pk>/delete/", views.region_delete, name="region_delete"),
    path("settings/roles/", views.roles, name="roles"),
    path("settings/roles/new/", views.role_form, name="role_create"),
    path("settings/roles/<int:pk>/", views.role_form, name="role_edit"),
    path("settings/roles/<int:pk>/delete/", views.role_delete, name="role_delete"),
    path("settings/users/", views.users, name="users"),
    path("settings/users/new/", views.user_form, name="user_create"),
    path("settings/users/<int:pk>/", views.user_form, name="user_edit"),
    path("metrics/", views.metrics, name="metrics"),
]

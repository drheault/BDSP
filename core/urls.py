from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/", views.company_settings, name="company_settings"),
    path("settings/currencies/add/", views.currency_add, name="currency_add"),
    path("settings/currencies/<int:pk>/edit/", views.currency_edit, name="currency_edit"),
    path("settings/currencies/<int:pk>/delete/", views.currency_delete, name="currency_delete"),
    path("settings/currencies/<int:pk>/default/", views.currency_make_default, name="currency_make_default"),
    path("metrics/", views.metrics, name="metrics"),
]

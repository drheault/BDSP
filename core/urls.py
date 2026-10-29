from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/", views.company_settings, name="company_settings"),
    path("metrics/", views.metrics, name="metrics"),
]

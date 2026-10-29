from django.urls import path

from . import views

urlpatterns = [
    path("", views.tool_list, name="tool_list"),
    path("upload/", views.tool_upload, name="tool_upload"),
    path("runs/<int:pk>/", views.run_detail, name="run_detail"),
    path("runs/<int:pk>/delete/", views.run_delete, name="run_delete"),
    path("build/", views.spec_builder, name="spec_builder"),
    path("build/<slug:key>/", views.spec_builder, name="spec_edit"),
    path("params/<int:pk>/", views.project_params, name="project_params"),
    path("<slug:key>/live/", views.tool_live, name="tool_live"),
    path("<slug:key>/", views.tool_detail, name="tool_detail"),
    path("<slug:key>/delete/", views.tool_delete, name="tool_delete"),
]

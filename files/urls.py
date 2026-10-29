from django.urls import path, re_path

from . import views

urlpatterns = [
    path("", views.file_home, name="file_home"),
    path("roots/save/", views.root_save, name="file_root_save"),
    path("roots/<int:pk>/delete/", views.root_delete, name="file_root_delete"),
    path("project/<int:pk>/", views.project_folder, name="project_folder"),
    path("project/<int:pk>/sync/", views.sync_project, name="sync_project"),
    path("<int:root_id>/upload/", views.upload, name="file_upload"),
    re_path(r"^(?P<root_id>\d+)/download/(?P<rel>.+)$", views.download, name="file_download"),
    re_path(r"^(?P<root_id>\d+)/browse/(?P<rel>.*)$", views.browse, name="file_browse"),
]

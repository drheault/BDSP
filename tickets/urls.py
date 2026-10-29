from django.urls import path

from . import views

urlpatterns = [
    path("", views.request_list, name="request_list"),
    path("new/", views.request_create, name="request_create"),
    path("<int:pk>/", views.request_detail, name="request_detail"),
    path("<int:pk>/update/", views.request_update, name="request_update"),
    path("<int:pk>/comment/", views.request_comment, name="request_comment"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read/", views.notifications_read, name="notifications_read"),
    path("notifications/badge/", views.notifications_badge, name="notifications_badge"),
]

from django.urls import path

from . import views

urlpatterns = [
    path("", views.programme, name="programme"),
    path("proposal/<int:pk>/", views.proposal_schedule, name="proposal_schedule"),
    path("proposal/<int:pk>/add/", views.task_add, name="task_add"),
    path("proposal/<int:pk>/defaults/", views.schedule_defaults, name="schedule_defaults"),
    path("proposal/<int:pk>/shift-all/", views.schedule_shift_all, name="schedule_shift_all"),
    path("task/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("task/<int:pk>/row/", views.task_row, name="task_row"),
    path("task/<int:pk>/delete/", views.task_delete, name="task_delete"),
    path("task/<int:pk>/move/<str:direction>/", views.task_move, name="task_move"),
    path("task/<int:pk>/shift/", views.task_shift, name="task_shift"),
]

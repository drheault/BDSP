from django.urls import path

from . import views

urlpatterns = [
    path("thread/<int:ct_id>/<int:obj_id>/", views.thread, name="thread"),
    path("thread/<int:ct_id>/<int:obj_id>/add/", views.comment_add, name="comment_add"),
    path("comment/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
    path("react/<int:ct_id>/<int:obj_id>/<str:value>/", views.react, name="react"),
    path("rate/<int:ct_id>/<int:obj_id>/", views.rate, name="rate"),
    path("people/", views.people, name="people"),
    path("people/<int:pk>/", views.person, name="person"),
    path("people/<int:pk>/edit/", views.person_edit, name="person_edit"),
    path("people/<int:pk>/endorse/", views.endorse, name="endorse"),
    path("people/<int:pk>/mentor/", views.mentor_propose, name="mentor_propose"),
    path("mentoring/<int:pk>/<str:action>/", views.mentor_respond, name="mentor_respond"),
    path("me/", views.my_profile, name="my_profile"),
    path("me/skills/add/", views.skill_add, name="skill_add"),
    path("me/skills/<int:pk>/remove/", views.skill_remove, name="skill_remove"),
]

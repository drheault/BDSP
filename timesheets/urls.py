from django.urls import path

from . import views

urlpatterns = [
    path("proposal/<int:pk>/", views.proposal_actuals, name="proposal_actuals"),
    path("proposal/<int:pk>/add/", views.actual_add, name="actual_add"),
    path("proposal/<int:pk>/import/", views.actual_import, name="actual_import"),
    path("entry/<int:pk>/delete/", views.actual_delete, name="actual_delete"),
    path("integrations/", views.integrations, name="integrations"),
    path("integrations/sync/", views.integrations_sync, name="integrations_sync"),
    path("integrations/notes-test/", views.notes_test, name="notes_test"),
]

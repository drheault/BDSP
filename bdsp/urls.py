from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="auth/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("core.urls")),
    path("clients/", include("crm.urls")),
    path("proposals/", include("proposals.urls")),
    path("schedule/", include("scheduling.urls")),
    path("projects/", include("projects.urls")),
    path("actuals/", include("timesheets.urls")),
    path("tags/", include("tags.urls")),
    path("community/", include("community.urls")),
    path("calcs/", include("calcs.urls")),
    path("files/", include("files.urls")),
    path("requests/", include("tickets.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

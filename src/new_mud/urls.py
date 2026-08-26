from django.urls import include, path

urlpatterns = [
    path("api/v1/health/", include("new_mud.apps.health.urls")),
    path("api/v1/auth/", include("new_mud.apps.identity.urls")),
]

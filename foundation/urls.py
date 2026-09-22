from django.urls import path
from .views import app_shell, health

urlpatterns = [
    path("foundation/", app_shell, name="app-shell"),
    path("app", app_shell, name="app-shell-alias"),
    path("health", health, name="health"),
    path("api/health", health, name="api-health"),
]

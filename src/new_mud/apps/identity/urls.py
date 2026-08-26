from django.urls import path

from .views import (
    login_view,
    logout_view,
    recover_view,
    recovery_code_rotate_view,
    refresh_view,
    register_view,
)

urlpatterns = [
    path("register", register_view, name="auth-register"),
    path("login", login_view, name="auth-login"),
    path("refresh", refresh_view, name="auth-refresh"),
    path("logout", logout_view, name="auth-logout"),
    path("recover", recover_view, name="auth-recover"),
    path(
        "recovery-code/rotate",
        recovery_code_rotate_view,
        name="auth-recovery-rotate",
    ),
]

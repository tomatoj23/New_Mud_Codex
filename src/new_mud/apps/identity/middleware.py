from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


class AuthNoStoreMiddleware:
    """Prevent every public authentication response from entering a cache."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if request.path_info.startswith("/api/v1/auth/"):
            response["Cache-Control"] = "no-store"
        return response

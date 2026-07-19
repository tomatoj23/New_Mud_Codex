from django.db import connections
from django.db.utils import DatabaseError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def liveness(_request):
    return Response({"status": "ok", "service": "new-mud", "version": "1"})


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness(_request):
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return Response({"status": "not_ready", "database": "unavailable"}, status=503)
    return Response({"status": "ok", "database": "ready"})

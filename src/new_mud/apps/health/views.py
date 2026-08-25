from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .readiness import probe_readiness


@api_view(["GET"])
@permission_classes([AllowAny])
def liveness(_request):
    return Response({"status": "ok", "service": "new-mud", "version": "1"})


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness(_request):
    status_code, payload = probe_readiness()
    return Response(payload, status=status_code)

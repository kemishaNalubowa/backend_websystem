# students/api/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from .serializers import PingSerializer

@api_view(['GET'])
@permission_classes([AllowAny])  # Public for testing; we'll secure later
def ping_api(request):
    """
    Test endpoint: Returns JSON to confirm Django ↔ React connection.
    URL: GET /api/students/ping/
    """
    data = {
        'message': '🎉 Django API is connected!',
        'timestamp': timezone.now(),
        'user': str(request.user) if request.user.is_authenticated else 'anonymous',
    }
    serializer = PingSerializer(data)
    return Response(serializer.data)
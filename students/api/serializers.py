# students/api/serializers.py
from rest_framework import serializers

# Simple test serializer - no database model needed yet
class PingSerializer(serializers.Serializer):
    """Test serializer for connection check"""
    message = serializers.CharField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
    user = serializers.CharField(read_only=True)
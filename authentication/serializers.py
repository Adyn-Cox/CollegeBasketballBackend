from rest_framework import serializers
from authentication.models import SupabaseUser


class LoginSerializer(serializers.Serializer):
    """Serializer for login request."""
    access_token = serializers.CharField(required=True)
    refresh_token = serializers.CharField(required=True)


class LoginResponseSerializer(serializers.ModelSerializer):
    """Serializer for login response."""
    
    class Meta:
        model = SupabaseUser
        fields = ['supabase_user_id', 'email', 'created_at', 'updated_at']
        read_only_fields = ['supabase_user_id', 'email', 'created_at', 'updated_at']


class LogoutSerializer(serializers.Serializer):
    """Serializer for logout request."""
    pass  # No fields needed, token is in header


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer for refresh token request."""
    refresh_token = serializers.CharField(required=True)


class RefreshTokenResponseSerializer(serializers.Serializer):
    """Serializer for refresh token response."""
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()


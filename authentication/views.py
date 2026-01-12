import requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
from authentication.models import SupabaseUser
from authentication.serializers import (
    LoginSerializer,
    LoginResponseSerializer,
    RefreshTokenSerializer,
    RefreshTokenResponseSerializer,
)
from authentication.utils import get_jwt_validator


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Public endpoint to login and save user information.
    Accepts access_token and refresh_token from Supabase.
    """
    serializer = LoginSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    access_token = serializer.validated_data['access_token']
    refresh_token = serializer.validated_data['refresh_token']
    
    # Validate the access token
    validator = get_jwt_validator()
    token_payload = validator.validate_token(access_token)
    
    if not token_payload:
        return Response(
            {'error': 'Invalid or expired access token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Extract user information from token
    user_id = validator.extract_user_id(token_payload)
    email = token_payload.get('email') or token_payload.get('user_metadata', {}).get('email', '')
    
    if not user_id:
        return Response(
            {'error': 'Invalid token payload'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Get or create user in database
    user, created = SupabaseUser.objects.update_or_create(
        supabase_user_id=user_id,
        defaults={
            'email': email,
            'refresh_token': refresh_token,
        }
    )
    
    response_serializer = LoginResponseSerializer(user)
    return Response(
        {
            'message': 'Login successful',
            'user': response_serializer.data,
            'created': created
        },
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    """
    Public endpoint to logout and remove refresh token.
    Optionally accepts a token in the header to identify the user.
    """
    # Try to get user from request (if token was provided)
    user = getattr(request, 'user', None)
    
    if user and isinstance(user, SupabaseUser):
        # Remove refresh token
        user.refresh_token = None
        user.save()
        return Response(
            {'message': 'Logout successful'},
            status=status.HTTP_200_OK
        )
    
    # If no user in request, check if refresh_token is in body
    refresh_token = request.data.get('refresh_token')
    if refresh_token:
        try:
            user = SupabaseUser.objects.get(refresh_token=refresh_token)
            user.refresh_token = None
            user.save()
            return Response(
                {'message': 'Logout successful'},
                status=status.HTTP_200_OK
            )
        except SupabaseUser.DoesNotExist:
            pass
    
    # If we can't identify the user, still return success
    # (idempotent operation)
    return Response(
        {'message': 'Logout successful'},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    """
    Public endpoint to refresh access token using refresh token.
    Exchanges refresh token with Supabase for new access token.
    """
    serializer = RefreshTokenSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    refresh_token = serializer.validated_data['refresh_token']
    
    # Verify refresh token exists in our database
    try:
        user = SupabaseUser.objects.get(refresh_token=refresh_token)
    except SupabaseUser.DoesNotExist:
        return Response(
            {'error': 'Invalid refresh token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Exchange refresh token with Supabase for new tokens
    supabase_url = getattr(settings, 'SUPABASE_URL', None)
    if not supabase_url:
        return Response(
            {'error': 'Supabase configuration error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Call Supabase token refresh endpoint
    try:
        response = requests.post(
            f"{supabase_url}/auth/v1/token?grant_type=refresh_token",
            json={'refresh_token': refresh_token},
            headers={
                'Content-Type': 'application/json',
                'apikey': getattr(settings, 'SUPABASE_ANON_KEY', ''),
            },
            timeout=10
        )
        
        if response.status_code != 200:
            return Response(
                {'error': 'Failed to refresh token with Supabase'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        data = response.json()
        new_access_token = data.get('access_token')
        new_refresh_token = data.get('refresh_token', refresh_token)  # Fallback to old if not provided
        
        # Update refresh token in database
        user.refresh_token = new_refresh_token
        user.save()
        
        response_serializer = RefreshTokenResponseSerializer({
            'access_token': new_access_token,
            'refresh_token': new_refresh_token,
        })
        
        return Response(response_serializer.data, status=status.HTTP_200_OK)
        
    except requests.RequestException:
        return Response(
            {'error': 'Failed to communicate with Supabase'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

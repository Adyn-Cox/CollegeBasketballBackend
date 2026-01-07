from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from authentication.models import SupabaseUser
from authentication.utils import get_jwt_validator


class SupabaseTokenValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate Supabase JWT tokens on every request.
    Skips validation for public endpoints.
    """
    
    # Public endpoints that don't require token validation
    PUBLIC_ENDPOINTS = [
        '/api/auth/login',
        '/api/auth/logout',
        '/api/auth/refresh',
    ]
    
    def process_request(self, request):
        """Process the request and validate the token if needed."""
        # Check if this is a public endpoint
        if self._is_public_endpoint(request.path):
            request.user = None
            return None
        
        # Extract token from Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        # If no auth header, return 401
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse(
                {'error': 'Missing or invalid authorization header'},
                status=401
            )
        
        token = auth_header.split(' ')[1]
        
        # Validate token
        validator = get_jwt_validator()
        token_payload = validator.validate_token(token)
        
        if not token_payload:
            return JsonResponse(
                {'error': 'Invalid or expired token'},
                status=401
            )
        
        # Extract user ID from token
        user_id = validator.extract_user_id(token_payload)
        
        if not user_id:
            return JsonResponse(
                {'error': 'Invalid token payload'},
                status=401
            )
        
        # Get or create user from database
        try:
            user = SupabaseUser.objects.get(supabase_user_id=user_id)
            request.user = user
        except SupabaseUser.DoesNotExist:
            # User doesn't exist in our database yet
            # This could happen if they haven't logged in through our API
            # For now, we'll return 401, but you might want to handle this differently
            return JsonResponse(
                {'error': 'User not found in database'},
                status=401
            )
        
        return None
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if the given path is a public endpoint."""
        # Normalize path by removing trailing slash for comparison
        normalized_path = path.rstrip('/')
        for public_path in self.PUBLIC_ENDPOINTS:
            # Normalize public path too
            normalized_public = public_path.rstrip('/')
            # Check exact match
            if normalized_path == normalized_public:
                return True
        return False


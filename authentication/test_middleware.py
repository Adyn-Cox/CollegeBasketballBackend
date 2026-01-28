"""Tests for authentication middleware."""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from django.http import JsonResponse
from django.test import RequestFactory
from authentication.middleware import SupabaseTokenValidationMiddleware
from authentication.models import SupabaseUser


@pytest.fixture
def middleware():
    """Create middleware instance."""
    return SupabaseTokenValidationMiddleware(lambda x: x)


@pytest.fixture
def factory():
    """Create request factory."""
    return RequestFactory()


@pytest.mark.django_db
class TestSupabaseTokenValidationMiddleware:
    """Tests for SupabaseTokenValidationMiddleware."""
    
    def test_public_endpoint_skips_validation(self, middleware, factory):
        """Test that public endpoints skip token validation."""
        request = factory.get('/api/auth/login')
        result = middleware.process_request(request)
        
        assert result is None
        assert request.user is None
    
    def test_public_endpoint_with_trailing_slash(self, middleware, factory):
        """Test public endpoint matching with trailing slash."""
        request = factory.get('/api/auth/login/')
        result = middleware.process_request(request)
        
        assert result is None
    
    def test_missing_authorization_header(self, middleware, factory):
        """Test request without Authorization header."""
        request = factory.get('/api/protected')
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == 401
        data = result.content.decode()
        assert 'Missing or invalid authorization header' in data
    
    def test_invalid_authorization_header_format(self, middleware, factory):
        """Test request with invalid Authorization header format."""
        request = factory.get('/api/protected', HTTP_AUTHORIZATION='InvalidFormat token')
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == 401
    
    @patch('authentication.middleware.get_jwt_validator')
    def test_invalid_token(self, mock_validator, middleware, factory):
        """Test request with invalid token."""
        validator_mock = MagicMock()
        validator_mock.validate_token.return_value = None
        mock_validator.return_value = validator_mock
        
        request = factory.get('/api/protected', HTTP_AUTHORIZATION='Bearer invalid-token')
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == 401
        data = result.content.decode()
        assert 'Invalid or expired token' in data
    
    @patch('authentication.middleware.get_jwt_validator')
    def test_token_without_user_id(self, mock_validator, middleware, factory):
        """Test token that doesn't contain user_id."""
        validator_mock = MagicMock()
        validator_mock.validate_token.return_value = {'email': 'test@example.com'}  # No 'sub'
        validator_mock.extract_user_id.return_value = None
        mock_validator.return_value = validator_mock
        
        request = factory.get('/api/protected', HTTP_AUTHORIZATION='Bearer valid-token')
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == 401
        data = result.content.decode()
        assert 'Invalid token payload' in data
    
    @patch('authentication.middleware.get_jwt_validator')
    @pytest.mark.django_db
    def test_user_not_found_in_database(self, mock_validator, middleware, factory):
        """Test when user doesn't exist in database."""
        non_existent_user_id = str(uuid.uuid4())
        validator_mock = MagicMock()
        validator_mock.validate_token.return_value = {'sub': non_existent_user_id}
        validator_mock.extract_user_id.return_value = non_existent_user_id
        mock_validator.return_value = validator_mock
        
        request = factory.get('/api/protected', HTTP_AUTHORIZATION='Bearer valid-token')
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == 401
        data = result.content.decode()
        assert 'User not found in database' in data
    
    @patch('authentication.middleware.get_jwt_validator')
    @pytest.mark.django_db
    def test_valid_token_and_user(self, mock_validator, middleware, factory):
        """Test successful token validation with existing user."""
        # Create a user for this test
        user = SupabaseUser.objects.create(
            supabase_user_id=uuid.uuid4(),
            email='test@example.com',
            refresh_token='test-token'
        )
        
        token_payload = {'sub': str(user.supabase_user_id), 'email': 'test@example.com'}
        validator_mock = MagicMock()
        validator_mock.validate_token.return_value = token_payload
        validator_mock.extract_user_id.return_value = str(user.supabase_user_id)
        mock_validator.return_value = validator_mock
        
        request = factory.get('/api/protected', HTTP_AUTHORIZATION='Bearer valid-token')
        result = middleware.process_request(request)
        
        assert result is None
        assert request.user == user
    
    def test_is_public_endpoint_all_public_paths(self, middleware):
        """Test _is_public_endpoint for all public paths."""
        assert middleware._is_public_endpoint('/api/auth/login') is True
        assert middleware._is_public_endpoint('/api/auth/logout') is True
        assert middleware._is_public_endpoint('/api/auth/refresh') is True
        assert middleware._is_public_endpoint('/api/auth/login/') is True
        assert middleware._is_public_endpoint('/api/auth/logout/') is True
        assert middleware._is_public_endpoint('/api/auth/refresh/') is True
    
    def test_is_public_endpoint_protected_paths(self, middleware):
        """Test _is_public_endpoint returns False for protected paths."""
        assert middleware._is_public_endpoint('/api/protected') is False
        assert middleware._is_public_endpoint('/api/users') is False
        assert middleware._is_public_endpoint('/api/auth/other') is False

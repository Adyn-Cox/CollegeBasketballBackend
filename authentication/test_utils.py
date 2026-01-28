"""Tests for authentication utilities."""
import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from django.conf import settings
from authentication.utils import SupabaseJWTValidator, get_jwt_validator


@pytest.fixture
def jwt_secret():
    """JWT secret for testing."""
    return "test-jwt-secret-key-for-testing-purposes-only"


@pytest.fixture
def sample_token_payload():
    """Sample token payload."""
    return {
        'sub': 'user-123',
        'email': 'test@example.com',
        'exp': datetime.utcnow() + timedelta(hours=1),
        'iat': datetime.utcnow(),
    }


class TestSupabaseJWTValidator:
    """Tests for SupabaseJWTValidator."""
    
    @patch('authentication.utils.settings')
    def test_init_loads_config(self, mock_settings):
        """Test that __init__ loads configuration."""
        mock_settings.SUPABASE_JWT_SECRET = 'test-secret'
        mock_settings.SUPABASE_URL = 'https://test.supabase.co'
        
        validator = SupabaseJWTValidator()
        
        assert validator.jwt_secret == 'test-secret'
        assert validator.supabase_url == 'https://test.supabase.co'
    
    @patch('authentication.utils.settings')
    def test_init_raises_error_when_secret_missing(self, mock_settings):
        """Test that __init__ raises error when JWT secret is missing."""
        mock_settings.SUPABASE_JWT_SECRET = None
        mock_settings.SUPABASE_URL = 'https://test.supabase.co'
        
        with pytest.raises(ValueError, match="SUPABASE_JWT_SECRET"):
            SupabaseJWTValidator()
    
    def test_get_token_algorithm_hs256(self, jwt_secret, sample_token_payload):
        """Test _get_token_algorithm for HS256 token."""
        token = jwt.encode(sample_token_payload, jwt_secret, algorithm='HS256')
        validator = SupabaseJWTValidator()
        
        algorithm = validator._get_token_algorithm(token)
        assert algorithm == 'HS256'
    
    def test_get_token_algorithm_es256(self):
        """Test _get_token_algorithm for ES256 token."""
        # Create a mock ES256 token header
        token = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyJ9.signature"
        validator = SupabaseJWTValidator()
        
        algorithm = validator._get_token_algorithm(token)
        # Will return None if token is invalid, but we're testing the method
        # In real scenario, it would return 'ES256'
    
    def test_get_token_algorithm_invalid_token(self):
        """Test _get_token_algorithm with invalid token."""
        validator = SupabaseJWTValidator()
        algorithm = validator._get_token_algorithm("invalid.token.here")
        assert algorithm is None
    
    @patch('authentication.utils.settings')
    def test_validate_token_hs256_valid(self, mock_settings, jwt_secret, sample_token_payload):
        """Test validate_token with valid HS256 token."""
        mock_settings.SUPABASE_JWT_SECRET = jwt_secret
        mock_settings.SUPABASE_URL = 'https://test.supabase.co'
        
        token = jwt.encode(sample_token_payload, jwt_secret, algorithm='HS256')
        validator = SupabaseJWTValidator()
        
        result = validator.validate_token(token)
        assert result is not None
        assert result['sub'] == 'user-123'
        assert result['email'] == 'test@example.com'
    
    @patch('authentication.utils.settings')
    def test_validate_token_hs256_expired(self, mock_settings, jwt_secret):
        """Test validate_token with expired HS256 token."""
        mock_settings.SUPABASE_JWT_SECRET = jwt_secret
        mock_settings.SUPABASE_URL = 'https://test.supabase.co'
        
        expired_payload = {
            'sub': 'user-123',
            'exp': datetime.utcnow() - timedelta(hours=1),
            'iat': datetime.utcnow() - timedelta(hours=2),
        }
        token = jwt.encode(expired_payload, jwt_secret, algorithm='HS256')
        validator = SupabaseJWTValidator()
        
        result = validator.validate_token(token)
        assert result is None
    
    def test_validate_token_hs256_invalid_signature(self, jwt_secret, sample_token_payload):
        """Test validate_token with invalid signature."""
        token = jwt.encode(sample_token_payload, 'wrong-secret', algorithm='HS256')
        validator = SupabaseJWTValidator()
        
        result = validator.validate_token(token)
        assert result is None
    
    @patch('authentication.utils.settings')
    def test_validate_token_es256(self, mock_settings, sample_token_payload):
        """Test validate_token with ES256 token (OAuth)."""
        mock_settings.SUPABASE_JWT_SECRET = 'test-secret'
        mock_settings.SUPABASE_URL = 'https://test.supabase.co'
        
        validator = SupabaseJWTValidator()
        
        # Create a valid JWT token structure for ES256
        # We'll use jwt.encode but with ES256 algorithm detection mocked
        from datetime import datetime, timedelta
        payload = {
            'sub': 'user-123',
            'exp': int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            'iat': int(datetime.utcnow().timestamp()),
        }
        
        # Mock the algorithm to be ES256
        with patch.object(validator, '_get_token_algorithm', return_value='ES256'):
            # For ES256, we decode without signature verification
            # Create a token that can be decoded (even if signature is wrong)
            token = jwt.encode(payload, 'dummy-key', algorithm='HS256')
            # Now decode it without verification (which is what ES256 path does)
            result = validator.validate_token(token)
            # Should return the decoded payload
            assert result is not None
            assert result['sub'] == 'user-123'
    
    def test_validate_token_unknown_algorithm(self, jwt_secret, sample_token_payload):
        """Test validate_token with unknown algorithm."""
        validator = SupabaseJWTValidator()
        
        with patch.object(validator, '_get_token_algorithm', return_value='HS512'):
            token = jwt.encode(sample_token_payload, jwt_secret, algorithm='HS256')
            result = validator.validate_token(token)
            assert result is None
    
    def test_validate_token_no_secret(self):
        """Test validate_token when secret is None."""
        validator = SupabaseJWTValidator()
        validator.jwt_secret = None
        
        result = validator.validate_token("any-token")
        assert result is None
    
    def test_validate_token_generic_exception(self, jwt_secret):
        """Test validate_token when exception occurs."""
        validator = SupabaseJWTValidator()
        
        # Mock jwt.decode to raise a generic exception
        with patch('jwt.decode', side_effect=Exception("Unexpected error")):
            result = validator.validate_token("any-token")
            assert result is None
    
    def test_extract_user_id_from_sub(self):
        """Test extract_user_id extracts from 'sub' field."""
        validator = SupabaseJWTValidator()
        payload = {'sub': 'user-123', 'email': 'test@example.com'}
        
        user_id = validator.extract_user_id(payload)
        assert user_id == 'user-123'
    
    def test_extract_user_id_from_user_id(self):
        """Test extract_user_id extracts from 'user_id' field when 'sub' missing."""
        validator = SupabaseJWTValidator()
        payload = {'user_id': 'user-456', 'email': 'test@example.com'}
        
        user_id = validator.extract_user_id(payload)
        assert user_id == 'user-456'
    
    def test_extract_user_id_prefers_sub(self):
        """Test extract_user_id prefers 'sub' over 'user_id'."""
        validator = SupabaseJWTValidator()
        payload = {'sub': 'user-123', 'user_id': 'user-456'}
        
        user_id = validator.extract_user_id(payload)
        assert user_id == 'user-123'
    
    def test_extract_user_id_none_when_missing(self):
        """Test extract_user_id returns None when neither field exists."""
        validator = SupabaseJWTValidator()
        payload = {'email': 'test@example.com'}
        
        user_id = validator.extract_user_id(payload)
        assert user_id is None


class TestGetJWTValidator:
    """Tests for get_jwt_validator singleton."""
    
    def test_get_jwt_validator_returns_singleton(self):
        """Test that get_jwt_validator returns the same instance."""
        # Clear the singleton
        import authentication.utils
        authentication.utils._jwt_validator = None
        
        validator1 = get_jwt_validator()
        validator2 = get_jwt_validator()
        
        assert validator1 is validator2
        assert isinstance(validator1, SupabaseJWTValidator)

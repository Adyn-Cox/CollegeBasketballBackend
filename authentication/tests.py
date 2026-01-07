import uuid
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from authentication.models import SupabaseUser


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def jwt_secret():
    """JWT secret for testing."""
    return "test-jwt-secret-key-for-testing-purposes-only"


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_token_payload(sample_user_id):
    """Create a sample JWT token payload."""
    return {
        'sub': sample_user_id,
        'email': 'test@example.com',
        'exp': datetime.utcnow() + timedelta(hours=1),
        'iat': datetime.utcnow(),
    }


@pytest.fixture
def valid_access_token(jwt_secret, sample_token_payload):
    """Create a valid JWT access token."""
    return jwt.encode(sample_token_payload, jwt_secret, algorithm='HS256')


@pytest.fixture
def sample_refresh_token():
    """Sample refresh token."""
    return "test-refresh-token-12345"


@pytest.fixture
def supabase_user(sample_user_id, sample_refresh_token):
    """Create a test SupabaseUser."""
    return SupabaseUser.objects.create(
        supabase_user_id=sample_user_id,
        email='test@example.com',
        refresh_token=sample_refresh_token,
        role='member'
    )


@pytest.mark.django_db
class TestSupabaseUserModel:
    """Tests for the SupabaseUser model."""
    
    def test_create_user(self, sample_user_id):
        """Test creating a SupabaseUser."""
        user = SupabaseUser.objects.create(
            supabase_user_id=sample_user_id,
            email='test@example.com',
            refresh_token='test-token',
            role='member'
        )
        
        assert user.email == 'test@example.com'
        assert str(user.supabase_user_id) == sample_user_id
        assert user.role == 'member'
        assert user.refresh_token == 'test-token'
        assert user.created_at is not None
        assert user.updated_at is not None
    
    def test_user_str_representation(self, supabase_user):
        """Test the string representation of SupabaseUser."""
        expected = f"{supabase_user.email} ({supabase_user.supabase_user_id})"
        assert str(supabase_user) == expected
    
    def test_user_unique_constraint(self, sample_user_id):
        """Test that supabase_user_id must be unique."""
        SupabaseUser.objects.create(
            supabase_user_id=sample_user_id,
            email='test1@example.com',
        )
        
        # Try to create another user with the same ID
        with pytest.raises(Exception):  # Should raise IntegrityError
            SupabaseUser.objects.create(
                supabase_user_id=sample_user_id,
                email='test2@example.com',
            )


@pytest.mark.django_db
class TestLoginView:
    """Tests for the login endpoint."""
    
    @patch('authentication.views.get_jwt_validator')
    def test_login_success_new_user(
        self, 
        mock_validator, 
        api_client, 
        valid_access_token, 
        sample_refresh_token,
        sample_token_payload,
        sample_user_id
    ):
        """Test successful login with a new user."""
        # Mock the JWT validator
        validator_mock = MagicMock()
        validator_mock.validate_token.return_value = sample_token_payload
        validator_mock.extract_user_id.return_value = sample_user_id
        mock_validator.return_value = validator_mock
        
        url = reverse('authentication:login')
        data = {
            'access_token': valid_access_token,
            'refresh_token': sample_refresh_token,
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data
        assert response.data['message'] == 'Login successful'
        assert 'user' in response.data
        assert response.data['user']['email'] == 'test@example.com'
        assert response.data['created'] is True
        
        # Verify user was created
        user = SupabaseUser.objects.get(supabase_user_id=sample_user_id)
        assert user.email == 'test@example.com'
        assert user.refresh_token == sample_refresh_token
    
    @patch('authentication.views.get_jwt_validator')
    def test_login_success_existing_user(
        self,
        mock_validator,
        api_client,
        valid_access_token,
        sample_refresh_token,
        sample_token_payload,
        supabase_user
    ):
        """Test successful login with an existing user."""
        # Mock the JWT validator
        validator_mock = MagicMock()
        validator_mock.validate_token.return_value = sample_token_payload
        validator_mock.extract_user_id.return_value = str(supabase_user.supabase_user_id)
        mock_validator.return_value = validator_mock
        
        url = reverse('authentication:login')
        new_refresh_token = 'new-refresh-token-123'
        data = {
            'access_token': valid_access_token,
            'refresh_token': new_refresh_token,
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['created'] is False
        
        # Verify refresh token was updated
        supabase_user.refresh_from_db()
        assert supabase_user.refresh_token == new_refresh_token
    
    @patch('authentication.views.get_jwt_validator')
    def test_login_invalid_token(self, mock_validator, api_client):
        """Test login with an invalid token."""
        # Mock the JWT validator to return None (invalid token)
        validator_mock = MagicMock()
        validator_mock.validate_token.return_value = None
        mock_validator.return_value = validator_mock
        
        url = reverse('authentication:login')
        data = {
            'access_token': 'invalid-token',
            'refresh_token': 'refresh-token',
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data
        assert 'Invalid or expired access token' in response.data['error']
    
    def test_login_missing_fields(self, api_client):
        """Test login with missing required fields."""
        url = reverse('authentication:login')
        data = {
            'access_token': 'token',
            # Missing refresh_token
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data


@pytest.mark.django_db
class TestLogoutView:
    """Tests for the logout endpoint."""
    
    def test_logout_with_refresh_token(self, api_client, supabase_user):
        """Test logout using refresh token in request body."""
        url = reverse('authentication:logout')
        data = {
            'refresh_token': supabase_user.refresh_token,
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Logout successful'
        
        # Verify refresh token was removed
        supabase_user.refresh_from_db()
        assert supabase_user.refresh_token is None
    
    def test_logout_without_token(self, api_client):
        """Test logout without providing a token (idempotent)."""
        url = reverse('authentication:logout')
        data = {}
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Logout successful'
    
    def test_logout_invalid_refresh_token(self, api_client):
        """Test logout with invalid refresh token."""
        url = reverse('authentication:logout')
        data = {
            'refresh_token': 'invalid-token',
        }
        
        response = api_client.post(url, data, format='json')
        
        # Should still return success (idempotent)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestRefreshTokenView:
    """Tests for the refresh token endpoint."""
    
    @patch('authentication.views.requests.post')
    def test_refresh_token_success(
        self,
        mock_post,
        api_client,
        supabase_user,
        jwt_secret
    ):
        """Test successful token refresh."""
        # Mock Supabase API response
        new_access_token = jwt.encode(
            {'sub': str(supabase_user.supabase_user_id), 'exp': datetime.utcnow() + timedelta(hours=1)},
            jwt_secret,
            algorithm='HS256'
        )
        new_refresh_token = 'new-refresh-token-456'
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': new_access_token,
            'refresh_token': new_refresh_token,
        }
        mock_post.return_value = mock_response
        
        url = reverse('authentication:refresh')
        data = {
            'refresh_token': supabase_user.refresh_token,
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access_token' in response.data
        assert 'refresh_token' in response.data
        assert response.data['refresh_token'] == new_refresh_token
        
        # Verify refresh token was updated in database
        supabase_user.refresh_from_db()
        assert supabase_user.refresh_token == new_refresh_token
    
    def test_refresh_token_invalid_token(self, api_client):
        """Test refresh with invalid refresh token."""
        url = reverse('authentication:refresh')
        data = {
            'refresh_token': 'invalid-token',
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data
        assert 'Invalid refresh token' in response.data['error']
    
    def test_refresh_token_missing_field(self, api_client):
        """Test refresh token with missing field."""
        url = reverse('authentication:refresh')
        data = {}
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

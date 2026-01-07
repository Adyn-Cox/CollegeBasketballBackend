"""
Pytest configuration and fixtures for Django tests.
Mocks all environment variables required for testing.
"""
import os


def pytest_configure():
    """Configure pytest and mock environment variables before Django loads."""
    # Mock all required environment variables for testing
    # This runs before Django settings are loaded, overriding any existing values
    os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost:5432/testdb'
    os.environ['SUPABASE_URL'] = 'https://test.supabase.co'
    os.environ['SUPABASE_JWT_SECRET'] = 'test-jwt-secret-key-for-testing-only'
    os.environ['SUPABASE_ANON_KEY'] = 'test-anon-key'


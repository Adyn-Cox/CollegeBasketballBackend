"""
Pytest configuration and fixtures for Django tests.
Mocks all environment variables required for testing.
"""
import os

# Set environment variables at module import time (before Django settings load)
# This ensures they're available when pytest-django loads Django settings
os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/testdb')
os.environ.setdefault('SUPABASE_URL', 'https://test.supabase.co')
os.environ.setdefault('SUPABASE_JWT_SECRET', 'test-jwt-secret-key-for-testing-only')
os.environ.setdefault('SUPABASE_ANON_KEY', 'test-anon-key')


"""Tests for ASGI and WSGI configuration."""
import pytest


def test_asgi_application_imports():
    """Test that ASGI application can be imported."""
    from config.asgi import application
    assert application is not None
    assert callable(application)


def test_wsgi_application_imports():
    """Test that WSGI application can be imported."""
    from config.wsgi import application
    assert application is not None
    assert callable(application)

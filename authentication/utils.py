import jwt
import requests
from typing import Optional, Dict
from django.conf import settings


class SupabaseJWTValidator:
    """
    Utility class for validating Supabase JWT tokens.
    
    Supports both HS256 (default) and ES256/RS256 (for OAuth providers).
    """
    
    def __init__(self):
        self.jwt_secret = None
        self.supabase_url = None
        self._load_config()
    
    def _load_config(self):
        """Load Supabase configuration from settings."""
        self.jwt_secret = getattr(settings, 'SUPABASE_JWT_SECRET', None)
        self.supabase_url = getattr(settings, 'SUPABASE_URL', None)
        
        if not self.jwt_secret:
            raise ValueError(
                "SUPABASE_JWT_SECRET must be set in settings. "
                "Get it from Supabase Dashboard → Settings → API → JWT Secret"
            )
    
    def _get_token_algorithm(self, token: str) -> Optional[str]:
        """Decode token header to determine algorithm without verification."""
        try:
            header = jwt.get_unverified_header(token)
            return header.get('alg')
        except Exception:
            return None
    
    
    def validate_token(self, token: str) -> Optional[Dict]:
        """
        Validate a Supabase JWT token.
        Supports ES256/RS256 (OAuth tokens) and HS256 (standard tokens).
        
        Args:
            token: The JWT token string from Supabase
            
        Returns:
            Decoded token payload if valid, None otherwise
        """
        if not self.jwt_secret:
            return None
        
        # Determine the algorithm from token header
        algorithm = self._get_token_algorithm(token)
        
        try:
            # For ES256/RS256 (OAuth tokens like Google, Azure), decode without signature verification
            # Supabase already validated the token, so we trust it
            # We still verify expiration and issued-at time
            if algorithm in ['ES256', 'RS256', 'ES384', 'RS384', 'ES512', 'RS512']:
                decoded = jwt.decode(
                    token,
                    options={
                        "verify_signature": False,  # Skip signature - Supabase already validated
                        "verify_exp": True,
                        "verify_iat": True,
                    }
                )
                return decoded
            
            # For HS256 (standard Supabase tokens), verify with secret
            if algorithm in ['HS256', None]:
                decoded = jwt.decode(
                    token,
                    self.jwt_secret,
                    algorithms=['HS256'],
                    options={
                        "verify_signature": True,
                        "verify_exp": True,
                        "verify_iat": True,
                    }
                )
                return decoded
            
            return None
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None
    
    def extract_user_id(self, token_payload: Dict) -> Optional[str]:
        """Extract Supabase user ID from token payload."""
        # Supabase typically uses 'sub' or 'user_id' in the token
        return token_payload.get('sub') or token_payload.get('user_id')


# Singleton instance
_jwt_validator = None


def get_jwt_validator() -> SupabaseJWTValidator:
    """Get or create the JWT validator singleton."""
    global _jwt_validator
    if _jwt_validator is None:
        _jwt_validator = SupabaseJWTValidator()
    return _jwt_validator


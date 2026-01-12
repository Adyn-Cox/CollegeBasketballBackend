import jwt
from typing import Optional, Dict, Any
from django.conf import settings


class SupabaseJWTValidator:
    """
    Utility class for validating Supabase JWT tokens.
    
    Supabase uses HS256 (HMAC-SHA256) symmetric signing by default.
    The JWT Secret is configured in Supabase Dashboard → Settings → API → JWT Secret.
    """
    
    def __init__(self):
        self.jwt_secret = None
        self._load_config()
    
    def _load_config(self):
        """Load Supabase JWT secret from settings."""
        supabase_jwt_secret = getattr(settings, 'SUPABASE_JWT_SECRET', None)
        
        if not supabase_jwt_secret:
            raise ValueError(
                "SUPABASE_JWT_SECRET must be set in settings. "
                "Get it from Supabase Dashboard → Settings → API → JWT Secret"
            )
        
        self.jwt_secret = supabase_jwt_secret
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a Supabase JWT token using HS256 algorithm.
        
        Args:
            token: The JWT token string from Supabase
            
        Returns:
            Decoded token payload if valid, None otherwise
        """
        if not self.jwt_secret:
            return None
        
        try:
            # Supabase uses HS256 (HMAC-SHA256) symmetric signing
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
            return decoded  # type: ignore[no-any-return]
            
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


from django.db import models


class SupabaseUser(models.Model):
    """User model to store Supabase user information and refresh tokens."""
    
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('admin', 'Admin'),
    ]
    
    supabase_user_id = models.UUIDField(unique=True, db_index=True)
    email = models.EmailField(max_length=255)
    refresh_token = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'supabase_users'
        verbose_name = 'Supabase User'
        verbose_name_plural = 'Supabase Users'
        indexes = [
            models.Index(fields=['supabase_user_id']),
            models.Index(fields=['email']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return f"{self.email} ({self.supabase_user_id})"

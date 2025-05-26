"""
Supabase client utilities for additional operations
"""

import os
from supabase import create_client, Client
from typing import Optional, Dict, Any


class SupabaseClient:
    """Supabase client wrapper for additional operations"""
    
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and Service Role Key must be set")
        
        self.client: Client = create_client(supabase_url, supabase_key)
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user from Supabase Auth"""
        try:
            response = self.client.auth.admin.get_user_by_id(user_id)
            return response.user.dict() if response.user else None
        except Exception:
            return None
    
    async def create_user(self, email: str, password: str, user_metadata: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Create user in Supabase Auth"""
        try:
            response = self.client.auth.admin.create_user({
                "email": email,
                "password": password,
                "user_metadata": user_metadata or {},
                "email_confirm": True
            })
            return response.user.dict() if response.user else None
        except Exception as e:
            raise Exception(f"Failed to create user: {str(e)}")
    
    async def update_user_metadata(self, user_id: str, metadata: Dict[str, Any]) -> bool:
        """Update user metadata in Supabase Auth"""
        try:
            self.client.auth.admin.update_user_by_id(user_id, {
                "user_metadata": metadata
            })
            return True
        except Exception:
            return False
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete user from Supabase Auth"""
        try:
            self.client.auth.admin.delete_user(user_id)
            return True
        except Exception:
            return False


# Global Supabase client instance
supabase_client = SupabaseClient()

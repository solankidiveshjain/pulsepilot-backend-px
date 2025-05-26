"""
Authentication utilities for Supabase integration
"""

import os
import jwt
from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import User, Team
from utils.database import get_db


security = HTTPBearer()


async def verify_supabase_token(token: str) -> dict:
    """Verify Supabase JWT token"""
    try:
        # Get Supabase JWT secret from environment
        jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        if not jwt_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Supabase JWT secret not configured"
            )
        
        # Decode and verify token
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            issuer=os.getenv("SUPABASE_URL")
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    
    # Verify token
    payload = await verify_supabase_token(credentials.credentials)
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Find user in database
    stmt = select(User).where(User.user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


async def get_current_team(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Team:
    """Get current user's team"""
    
    stmt = select(Team).where(Team.team_id == current_user.team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    return team


def require_roles(required_roles: list):
    """Decorator to require specific user roles"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user or not any(role in current_user.roles for role in required_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator

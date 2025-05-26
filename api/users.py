"""
User management endpoints integrated with Supabase Auth
"""

from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, EmailStr

from models.database import User, Team
from utils.database import get_db
from utils.auth import get_current_user, get_current_team
from utils.supabase_client import supabase_client


router = APIRouter()


class UserCreateRequest(BaseModel):
    email: EmailStr
    user_name: str
    roles: List[str] = ["member"]


class UserUpdateRequest(BaseModel):
    user_name: Optional[str] = None
    roles: Optional[List[str]] = None


class UserResponse(BaseModel):
    user_id: UUID
    email: str
    user_name: Optional[str]
    roles: List[str]
    team_id: UUID
    created_at: str


@router.post("/teams/{team_id}/users")
async def create_team_user(
    team_id: UUID,
    request: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team),
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """Create a new user in the team"""
    
    # Verify team access and admin role
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    try:
        # Create user in Supabase Auth
        supabase_user = await supabase_client.create_user(
            email=request.email,
            password="temp_password_123!",  # User will reset on first login
            user_metadata={
                "team_id": str(team_id),
                "user_name": request.user_name,
                "roles": request.roles
            }
        )
        
        if not supabase_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user in authentication system"
            )
        
        # Create user in our database
        user = User(
            user_id=UUID(supabase_user["id"]),
            team_id=team_id,
            email=request.email,
            user_name=request.user_name,
            roles=request.roles
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return UserResponse(
            user_id=user.user_id,
            email=user.email,
            user_name=user.user_name,
            roles=user.roles,
            team_id=user.team_id,
            created_at=user.created_at.isoformat()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.get("/teams/{team_id}/users")
async def list_team_users(
    team_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> List[UserResponse]:
    """List all users in the team"""
    
    # Verify team access
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    stmt = select(User).where(User.team_id == team_id)
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    return [
        UserResponse(
            user_id=user.user_id,
            email=user.email,
            user_name=user.user_name,
            roles=user.roles,
            team_id=user.team_id,
            created_at=user.created_at.isoformat()
        )
        for user in users
    ]


@router.put("/teams/{team_id}/users/{user_id}")
async def update_team_user(
    team_id: UUID,
    user_id: UUID,
    request: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team),
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """Update a team user"""
    
    # Verify team access and permissions
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    # Users can update themselves, admins can update anyone
    if current_user.user_id != user_id and "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Find user
    stmt = select(User).where(
        User.user_id == user_id,
        User.team_id == team_id
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user
    update_data = {}
    if request.user_name is not None:
        update_data["user_name"] = request.user_name
    if request.roles is not None and "admin" in current_user.roles:
        update_data["roles"] = request.roles
    
    if update_data:
        stmt = update(User).where(User.user_id == user_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        
        # Update Supabase user metadata
        await supabase_client.update_user_metadata(
            str(user_id),
            {
                "user_name": update_data.get("user_name", user.user_name),
                "roles": update_data.get("roles", user.roles)
            }
        )
        
        await db.refresh(user)
    
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        user_name=user.user_name,
        roles=user.roles,
        team_id=user.team_id,
        created_at=user.created_at.isoformat()
    )


@router.delete("/teams/{team_id}/users/{user_id}")
async def delete_team_user(
    team_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team),
    current_user: User = Depends(get_current_user)
):
    """Delete a team user"""
    
    # Verify team access and admin role
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    # Can't delete yourself
    if current_user.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    # Find user
    stmt = select(User).where(
        User.user_id == user_id,
        User.team_id == team_id
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete from Supabase Auth
    await supabase_client.delete_user(str(user_id))
    
    # Delete from our database
    await db.delete(user)
    await db.commit()
    
    return {"message": "User deleted successfully"}

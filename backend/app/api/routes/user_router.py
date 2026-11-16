from pydantic import BaseModel
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.common.auth import verify_jwt  
from app.db.session import get_db_users  
from app.db.user_models.user_meta import User_Meta 



router = APIRouter(
    prefix="/users", 
    tags=["Users"]
)

class SyncUserRequest(BaseModel):
    username: str

@router.post("/sync")
async def sync_user(
    request: SyncUserRequest,
    user_id: str = Depends(verify_jwt), 
    db: AsyncSession = Depends(get_db_users) 
):
    """
    called by the React frontend immediately after a successful Supabase login/signup.
    ensures the user exists in the local PostgreSQL database.
    """
    result = await db.execute(select(User_Meta).where(User_Meta.user_id == user_id))
    existing_user = result.scalar_one_or_none()

    if not existing_user:
        new_user = User_Meta(
            user_id=user_id,
            username=request.username,
            created_at=datetime.now(timezone.utc)
        )
        db.add(new_user)
        await db.commit()
        return {
            "status": "success", 
            "message": "User synced to local database", 
            "user_id": user_id
        }

    return {
        "status": "success", 
        "message": "User already exists", 
        "user_id": user_id
    }
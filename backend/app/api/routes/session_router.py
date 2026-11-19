from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel

from app.common.auth import verify_jwt 
from app.db.session import get_db_users 
from app.db.user_models.chat_session import Chat_Session 
from app.db.user_models.chat_message import Chat_Message, Role 
from app.agent.llm.router import _MODELS

router = APIRouter(
    prefix="/sessions", 
    tags=["Sessions"]
)


class CreateSessionRequest(BaseModel):
    query: str 
    
@router.post("")
async def create_session(
    request: Request,
    session_request: CreateSessionRequest,
    user_id: str = Depends(verify_jwt), 
    db: AsyncSession = Depends(get_db_users) 
):
    """Creates a new session and generates a title using an LLM."""
    session_id = str(uuid.uuid4())
    
    llm = _MODELS["gemini"]
    message = f"You need to convert the given query below into a title of 3 to 5 words:\nQuery: {session_request.query}"
    try:
        title = await llm.ainvoke(message)
    except Exception:
        if len(session_request.query) > 30:
            title = f"{session_request.query[:30]}..."
        else:
            title = f"{session_request.query[:30]}"
            
    new_session = Chat_Session(
        session_id=session_id, 
        user_id=user_id, 
        title=title, 
        created_at=datetime.now(timezone.utc), 
        updated_at=datetime.now(timezone.utc) 
    )
    
    db.add(new_session)
    await db.commit()
    
    return {
        "session_id": session_id, 
        "title": title
    }

@router.get("")
async def list_sessions(
    user_id: str = Depends(verify_jwt), 
    db: AsyncSession = Depends(get_db_users) 
):
    """Fetches all sessions for the logged-in user to populate the sidebar."""
    result = await db.execute(
        select(Chat_Session)
        .where(Chat_Session.user_id == user_id) 
        .order_by(desc(Chat_Session.updated_at)) 
    )
    sessions = result.scalars().all()
    
    return [
        {
            "session_id": s.session_id, 
            "title": s.title, 
            "updated_at": s.updated_at
        } for s in sessions
    ]

@router.get("/{session_id}/messages")
async def get_session_history(
    session_id: str,
    user_id: str = Depends(verify_jwt), 
    db: AsyncSession = Depends(get_db_users) 
):
    """Loads the chat history when a user clicks a past session in the sidebar."""
    
    session_result = await db.execute(
        select(Chat_Session).where(
            Chat_Session.session_id == session_id, 
            Chat_Session.user_id == user_id 
        )
    )
    if not session_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to view this session"
        )

    msg_result = await db.execute(
        select(Chat_Message)
        .where(Chat_Message.session_id == session_id) 
        .order_by(Chat_Message.created_at) 
    )
    messages = msg_result.scalars().all()
    
    return [
        {
            "message_id": m.message_id, 
            "role": m.role.value,
            "content": m.content, 
            "created_at": m.created_at
        } for m in messages
    ]
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

# Import your dependencies and models
from app.agent.services.agent_service import AgentService
from app.common.auth import verify_jwt 
from app.db.session import get_db_users 
from app.db.user_models.chat_message import Chat_Message, Role 

router = APIRouter(
    prefix="/agent", 
    tags=["Agent"]
)

class ChatRequest(BaseModel):
    query: str
    thread_id: str


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    user_id: str = Depends(verify_jwt), # Validates Supabase JW
    db: AsyncSession = Depends(get_db_users) # Yields DB sessio
):
    agent: AgentService = request.app.state.agent_service 

    # Save the User's Message immediately
    user_msg = Chat_Message(
        session_id=body.thread_id, 
        user_id=user_id, 
        role=Role.USER, 
        content=body.query, 
        created_at=datetime.now(timezone.utc) 
    )
    db.add(user_msg)
    await db.commit()

    # generator to stream data and capture the final text
    async def response_generator():
        final_agent_text = ""
        usage_metadata = {}

        async for chunk in agent.run_query(query=body.query, thread_id=body.thread_id):
            if chunk.startswith("event: message"):
                data_json = json.loads(chunk.split("data: ", 1)[1].strip())
                final_agent_text += data_json.get("text", "")
                yield chunk

            elif chunk.startswith("event: metadata"):
                data_json = json.loads(chunk.split("data: ", 1)[1].strip())
                usage_metadata = data_json.get("usage_metadata", {})
                # yield chunk if React UI displays token usage / compression warnings
                # yield chunk
                continue

            else:
                yield chunk

        # Save agent message (and usage_metadata if you add a JSONB column to Chat_Message)
        agent_msg = Chat_Message(
            session_id=body.thread_id,
            user_id=user_id,
            role=Role.AGENT,
            content=final_agent_text,
            created_at=datetime.utcnow()
        )
        db.add(agent_msg)
        await db.commit()

    # Return the stream using FastAPI's native StreamingResponse
    return StreamingResponse(response_generator(), media_type="text/event-stream")
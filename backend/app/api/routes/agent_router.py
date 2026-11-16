from fastapi import APIRouter, Request

from pydantic import BaseModel

from app.agent.services.agent_service import AgentService

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
    body: ChatRequest
):

    agent: AgentService = request.app.state.agent_service

    result = await agent.run_query(
        query=body.query,
        thread_id=body.thread_id
    )

    return {
        "thread_id": body.thread_id,
        "result": result
    }
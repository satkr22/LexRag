from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.common.config import settings
from app.agent.runtime.runtime_factory import create_agent_runtime
from app.agent.services.agent_service import AgentService

from app.api.routes.agent_router import router as agent_router
from app.api.routes.user_router import router as user_router
from app.api.routes.session_router import router as session_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    async with create_agent_runtime() as runtime:
        
        app.state.agent_service = AgentService(runtime)

        yield


app = FastAPI(lifespan=lifespan)

app.include_router(agent_router)
app.include_router(user_router)
app.include_router(session_router)


@app.get("/")
def root():
    return {
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT
    }
 
    
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "LexRAG-backend"
    }
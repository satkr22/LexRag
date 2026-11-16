from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.common.config import settings
from app.api.routes.agent import router as agent_router
from app.agent.runtime.runtime_factory import create_agent_runtime
from app.agent.services.agent_service import AgentService


@asynccontextmanager
async def lifespan(app: FastAPI):

    async with create_agent_runtime() as runtime:
        
        app.state.agent_service = AgentService(runtime)

        yield


app = FastAPI(lifespan=lifespan)

app.include_router(agent_router)


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
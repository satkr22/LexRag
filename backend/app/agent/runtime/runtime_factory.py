from contextlib import asynccontextmanager
from pathlib import Path

from qdrant_client import AsyncQdrantClient
from fastembed import TextEmbedding, SparseTextEmbedding

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.common.config import settings
from app.db.session import SessionLocal_corpus

from app.agent.config.settings import load_config
from app.agent.llm.router import build_chat_model
from app.agent.tools.tool_registry import build_legal_tools
from app.agent.graph.graph import create_graph

from app.rag.retrieval.query_llm.data_models import QueryResponse

from app.agent.runtime.runtime_model import AgentRuntime


@asynccontextmanager
async def create_agent_runtime():

    qdrant = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        timeout=120
    )

    try:
        dense_model = TextEmbedding(
            model_name=settings.DENSE_MODEL_NAME,
            providers=["CPUExecutionProvider"],
            cache_dir="/models/fastembed"
        )

        sparse_model = SparseTextEmbedding(
            model_name=settings.SPARSE_MODEL_NAME,
            providers=["CPUExecutionProvider"],
            cache_dir="/models/fastembed"
        )

        list(dense_model.embed(["warmup"]))
        list(sparse_model.embed(["warmup"]))

        cfg = load_config()

        tools = await build_legal_tools(
            session_factory=SessionLocal_corpus,
            client=qdrant,
            dense_model=dense_model,
            sparse_model=sparse_model
        )

        llm_rag = build_chat_model(
            config=cfg.llm,
            route="rag",
            schema=QueryResponse
        )

        llm_agent = build_chat_model(
            config=cfg.llm,
            route="agent",
            tools=tools
        )

        system_prompt = Path(
            cfg.agent.system_prompt
        ).resolve().read_text()

        async with AsyncPostgresSaver.from_conn_string(
            settings.DATABASE_URL_MAIN
        ) as checkpointer:

            await checkpointer.setup()

            graph = create_graph(
                executor_model=llm_agent,
                structured_tools=tools,
                checkpointer=checkpointer
            )

            runtime = AgentRuntime(
                cfg=cfg,
                qdrant=qdrant,
                dense_model=dense_model,
                sparse_model=sparse_model,
                graph=graph,
                llm_rag=llm_rag,
                llm_agent=llm_agent,
                system_prompt=system_prompt
            )

            yield runtime

    finally:
        await qdrant.close()
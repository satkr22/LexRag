import json

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.rag.retrieval.retriever_main import retrieve
from app.agent.stream import streaming
from app.agent.runtime.runtime_model import AgentRuntime


class AgentService:

    def __init__(self, runtime):
        self.runtime = runtime

    async def run_query(self, query: str, thread_id: str):

        runtime: AgentRuntime = self.runtime

        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id
            },
            "recursion_limit": 200
        }

        rag_result = await retrieve(
            query=query,
            client=runtime.qdrant,
            dense_model=runtime.dense_model,
            sparse_model=runtime.sparse_model,
            llm_runnable=runtime.llm_rag
        )

        evaluation_dict = {
            "seed_rag_result": rag_result
        }

        # Construct initial message
        if rag_result.get("retriver_failed"):

            seed_message = f"User Query: {query}"

        else:

            seed_message = f"""
            User Query: {query}

            Below is the initial routing result from RAG Hybrid retrieval:

            - Requires Retrieval: {rag_result.get("requires_retrieval")}
            - Initial Results Count: {rag_result.get("count")}

            Data Payload:
            {json.dumps(rag_result.get("results"), indent=2)}

            - Hint: {rag_result.get("hint")}
            """

        # Get existing graph state
        current_state = await runtime.graph.aget_state(config)

        existing_messages = current_state.values.get(
            "executor_messages", []
        )

        current_context_window = current_state.values.get(
            "current_context_window", 0
        )

        token_usage = current_state.values.get(
            "token_usage", {}
        )

        is_new_thread = len(existing_messages) == 0

        # Prepare messages
        messages_to_send = []

        if is_new_thread:
            messages_to_send.append(
                SystemMessage(runtime.system_prompt)
            )

        messages_to_send.append(
            HumanMessage(seed_message)
        )

        cfg = runtime.cfg

        payload = {
            "executor_messages": messages_to_send,
            "task": query,
            "iteration": 0,
            "context_window": cfg.llm.providers[
                cfg.llm.agent.active_provider
            ].context_window,
            "compression_threshold": cfg.llm.providers[
                cfg.llm.agent.active_provider
            ].compression_threshold,
            "current_context_window": current_context_window,
            "is_compressed": False,
            "token_usage": token_usage
        }

        # Execute graph
        result = await streaming(
            graph=runtime.graph,
            payload=payload,
            config=config,
            evaluation_dict=evaluation_dict
        )

        return result
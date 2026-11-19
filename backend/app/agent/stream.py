import json
from langchain_core.runnables import RunnableConfig

async def streaming(
    graph,
    payload: dict,
    config: RunnableConfig,
    evaluation_dict: dict,
):
    total_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    try:
        async for event in graph.astream_events(payload, config=config, version="v2"):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    text = chunk.content[0].get("text", "")
                    yield f"event: message\ndata: {json.dumps({'text': text})}\n\n"

            elif kind == "on_tool_start":
                tool_args = event["data"]["input"]
                tool_name = event["name"]
                yield f"event: thinking_start\ndata: {json.dumps({'tool': tool_name, 'args': tool_args})}\n\n"

            elif kind == "on_tool_end":
                yield f"event: thinking_end\ndata: {json.dumps({'tool': event['name']})}\n\n"

            elif kind == "on_chat_model_end":
                output = event["data"].get("output")
                usage = getattr(output, "usage_metadata", None)
                if usage:
                    total_usage["input_tokens"] += usage.get("input_tokens", 0)
                    total_usage["output_tokens"] += usage.get("output_tokens", 0)
                    total_usage["total_tokens"] += usage.get("total_tokens", 0)

        # Preserve your existing state check after the stream finishes
        final_state = await graph.aget_state(config)
        is_compressed = False
        if final_state and isinstance(final_state.values, dict):
            is_compressed = final_state.values.get("is_compressed", False)

        # Yield a event carrying the final usage & state metadata
        yield f"event: metadata\ndata: {json.dumps({'usage_metadata': total_usage, 'is_compressed': is_compressed})}\n\n"

    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

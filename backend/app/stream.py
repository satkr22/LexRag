from langchain_core.runnables import RunnableConfig


async def streaming(
    graph,
    payload: dict,
    config: RunnableConfig,
    evaluation_dict: dict,
):
    try:
        tool_results = []
        async for event in graph.astream_events(payload, config=config, version="v2"):
            
            kind = event["event"]
            
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    print(f"\nEvent Type: {kind}:\n")
                    print(chunk.content[0].get("text"))
            
            elif kind == "on_tool_start":
                tool_args = event["data"]["input"]
                tool_name = event["name"]
                print(f"\nEvent Type: {kind}:\n")
                print(f"\nTool: {tool_name}\nArgs: {tool_args}")
            
            elif kind == "on_tool_end":
                tool_output = event["data"]["output"]
                tool_results.append(tool_output)
                    
            elif kind == "on_chat_model_end":
                output = event["data"].get("output")
                if output:
                    print(f"\nEvent: {kind}:\n")
                    print(output)
                    
        evaluation_dict["tool_output"] = tool_results
        
        token_usage = {}
        is_compressed = False
        
        final_state = await graph.aget_state(config)
        
        if final_state and hasattr(final_state, "values") and isinstance(final_state.values, dict):
            is_compressed = final_state.values.get("is_compressed", False)
            token_usage = final_state.values.get("token_usage", {})
            evaluation_dict["final_output"] = final_state.values.get("executor_messages", [])[-1].content
            
        return {
            "token_usage": token_usage,
            "is_compressed": is_compressed,
            "evaluation_dict": evaluation_dict
        }
    
    except Exception as e:
        raise ValueError(f"Problem in astream_events: {e}") from e
        # return token_usage
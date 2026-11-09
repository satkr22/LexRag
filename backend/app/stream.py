from langchain_core.runnables import RunnableConfig


async def streaming(
    graph,
    payload: dict,
    config: RunnableConfig,
):
    token_usage = {}
    try:
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
                    
            elif kind == "on_chat_model_end":
                output = event["data"].get("output")
                if output:
                    print(f"\nEvent: {kind}:\n")
                    print(output)
                    token_usage = output.usage_metadata
            
        return token_usage
    
    except Exception as e:
        raise ValueError(f"Problem in astream_events: {e}")  
        # return token_usage
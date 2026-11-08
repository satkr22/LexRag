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
                # extract reasoning
                reasoning_chunk = getattr(chunk, "reasoning_content", None)
                
                if not reasoning_chunk and "reasoning_content" in chunk.additional_kwargs:
                    reasoning_chunk = chunk.additional_kwargs["reasoning_content"]
                
                if reasoning_chunk:
                    print("\nThinking:\n")
                    print(reasoning_chunk)
                
                if chunk.content:
                    print("\nResponse:\n")
                    print(chunk.content[0].get("text"))
            
            elif kind == "on_tool_start":
                tool = event["data"]["input"]
                print("\nUsing Tool:\n")
                print(tool)
            
            elif kind == "on_tool_end":
                tool_output = event["data"]["output"]
                print("\nTool Output:\n")
                print(tool_output)
                    
            elif kind == "on_chat_model_end":
                output = event["data"].get("output")
                token_usage = event["data"].get("usage_metadata", token_usage) 
                print("\nFinal Output:\n")
                print(output)
            
        return token_usage
    
    except Exception as e:
        raise ValueError(f"Problem in astream_events: {e}")  
        # return token_usage
import os
import dotenv
import json, asyncio
from pathlib import Path
from pydantic import BaseModel, Field

from openai import AsyncOpenAI

dotenv.load_dotenv()


class QueryResponse(BaseModel):
    reply: str = Field(description="reply based on users query")
    
client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://ws-n7c4pdh4ldno9hkc.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",                     
)

async def gen(query: str):
    system_prompt = "Reponse in valid json schema"
    response = await client.responses.parse(
        # model="qwen3.8-2.4t-a95b",
        model="qwen3.8-max",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        text_format=QueryResponse,
        temperature=0.7,
    )
    
    result: QueryResponse = response.output_parsed # type: ignore
    
    return result

async def main():

    print(f"generating...")
    rows = await gen("can u read the given pydantic schema i have attached for structured output")
    
    print(rows.reply)

asyncio.run(main())
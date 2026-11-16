import asyncio

from app.agent.runtime.runtime_factory import create_agent_runtime
from app.agent.services.agent_service import AgentService


async def main():

    async with create_agent_runtime() as runtime:

        agent = AgentService(runtime)

        print("\nLexRag CLI initialized.")
        print("Type /exit to quit.\n")

        thread_id = "__lexrag_cli__"

        while True:

            try:
                query = input("\nYou: ").strip()

                if query == "/exit":
                    break

                if not query:
                    continue

                result = await agent.run_query(
                    query=query,
                    thread_id=thread_id
                )

                print("\nAgent execution completed.")

            except KeyboardInterrupt:
                break

            except Exception as e:
                print(f"Error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
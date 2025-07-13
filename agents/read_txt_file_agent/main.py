import asyncio
from typing import Any, Annotated

from genai_session.session import GenAISession

session = GenAISession(
    jwt_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmMWY5ODU1OC1lNjRmLTQwMDgtYjMwYy1iYTY0MDBlYzE0YTgiLCJleHAiOjI1MzQwMjMwMDc5OSwidXNlcl9pZCI6IjhiMDFiM2M1LTJjNGItNDVjMC04OGRlLWQzMTQ1YTI2YWI4ZSJ9.nd7k1LLPvA86T-3fG3EHMvtOdBKlcRYMdGw4F43JcdA"
)


@session.bind(name="read_txt_file", description="Get content from the txt file")
async def read_text_file(
        agent_context,
        file_id: Annotated[str, "ID of the file to read"]
) -> dict[str, Any]:
    file = await agent_context.files.get_by_id(file_id)
    file_content = file.read().decode("utf-8")
    return file_content


async def main():
    print(f"Agent with ID {session.jwt_token} started")
    await session.process_events()


if __name__ == "__main__":
    asyncio.run(main())

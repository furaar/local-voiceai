import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


def get_chat_model() -> ChatOpenAI:
    """Initialize and return a ChatOpenAI model from environment settings."""
    return ChatOpenAI(
        model=os.environ.get("MODEL_NAME"),
        base_url=os.environ["BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
        temperature=0.7,
    )


async def run_e2e_test_with_client(client: MultiServerMCPClient, expected_tools: list[str], test_prompts: list[tuple[str, str]]) -> None:
    """Run an end-to-end test using a connected MCP client and validate tool behavior."""
    tools = client.get_tools()
    tool_names = [tool.name for tool in tools]
    print(f"🔧 Tools list: {tool_names}")

    for tool in expected_tools:
        assert tool in tool_names, f"Expected '{tool}' tool to be available"

    agent = create_react_agent(get_chat_model(), tools)

    for question, expected_answer in test_prompts:
        response = await agent.ainvoke({"messages": question})
        for m in response['messages']:
            m.pretty_print()
        assert any(expected_answer.lower() in m.content.lower() for m in response["messages"]), \
            f"Expected answer to include '{expected_answer}'"

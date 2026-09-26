"""Builds the LangChain tool-calling agent and exposes a simple chat() function.

Run directly for a terminal chat:  python -m agent.agent
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import GoogleAPIError, GoogleRateLimitError

from agent import config
from agent.prompts import build_system_prompt
from agent.tools import ALL_TOOLS

# Free-tier Gemini allows only a few requests per minute and is sometimes overloaded (503). On those errors,
# wait and retry just the model call (not the whole turn), so tools like make_reservation never run twice.
RATE_LIMIT_RETRY = ModelRetryMiddleware(max_retries=3, retry_on=(GoogleRateLimitError, GoogleAPIError), on_failure="error",
                                        initial_delay=20, backoff_factor=1.5, max_delay=60)


def build_agent():
    llm = ChatGoogleGenerativeAI(model=config.CHAT_MODEL, google_api_key=config.GOOGLE_API_KEY,
                                 temperature=0.3, max_retries=3)
    # The system prompt is rebuilt per agent so "today's date" is always current.
    return create_agent(llm, tools=ALL_TOOLS, system_prompt=build_system_prompt(), middleware=[RATE_LIMIT_RETRY])


def chat(agent, history: list[BaseMessage], user_input: str) -> tuple[str, list[dict], list[BaseMessage]]:
    """Send one user message.

    history: full message list from previous turns (this is the conversation memory).
    Returns (reply_text, tool_calls_made_this_turn, updated_history).
    """
    result = agent.invoke({"messages": history + [HumanMessage(user_input)]})
    messages = result["messages"]
    new_messages = messages[len(history):]

    tool_calls = [
        {"name": call["name"], "args": call["args"]}
        for msg in new_messages if isinstance(msg, AIMessage)
        for call in msg.tool_calls
    ]
    return messages[-1].text, tool_calls, messages


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    agent = build_agent()
    history: list[BaseMessage] = []
    print("Spice Garden assistant (type 'exit' to quit)\n")
    while (user := input("You: ").strip()).lower() not in {"exit", "quit"}:
        if not user:
            continue
        reply, calls, history = chat(agent, history, user)
        for c in calls:
            print(f"   [tool] {c['name']}({c['args']})")
        print(f"Spicy: {reply}\n")

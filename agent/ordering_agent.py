"""Builds ordering_agent: GPT-4o + tools + conversation memory.

The agent is a LangGraph ReAct-style agent: GPT-4o decides when to call
the knowledge-base / order / reservation tools, and the checkpointer keeps
per-conversation memory so multi-turn ordering flows work naturally.
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from agent.memory import trim_history
from agent.prompts import SYSTEM_PROMPT
from agent.tools import ALL_TOOLS
from ingestion.logger import get_logger

logger = get_logger(__name__)

# The chat model powering the agent
MODEL_NAME = "gpt-4o"


def build_agent():
    """Create and return the ordering_agent, ready to chat.

    Returns:
        A LangGraph agent. Invoke it with:
            agent.invoke(
                {"messages": [{"role": "user", "content": "..."}]},
                {"configurable": {"thread_id": "<conversation id>"}},
            )

    Raises:
        ValueError: If the OpenAI API key is missing from .env.
    """
    # --- Load the API key from .env and fail fast if missing --------------
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not found — check your .env file")
        raise ValueError("OPENAI_API_KEY is not set in the environment/.env")

    # --- Configure GPT-4o ----------------------------------------------------
    # Low temperature keeps prices, phone numbers and order details accurate
    model = ChatOpenAI(model=MODEL_NAME, temperature=0.3)

    # --- Conversation memory -------------------------------------------------
    # The checkpointer stores message history per session (thread_id), so
    # each user's conversation is remembered separately. The trim_history
    # middleware caps every session at the last 10 messages to keep memory
    # and token usage lightweight.
    checkpointer = InMemorySaver()

    # --- Give the model today's date -----------------------------------------
    # The LLM has no built-in clock; without this it cannot resolve dates
    # like "this Saturday" or validate that a reservation date is upcoming.
    today_line = datetime.now().strftime(
        "\n# Current date\n\nToday is %A, %d %B %Y."
    )

    # --- Assemble the agent --------------------------------------------------
    agent = create_agent(
        model=model,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT + today_line,
        middleware=[trim_history],
        checkpointer=checkpointer,
        name="ordering_agent",
    )

    logger.info(
        "ordering_agent ready (model=%s, tools=%d)", MODEL_NAME, len(ALL_TOOLS)
    )
    return agent

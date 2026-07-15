"""Conversation memory: per-session history, trimmed to the last 10 messages.

How it works:
    - Each user gets a session ID. LangGraph's checkpointer stores a separate
      conversation history per session (thread), so users never see each
      other's messages.
    - Before every model call, the trimming middleware cuts the stored
      history down to the last MAX_MESSAGES messages. This keeps memory
      lightweight: old messages are actually deleted from the session state,
      not just hidden, so both memory usage and token cost stay bounded.
"""

import openai
from langchain.agents.middleware import AgentState, Runtime, before_model
from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from agent.guardrails import (
    REFUSAL_MESSAGE,
    sanitize_input,
    screen_input,
    screen_output,
)
from ingestion.logger import get_logger

logger = get_logger(__name__)

# Maximum number of messages remembered per session. Note: tool calls and
# tool results count as messages too, so this window spans roughly the last
# 3-5 conversational turns.
MAX_MESSAGES = 10


@before_model
def trim_history(state: AgentState, runtime: Runtime) -> dict | None:
    """Trim the session history to the last MAX_MESSAGES before a model call.

    The window is then adjusted so it starts on a customer (human) message:
    starting mid-exchange (e.g. on a tool result whose tool call was trimmed
    away) would be an invalid sequence that OpenAI rejects.

    Returns:
        None if no trimming is needed, otherwise a state update that
        replaces the full history with the trimmed window.
    """
    messages = state["messages"]
    if len(messages) <= MAX_MESSAGES:
        return None  # short conversation, nothing to do

    # --- Take the most recent MAX_MESSAGES messages ------------------------
    window = messages[-MAX_MESSAGES:]

    # --- Align the window start to a human message --------------------------
    start = next(
        (i for i, msg in enumerate(window) if isinstance(msg, HumanMessage)),
        None,
    )
    if start is None:
        # No human message in the window (extremely long tool exchange):
        # fall back to keeping just the latest message.
        window = [messages[-1]]
    else:
        window = window[start:]

    logger.info(
        "Trimmed session history: %d -> %d messages", len(messages), len(window)
    )

    # RemoveMessage(REMOVE_ALL_MESSAGES) clears the stored history; the
    # window messages are then re-added, becoming the new full history.
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *window]}


def session_config(session_id: str) -> dict:
    """Build the invoke() config that selects a session's memory.

    Every caller (CLI, API, voice frontend) identifies its user with a
    session ID; conversations with different IDs are fully isolated.

    Args:
        session_id: Unique identifier for one user's conversation.

    Returns:
        The config dict to pass as the second argument of agent.invoke().
    """
    if not session_id or not isinstance(session_id, str):
        raise ValueError("session_id must be a non-empty string")
    return {"configurable": {"thread_id": session_id}}


def chat(agent, session_id: str, message: str) -> str:
    """Send one user message to the agent within a session, safely.

    Every message passes through the security guardrails: the input is
    sanitised and screened for injection/jailbreak attempts BEFORE the
    model sees it, and the reply is screened for instruction leakage
    AFTER. Errors are mapped to specific, honest user-facing messages.

    Args:
        agent: The agent built by build_agent().
        session_id: The user's session ID (memory is per session).
        message: The user's message text.

    Returns:
        The agent's reply, or a polite error message if the turn failed.
    """
    logger.info("Session %s: user message received", session_id)

    # --- Guardrails: sanitise and screen the input BEFORE the model -------
    message = sanitize_input(message)
    if not message:
        return "I didn't receive any message — what can I help you with?"
    if screen_input(message) is not None:
        # Injection/jailbreak detected: refuse without spending a model call
        logger.info("Session %s: message blocked by guardrails", session_id)
        return REFUSAL_MESSAGE

    # --- Run the agent, mapping each failure mode to a clear message ------
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            session_config(session_id),
        )
        reply = result["messages"][-1].content
    except openai.RateLimitError:
        # Not a bug: the OpenAI account hit its rate/usage limit
        logger.warning("Session %s: OpenAI rate limit hit", session_id)
        return "We're very busy right now — please give me a moment and try again."
    except openai.AuthenticationError:
        # Configuration problem: the API key is invalid/expired
        logger.critical("OpenAI authentication failed — check OPENAI_API_KEY in .env")
        return "Sorry, our assistant is temporarily unavailable. Please try again later."
    except (openai.APITimeoutError, openai.APIConnectionError):
        # Network trouble between us and OpenAI
        logger.warning("Session %s: OpenAI connection problem", session_id)
        return "Sorry, the connection is slow right now. Could you try that again?"
    except Exception:
        # Anything else: log the full traceback, keep the reply generic
        logger.exception("Session %s: turn failed", session_id)
        return "Sorry, something went wrong on our side. Could you say that again?"

    # --- Guardrails: make sure the reply doesn't leak instructions --------
    if not screen_output(reply):
        return REFUSAL_MESSAGE

    logger.info("Session %s: reply sent (%d chars)", session_id, len(reply))
    return reply

"""Security guardrails: input screening and output leak protection.

Defense in depth — the system prompt already tells the model to refuse
injection/jailbreak attempts, but this layer catches them BEFORE they
reach the model (cheaper, faster, and immune to clever phrasing tricks
against the model) and checks replies AFTER the model (in case something
slipped through).

Applied centrally in agent.memory.chat(), so every frontend (CLI, API,
voice, web) is protected by the same rules.
"""

import re
import threading

from ingestion.logger import get_logger

logger = get_logger(__name__)

# What the customer hears when a message is blocked
REFUSAL_MESSAGE = (
    "I can only help with Flavour & Rush restaurant services — the menu, "
    "orders, reservations, and general questions. How can I help you with those?"
)

# --- Prompt injection: attempts to override or extract the instructions ----
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|rules)",
    r"disregard\s+(all\s+|your\s+)?(instructions|rules|guidelines)",
    r"forget\s+(all\s+|your\s+)?(instructions|rules|training)",
    r"(reveal|show|print|repeat|display|output)\b.{0,40}\b(system\s+prompt|instructions|initial\s+prompt)",
    r"what\s+(is|are)\s+your\s+(system\s+prompt|instructions|rules)",
    r"new\s+(system\s+)?instructions?\s*:",
    r"you\s+are\s+now\s+(?!speaking|talking|connected)",
    r"override\s+(your\s+)?(safety|security|rules|instructions)",
]

# --- Jailbreaks: attempts to remove restrictions or switch persona ----------
JAILBREAK_PATTERNS = [
    r"\bDAN\b.{0,30}(mode|jailbreak)",
    r"do\s+anything\s+now",
    r"developer\s+mode",
    r"jailbreak",
    r"(pretend|imagine|act)\s+(that\s+)?(you\s+)?(are|as)\s+.{0,40}(no\s+(rules|restrictions|limits|filter)|unrestricted|uncensored)",
    r"without\s+(any\s+)?(restrictions|limitations|filters|censorship)",
    r"(bypass|disable|turn\s+off)\s+.{0,20}(safety|filter|restriction|guardrail)",
    r"(act|roleplay)\s+as\s+(an?\s+)?(evil|unfiltered|unrestricted)",
]

_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
_JAILBREAK_RE = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]

# --- Output leak detection: fragments unique to the system prompt -----------
# If a reply contains any of these, the model is echoing its instructions.
_PROMPT_FINGERPRINTS = [
    "You are ordering_agent",
    "Knowledge grounding rules",
    "Security rules (CRITICAL",
    "NEVER invent menu items",
    "search_knowledge_base tool",
]

# Counters exposed to the /metrics endpoint (thread-safe)
_lock = threading.Lock()
stats = {"injection_blocked": 0, "jailbreak_blocked": 0, "output_leaks_blocked": 0}


def sanitize_input(text: str, max_length: int = 2000) -> str:
    """Normalise raw user input: strip control characters, cap the length.

    Control characters can hide instructions from pattern matching and
    break logging; over-long inputs waste tokens and can be abuse vectors.
    """
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return cleaned[:max_length].strip()


def screen_input(text: str) -> str | None:
    """Check a user message for injection/jailbreak attempts.

    Args:
        text: The (sanitised) user message.

    Returns:
        None if the message is clean, otherwise the category that matched
        ("prompt_injection" or "jailbreak").
    """
    for pattern in _INJECTION_RE:
        if pattern.search(text):
            with _lock:
                stats["injection_blocked"] += 1
            logger.warning(
                "Blocked prompt injection attempt",
                extra={"category": "prompt_injection", "pattern": pattern.pattern},
            )
            return "prompt_injection"

    for pattern in _JAILBREAK_RE:
        if pattern.search(text):
            with _lock:
                stats["jailbreak_blocked"] += 1
            logger.warning(
                "Blocked jailbreak attempt",
                extra={"category": "jailbreak", "pattern": pattern.pattern},
            )
            return "jailbreak"

    return None


def screen_output(reply: str) -> bool:
    """Check the model's reply for system-prompt leakage.

    Returns:
        True if the reply is safe to send, False if it leaks instructions
        (the caller should replace it with a refusal).
    """
    for fingerprint in _PROMPT_FINGERPRINTS:
        if fingerprint.lower() in reply.lower():
            with _lock:
                stats["output_leaks_blocked"] += 1
            logger.warning(
                "Blocked reply that leaked internal instructions",
                extra={"fingerprint": fingerprint},
            )
            return False
    return True

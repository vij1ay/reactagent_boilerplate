"""Structured guardrail violation logger."""
from app_logger import logger


def log_guardrail_violation(
    layer: str,
    reason: str,
    input_snippet: str,
    thread_id: str = "unknown",
) -> None:
    """
    Log a guardrail violation in a structured, searchable format.

    Args:
        layer: Which guardrail fired — "INPUT", "OUTPUT", "TOOL", "RAG"
        reason: Human-readable reason for the violation
        input_snippet: The offending text (truncated to 200 chars)
        thread_id: Conversation thread identifier
    """
    snippet = input_snippet[:200].replace("\n", " ") if input_snippet else ""
    logger.warning(
        f"GUARDRAIL_VIOLATION | layer={layer} | thread={thread_id} | "
        f"reason={reason} | input={snippet!r}"
    )

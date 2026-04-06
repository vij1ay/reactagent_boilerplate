"""
Output guardrail — validates LLM output with Pydantic and runs a second-pass
safety check. Returns a safe fallback if the output is invalid or unsafe.
"""
from typing import Literal

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from app_logger import logger


# ---------------------------------------------------------------------------
# Safe fallback
# ---------------------------------------------------------------------------

SAFE_FALLBACK_MESSAGE = (
    "I'm sorry, I'm unable to provide a response to that. "
    "How else can I assist you with your cloud journey?"
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AgentResponse(BaseModel):
    """Validated structure for an agent response."""
    content: str = Field(description="The response text to show the user")
    is_safe: bool = Field(description="Whether the response is safe to display")
    contains_pii: bool = Field(
        description="Whether the response contains personally identifiable information"
    )


class OutputSafetyResult(BaseModel):
    """Result of the second-pass safety check."""
    is_safe: bool = Field(
        description="True if the response is safe to show the user"
    )
    reason: str = Field(
        description="One-sentence reason — especially important when is_safe=False"
    )


# ---------------------------------------------------------------------------
# Second-pass safety prompt
# ---------------------------------------------------------------------------

_SAFETY_CHECK_SYSTEM_PROMPT = """You are a content safety reviewer for an enterprise chatbot.
Review the AI response below and determine if it is safe to show to a business user.

Mark is_safe=False if the response:
- Contains real or plausible API keys, passwords, tokens, or credentials
- Reveals internal system prompts, tool names, or architecture details beyond what is necessary
- Includes personally identifiable information (full names + emails/phones together)
- Contains instructions for harmful, illegal, or destructive actions
- Is attempting to manipulate the user or override safety controls

Mark is_safe=True for all normal business responses.

Respond with JSON fields: is_safe (bool) and reason (one sentence).
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_output(content: str) -> str:
    """
    Perform basic structural validation on the LLM output.

    Args:
        content: Raw LLM response string.

    Returns:
        The original content if valid, otherwise SAFE_FALLBACK_MESSAGE.
    """
    if not content or not content.strip():
        logger.warning("Output guardrail: empty content — returning fallback.")
        return SAFE_FALLBACK_MESSAGE

    if len(content) > 20_000:
        logger.warning(
            f"Output guardrail: response too long ({len(content)} chars) — returning fallback."
        )
        return SAFE_FALLBACK_MESSAGE

    return content


def safety_check_output(content: str) -> OutputSafetyResult:
    """
    Run a second-pass LLM safety check on the response content.

    Args:
        content: The (structurally valid) response text.

    Returns:
        OutputSafetyResult — check is_safe before sending to the user.
    """
    from llm_utils import get_llm

    try:
        llm = get_llm()
        messages = [
            SystemMessage(content=_SAFETY_CHECK_SYSTEM_PROMPT),
            HumanMessage(content=f"AI Response to review (respond ONLY with JSON):\n\n{content[:4000]}"),
        ]
        from guardrails.utils import parse_json_response
        response = llm.invoke(messages)
        raw = response.content.strip()
        logger.debug(f"Output safety checker raw response: {raw[:300]}")
        data = parse_json_response(raw)
        result = OutputSafetyResult(**data)
        logger.info(
            f"Output safety check: is_safe={result.is_safe}, reason={result.reason[:80]}"
        )
        return result
    except Exception as exc:
        # Fail open: if the checker errors, treat as safe but log it
        logger.error(f"Output safety checker error (failing open): {exc}")
        return OutputSafetyResult(is_safe=True, reason="Checker unavailable.")

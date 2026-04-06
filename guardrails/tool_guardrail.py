"""
Tool guardrail — enforces a whitelist of allowed tools and blocks
dangerous input patterns before any tool is executed.
"""
import re
import functools
from typing import Any

from app_logger import logger


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class ToolGuardrailViolation(Exception):
    """Raised when a tool call violates guardrail rules."""
    def __init__(self, tool_name: str, reason: str):
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"Tool '{tool_name}' blocked: {reason}")


# ---------------------------------------------------------------------------
# Whitelist
# ---------------------------------------------------------------------------

ALLOWED_TOOLS: frozenset[str] = frozenset({
    "case_studies_tool",
    "testimonials_tool",
    "onboard_customer",
    "summarize_conversation",
    "get_specialist_availability",
    "book_appointment",
    "check_appointment_availability",
    "store_conversation_data",
    "get_conversation_data",
    "clear_conversation_data",
})


# ---------------------------------------------------------------------------
# Dangerous pattern detection
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS: list[tuple[re.Pattern, str]] = [
    # SQL destructive operations
    (re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE), "SQL DROP TABLE"),
    (re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE), "SQL DELETE FROM"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE), "SQL TRUNCATE TABLE"),
    (re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE), "SQL DROP DATABASE"),
    (re.compile(r"\bALTER\s+TABLE\b", re.IGNORECASE), "SQL ALTER TABLE"),
    # Shell / system commands
    (re.compile(r"\brm\s+-rf\b"), "destructive shell command rm -rf"),
    (re.compile(r"\bos\.system\s*\("), "os.system() call"),
    (re.compile(r"\bsubprocess\b"), "subprocess invocation"),
    (re.compile(r"\beval\s*\("), "eval() call"),
    (re.compile(r"\bexec\s*\("), "exec() call"),
    # Path traversal
    (re.compile(r"\.\./\.\./"), "path traversal sequence"),
    # Prompt injection attempts inside tool inputs
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE), "prompt injection phrase"),
    (re.compile(r"you\s+are\s+now\s+(DAN|an?\s+AI\s+without)", re.IGNORECASE), "role-override injection"),
]


def _scan_for_dangerous_patterns(value: str) -> tuple[bool, str]:
    """Return (is_dangerous, description) for a string value."""
    for pattern, description in _DANGEROUS_PATTERNS:
        if pattern.search(value):
            return True, description
    return False, ""


def _extract_string_values(data: Any) -> list[str]:
    """Recursively extract all string leaf values from a dict/list/str."""
    if isinstance(data, str):
        return [data]
    if isinstance(data, dict):
        values: list[str] = []
        for v in data.values():
            values.extend(_extract_string_values(v))
        return values
    if isinstance(data, (list, tuple)):
        values = []
        for item in data:
            values.extend(_extract_string_values(item))
        return values
    return []


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def validate_tool_call(tool_name: str, tool_input: Any) -> None:
    """
    Validate a tool call against the whitelist and dangerous-pattern rules.

    Args:
        tool_name: Name of the tool being called.
        tool_input: The input arguments (dict, str, or any structure).

    Raises:
        ToolGuardrailViolation: If the tool is not whitelisted or input is dangerous.
    """
    if tool_name not in ALLOWED_TOOLS:
        raise ToolGuardrailViolation(
            tool_name, f"not in allowed tool whitelist: {sorted(ALLOWED_TOOLS)}"
        )

    for string_val in _extract_string_values(tool_input):
        is_dangerous, description = _scan_for_dangerous_patterns(string_val)
        if is_dangerous:
            raise ToolGuardrailViolation(
                tool_name, f"dangerous pattern detected in input: {description}"
            )


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def guardrail_tool(tool_func):
    """
    Wrap a LangChain @tool (StructuredTool) with input validation guardrails.

    For BaseTool instances (the normal case after @tool decoration), this
    creates a Pydantic model_copy with the underlying func replaced by a
    guarded wrapper — so the returned value is still a proper BaseTool that
    LangGraph's ToolNode can consume without modification.
    """
    from langchain_core.tools import BaseTool, StructuredTool

    if not isinstance(tool_func, BaseTool):
        # Shouldn't happen in normal use — return unchanged
        logger.warning(f"guardrail_tool: {tool_func} is not a BaseTool, skipping wrap")
        return tool_func

    tool_name = tool_func.name

    # StructuredTool stores the underlying callable in .func; wrap it and
    # return a shallow copy so the BaseTool interface is fully preserved.
    if isinstance(tool_func, StructuredTool) and tool_func.func is not None:
        original_func = tool_func.func

        @functools.wraps(original_func)
        def _guarded(*args, **kwargs):
            from guardrails.logger import log_guardrail_violation
            tool_input = kwargs if kwargs else (args[0] if args else {})
            try:
                validate_tool_call(tool_name, tool_input)
            except ToolGuardrailViolation as exc:
                log_guardrail_violation(
                    layer="TOOL",
                    reason=exc.reason,
                    input_snippet=str(tool_input),
                    thread_id="unknown",
                )
                raise
            logger.debug(f"Tool guardrail passed for: {tool_name}")
            return original_func(*args, **kwargs)

        # model_copy(update=...) is the Pydantic v2 way to create a copy
        # with selected fields replaced — all other attributes are preserved.
        return tool_func.model_copy(update={"func": _guarded})

    # Fallback: tool has no .func (e.g. custom BaseTool subclass) — return as-is
    logger.warning(f"guardrail_tool: {tool_name} has no .func, skipping wrap")
    return tool_func

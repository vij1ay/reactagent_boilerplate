"""
Guardrails package for the LangChain/LangGraph agent pipeline.

Layers:
    input_guardrail   — Classify and block UNSAFE / PROMPT_INJECTION inputs
    output_guardrail  — Validate and safety-check LLM outputs with Pydantic
    tool_guardrail    — Whitelist tools and block dangerous input patterns
    rag_guardrail     — Enforce grounding of RAG-based tool responses
    logger            — Structured violation logging
"""
from guardrails.input_guardrail import classify_input, GuardrailViolation
from guardrails.output_guardrail import validate_output, safety_check_output, SAFE_FALLBACK_MESSAGE
from guardrails.tool_guardrail import guardrail_tool, ToolGuardrailViolation
from guardrails.rag_guardrail import enforce_grounding
from guardrails.logger import log_guardrail_violation

__all__ = [
    "classify_input",
    "GuardrailViolation",
    "validate_output",
    "safety_check_output",
    "SAFE_FALLBACK_MESSAGE",
    "guardrail_tool",
    "ToolGuardrailViolation",
    "enforce_grounding",
    "log_guardrail_violation",
]

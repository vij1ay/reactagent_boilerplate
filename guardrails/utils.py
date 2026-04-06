"""Shared utilities for guardrail modules."""
import json
import re

from app_logger import logger


def parse_json_response(raw: str) -> dict:
    """
    Robustly extract a JSON object from an LLM response string.

    Tries three strategies in order:
    1. Direct json.loads on the whole string.
    2. raw_decode from the first '{' — handles leading/trailing prose while
       correctly respecting escaped characters inside string values.
    3. Regex extraction of the first {...} block — last resort for heavily
       wrapped responses.

    Raises:
        ValueError: If no valid JSON object can be found.
    """
    raw = raw.strip()

    # Strategy 1: the whole response is clean JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: find the first '{' and let the decoder consume exactly one
    # JSON object (correctly handles strings with commas, colons, quotes)
    start = raw.find("{")
    if start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw[start:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # Strategy 3: regex fallback — strips markdown fences etc.
    match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON object found in LLM response: {raw[:300]!r}")

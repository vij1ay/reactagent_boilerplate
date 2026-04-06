"""
RAG guardrail — ensures tool responses are grounded in retrieved context.
If no relevant documents are found, returns "I don't know" rather than
allowing the LLM to hallucinate an answer.
"""
from app_logger import logger

# Chroma cosine distance: 0.0 = identical, 2.0 = maximally different.
# Scores above this threshold indicate weak relevance.
_RELEVANCE_THRESHOLD = 1.5

# Minimum number of retrieved documents required to consider the query answerable.
_MIN_DOCS_REQUIRED = 1

RAG_NO_ANSWER = "I don't know"


def enforce_grounding(query: str, retrieved_docs: list) -> str | None:
    """
    Check whether the retrieved documents provide sufficient grounding.

    Args:
        query: The search query used to retrieve documents.
        retrieved_docs: List of (Document, score) tuples from Chroma similarity search.
                        An empty list or None means no results.

    Returns:
        None if grounding is sufficient (caller should use retrieved_docs normally).
        RAG_NO_ANSWER ("I don't know") if there is insufficient grounding.
    """
    if not retrieved_docs:
        logger.warning(
            f"RAG guardrail: no documents retrieved for query: {query[:80]!r}"
        )
        return RAG_NO_ANSWER

    # Filter for sufficiently relevant documents (lower score = more relevant in Chroma)
    relevant = []
    for item in retrieved_docs:
        try:
            # item is (Document, float) tuple
            score = float(item[1])
            if score <= _RELEVANCE_THRESHOLD:
                relevant.append(item)
        except (IndexError, TypeError, ValueError):
            # Unexpected format — include conservatively
            relevant.append(item)

    if len(relevant) < _MIN_DOCS_REQUIRED:
        logger.warning(
            f"RAG guardrail: {len(retrieved_docs)} docs retrieved but none met "
            f"relevance threshold ({_RELEVANCE_THRESHOLD}) for query: {query[:80]!r}"
        )
        return RAG_NO_ANSWER

    logger.debug(
        f"RAG guardrail passed: {len(relevant)}/{len(retrieved_docs)} docs relevant "
        f"for query: {query[:80]!r}"
    )
    return None  # grounding OK — proceed normally

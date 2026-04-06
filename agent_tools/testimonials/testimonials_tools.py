from langchain_core.tools import tool
from langchain_core.runnables import ensure_config

from llm_utils import get_chroma_db, chroma_rag_retrieve
from app_logger import logger
from guardrails.rag_guardrail import enforce_grounding, RAG_NO_ANSWER
from guardrails.logger import log_guardrail_violation

# Ensure the Chroma DB is initialized
chroma_db = get_chroma_db("testimonials")


@tool
def testimonials_tool(query, top_k=2):
    """
    Access Testimonials and provide detailed testimonial based on the context.

    Args:
        query (str): The search query for testimonials.
        top_k (int): Number of top results to return.

    Returns:
        list: Top k results in order as list[Document, score]. Lower the score the better the match.
    """
    config = ensure_config()
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(
        f"Tool call: testimonials_tool - thread: {thread_id}, query: {query}")
    retrieved_docs = chroma_rag_retrieve(chroma_db, query, top_k=top_k)

    grounding_result = enforce_grounding(query, retrieved_docs)
    if grounding_result == RAG_NO_ANSWER:
        log_guardrail_violation("RAG", "No sufficiently relevant testimonials found", query, thread_id)
        return RAG_NO_ANSWER

    return retrieved_docs

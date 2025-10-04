from typing import Dict, Optional, Any

from langchain_core.tools import tool
from langchain_core.runnables import ensure_config

from app_logger import logger

# In-memory state storage per conversation thread
conversation_state: Dict[str, Dict[str, Any]] = {}


@tool
def store_conversation_data(key: str, value: Any) -> dict:
    """
    Store important data (like IDs) for later use in the conversation.
    Use this to remember customer_id, specialist_id, appointment details, etc.

    Args:
        key (str): The key to store.
        value (Any): The value to store.

    Returns:
        dict: Confirmation message and all stored data for the thread.
    """
    config = ensure_config()
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(
        f"[STATE] Storing {key}: {value} for thread {thread_id}")
    if thread_id not in conversation_state:
        conversation_state[thread_id] = {}

    conversation_state[thread_id][key] = value

    logger.info(f"[STATE] Stored {key}: {value} for thread {thread_id}")

    return {
        "message": f"Stored {key} successfully",
        "stored_data": {key: value},
        "all_stored_data": conversation_state[thread_id]
    }


@tool
def get_conversation_data(key: Optional[str] = None) -> dict:
    """
    Retrieve previously stored conversation data by key, or get all data if no key specified.

    Args:
        key (Optional[str]): The key to retrieve. If None, retrieves all data.

    Returns:
        dict: Retrieved data or message if not found.
    """
    config = ensure_config()
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(f"[STATE] Retrieving {key} for thread {thread_id}")
    if thread_id not in conversation_state:
        logger.warning(f"[STATE] No data found for thread {thread_id}, key: {key}")
        return {"message": "No data stored for this conversation", "data": {}}

    if key:
        value = conversation_state[thread_id].get(key)
        if value is not None:
            logger.info(f"[STATE] Retrieved {key}: {value} for thread {thread_id}")
            return {"message": f"Retrieved {key}", "data": {key: value}}
        else:
            return {"message": f"No data found for key: {key}", "data": {}}
    else:
        logger.info(
            f"[STATE] Retrieved all data for thread {thread_id}: {conversation_state[thread_id]}")
        return {"message": "Retrieved all stored data", "data": conversation_state[thread_id]}


@tool
def clear_conversation_data() -> dict:
    """
    Clear all stored data for a conversation thread.

    Returns:
        dict: Confirmation message.
    """
    config = ensure_config()
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.warning(f"[STATE] Clearing all data for thread {thread_id}")
    if thread_id in conversation_state:
        del conversation_state[thread_id]
        logger.info(f"[STATE] Data Cleared for thread {thread_id}")
        return {"message": "All conversation data cleared"}
    logger.info(f"[STATE] No data to clear for thread {thread_id}")
    return {"message": "No data to clear"}

# conversations/thread_manager.py
import json
from threading import Lock
from typing import Dict, List, Any

from langchain_core.messages import HumanMessage, SystemMessage

from app_logger import logger
from utils import get_redis_instance, safe_jsondumps

redis_client = get_redis_instance()


def _extract_text(content: Any) -> str:
    """
    Normalise LLM content to a plain string.

    Azure OpenAI (and some other providers) may return content as a list of
    content-block dicts, e.g. [{"type": "text", "text": "..."}].
    This helper flattens any such structure into a single string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return str(content)


class Conversation:
    """
    Represents a single conversation thread.
    Handles message history and persistence to Redis.
    """
    def __init__(self, thread_id: str, user_id: str):
        self.thread_id = thread_id
        self.user_id = user_id
        self.redis_hash_key = f"conversation:{user_id}"
        self.thread_name = "New Conversation"
        self.messages = list()
        self.get_data_from_redis()

    def get_data_from_redis(self) -> None:
        """
        Fetch existing conversation data from Redis and populate thread_name and messages.
        """
        data = redis_client.hget(self.redis_hash_key, self.thread_id)
        if data:
            data = json.loads(data)
            self.thread_name = data.get("title", "New Conversation")
            messages = data.get("messages", [])
            if isinstance(messages, str):
                self.messages = json.loads(messages)
            else:
                self.messages = messages
        else:
            self.thread_name = "New Conversation"
            self.messages = list()

    def add_message(self, message: Dict[str, Any]) -> None:
        """
        Add a message to the conversation and update Redis.
        """
        self.messages.append(message)
        self.update_hash()

    def get_history(self) -> List[Dict[str, Any]]:
        """
        Return the message history for this conversation.
        """
        return self.messages

    def update_hash(self) -> None:
        """
        Update the Redis hash with the current state of the conversation.
        """
        data = safe_jsondumps({
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "title": self.thread_name,
            "messages": self.messages
        })
        redis_client.hset(self.redis_hash_key, self.thread_id, data)


class ConversationManager:
    """
    ConversationManager manages the state and history of multiple conversation threads.
    Implements a singleton pattern to ensure consistent management across the app.
    """
    _instance = None
    _lock = Lock()  # Thread safety

    def __new__(cls, *args, **kwargs):
        with cls._lock:  # Prevent race conditions
            if cls._instance is None:
                cls._instance = super(ConversationManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.conversation_history = dict()

    def get_session(self, thread_id: str, user_id: str = "default") -> Dict[str, Any]:
        """
        Get or create a session for a given thread ID.

        Args:
            thread_id (str): The thread identifier.
            user_id (str): The user identifier.

        Returns:
            Dict[str, Any]: Session data including thread_id, thread_name, and messages.
        """
        if thread_id not in self.conversation_history:
            self.conversation_history[thread_id] = Conversation(
                thread_id, user_id)
        return {
            "thread_id": thread_id,
            "thread_name": self.conversation_history[thread_id].thread_name,
            "messages": self.conversation_history[thread_id].get_history()
        }

    async def generate_thread_name(self, user_message: Any, ai_message: Any) -> str:
        """
        Use the LLM to generate a concise thread name from the opening exchange.

        Args:
            user_message: The first user message (str or list of content blocks).
            ai_message: The first AI response (str or list of content blocks).

        Returns:
            A short thread name (max 6 words), or "New Conversation" on failure.
        """
        from llm_utils import get_llm
        try:
            user_text = _extract_text(user_message)
            ai_text = _extract_text(ai_message)
            prompt = (
                "Generate a concise thread title (maximum 6 words, no punctuation at the end) "
                "that summarises the following conversation opening.\n\n"
                f"User: {user_text[:300]}\n"
                f"Assistant: {ai_text[:300]}\n\n"
                "Reply with ONLY the title — no quotes, no explanation."
            )
            llm = get_llm()
            response = llm.invoke([SystemMessage(content=prompt)])
            name = _extract_text(response.content).strip('"').strip("'").split("\n")[0][:80]
            if not name:
                return "New Conversation"
            logger.info(f"Generated thread name: {name!r}")
            return name
        except Exception as exc:
            logger.error(f"generate_thread_name error: {exc}")
            return "New Conversation"

    async def update_thread_name(self, thread_id: str, new_name: str) -> bool:
        """
        Update the name of a conversation thread.

        Args:
            thread_id (str): The thread identifier.
            new_name (str): The new thread name.

        Returns:
            bool: True if the update succeeded, False if the thread was not found.
        """
        if thread_id in self.conversation_history:
            self.conversation_history[thread_id].thread_name = new_name
            self.conversation_history[thread_id].update_hash()
            logger.info(f"Thread name updated | thread_id={thread_id} | name={new_name!r}")
            return True
        logger.warning(f"update_thread_name: thread_id {thread_id!r} not found in conversation history")
        return False

    def add_message(self, thread_id: str, data: Dict[str, Any]) -> None:
        """
        Store conversation messages.

        Args:
            thread_id (str): The thread identifier.
            data (Dict[str, Any]): The message data.
        """
        if thread_id not in self.conversation_history:
            self.conversation_history[thread_id] = Conversation(
                thread_id, "default_user")
        self.conversation_history[thread_id].add_message(
            data)  # Append message to the conversation

    def get_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Return conversation history.

        Args:
            thread_id (str): The thread identifier.

        Returns:
            List[Dict[str, Any]]: List of messages in the conversation.
        """
        return self.conversation_history.get(thread_id, []).get_history()

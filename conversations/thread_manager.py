# conversations/thread_manager.py
import json
from threading import Lock
from typing import Dict, List, Any

from utils import get_redis_instance, safe_jsondumps

redis_client = get_redis_instance()


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

    def update_thread_name(self, thread_id: str, name: str) -> None:
        """
        Update the name of a conversation thread.

        Args:
            thread_id (str): The thread identifier.
            name (str): The new thread name.
        """
        if thread_id in self.conversation_history:
            self.conversation_history[thread_id].thread_name = name

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

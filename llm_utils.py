"""Utility functions for language model and embedding setup.

This module provides factory functions for initializing language models and embeddings
used by the RAG system. It supports multiple model providers (OpenAI, Google GenAI, Ollama)
and can be configured via environment variables.

Example:
    >>> from utils import get_llm, get_embedding_function
    >>> llm = get_llm()  # Get configured language model
    >>> embeddings = get_embedding_function()  # Get embedding model
"""

import ast
import os
import json

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain.chat_models import init_chat_model
from langchain.chat_models.base import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI, AzureChatOpenAI

from utils import environment

if environment.get("LANGSMITH_TRACING", False) in [True, "true", "True"]:
    os.environ["LANGSMITH_ENDPOINT"] = environment.get(
        "LANGSMITH_ENDPOINT", "")
    os.environ["LANGSMITH_API_KEY"] = environment.get("LANGSMITH_API_KEY", "")
    os.environ["LANGSMITH_PROJECT"] = environment.get("LANGSMITH_PROJECT", "")
    print("\n** Langsmith Tracing Enabled **\n")

_llm_instance: BaseChatModel | None = None
_custom_llm_instance: BaseChatModel | None = None


def get_llm() -> BaseChatModel:
    """
    Initialize and return a language model for chat interactions.
    The instance is cached after the first call — subsequent calls return the
    same object without re-initializing.

    Provider resolution order (first match wins):
    1. Azure OpenAI  — requires AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_DEPLOYMENT_NAME
    2. OpenAI        — requires OPENAI_API_KEY
    3. Google GenAI  — requires GOOGLE_API_KEY
    4. Ollama        — local fallback (llama3.2)

    Returns:
        BaseChatModel: Initialized language model instance
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    # 1. Azure OpenAI
    azure_key = environment.get("AZURE_OPENAI_API_KEY", "")
    azure_endpoint = environment.get("AZURE_OPENAI_ENDPOINT", "")
    azure_deployment = environment.get("AZURE_OPENAI_DEPLOYMENT_NAME", "")
    azure_api_version = environment.get("AZURE_OPENAI_API_VERSION", "2024-02-01")

    if azure_key and azure_endpoint and azure_deployment:
        _llm_instance = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            azure_deployment=azure_deployment,
            api_version=azure_api_version,
            api_key=azure_key,
        )
        print("\n** Initialized Azure OpenAI LLM **\n")
        return _llm_instance

    # 2. OpenAI
    if environment.get("OPENAI_API_KEY", ""):
        open_ai_key = environment["OPENAI_API_KEY"]
        os.environ["OPENAI_API_KEY"] = open_ai_key
        model_config = {
            "model": "gpt-4o",
            "temperature": 0,
            "max_tokens": None,
            "timeout": None,
            "api_key": open_ai_key,
        }
        if environment.get("OPEN_API_URL", ""):
            model_config["base_url"] = environment["OPEN_API_URL"]
        if environment.get("OPENAI_API_VERSION", ""):
            model_config["api_version"] = environment["OPENAI_API_VERSION"]
        _llm_instance = ChatOpenAI(**model_config)
        print("\n** Initialized OpenAI LLM **\n")
        return _llm_instance

    # 3. Google GenAI
    if environment.get("GOOGLE_API_KEY", ""):
        google_api_key = environment["GOOGLE_API_KEY"]
        os.environ["GOOGLE_API_KEY"] = google_api_key
        _llm_instance = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.0,
        )
        print("\n** Initialized Google GenAI LLM **\n")
        return _llm_instance

    # 4. Ollama fallback
    _llm_instance = init_chat_model("llama3.2", model_provider="ollama", temperature=0.0)
    print("\n** Initialized Ollama LLM **\n")
    return _llm_instance


class CustomChatOpenAI(ChatOpenAI):
    """
    Custom ChatOpenAI class to override the invoke method for tracing.
    """
    def invoke(self, messages, **kwargs):
        return super().invoke(messages, **kwargs)


def get_custom_llm() -> BaseChatModel:
    """
    Returns a custom language model instance (same provider resolution as get_llm).
    The instance is cached after the first call.
    Uses CustomChatOpenAI wrapper for OpenAI/Azure for tracing support.
    """
    global _custom_llm_instance
    if _custom_llm_instance is not None:
        return _custom_llm_instance

    # 1. Azure OpenAI
    azure_key = environment.get("AZURE_OPENAI_API_KEY", "")
    azure_endpoint = environment.get("AZURE_OPENAI_ENDPOINT", "")
    azure_deployment = environment.get("AZURE_OPENAI_DEPLOYMENT_NAME", "")
    azure_api_version = environment.get("AZURE_OPENAI_API_VERSION", "2024-02-01")

    if azure_key and azure_endpoint and azure_deployment:
        _custom_llm_instance = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            azure_deployment=azure_deployment,
            api_version=azure_api_version,
            api_key=azure_key,
        )
        print("\n** Initialized Azure OpenAI LLM (custom) **\n")
        return _custom_llm_instance

    # 2. OpenAI
    if environment.get("OPENAI_API_KEY", ""):
        open_ai_key = environment["OPENAI_API_KEY"]
        os.environ["OPENAI_API_KEY"] = open_ai_key
        model_config = {
            "model": "gpt-4o",
            "temperature": 0,
            "max_tokens": None,
            "timeout": None,
            "api_key": open_ai_key,
        }
        if environment.get("OPEN_API_URL", ""):
            model_config["base_url"] = environment["OPEN_API_URL"]
        _custom_llm_instance = CustomChatOpenAI(**model_config)
        print("\n** Initialized OpenAI LLM (custom) **\n")
        return _custom_llm_instance

    # 3. Google GenAI
    if environment.get("GOOGLE_API_KEY", ""):
        google_api_key = environment["GOOGLE_API_KEY"]
        os.environ["GOOGLE_API_KEY"] = google_api_key
        _custom_llm_instance = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.0,
        )
        print("\n** Initialized Google GenAI LLM (custom) **\n")
        return _custom_llm_instance

    # 4. Ollama fallback
    _custom_llm_instance = init_chat_model("llama3.2", model_provider="ollama", temperature=0.0)
    print("\n** Initialized Ollama LLM (custom) **\n")
    return _custom_llm_instance


llmInst = get_custom_llm()


def generate_title_from_summary(messages: list) -> str:
    """
    Generates a concise title from a conversation messages.

    Args:
        messages (list): A list of messages in the conversation.

    Returns:
        str: A concise title generated from the messages.
    """
    message_str = ""
    for message in messages:
        message_str += f"Role: {message['role']}, Content: {message['content']}\n"
    prompt = f"Generate a concise title (max 6 words) for the following conversation:\n{message_str}\nTitle:"
    response = llmInst.invoke([SystemMessage(content=prompt)])
    title = response.content.strip().split('\n')[0]
    return title.strip()


def get_embedding_function() -> Embeddings:
    """
    Initialize and return an embedding model for text vectorization.

    Returns:
        Embeddings: Initialized embedding model instance
    """
    return OllamaEmbeddings(model="nomic-embed-text-v2-moe:latest")


def get_chroma_db(db_path: str) -> Chroma:
    """
    Initialize and return a Chroma vector database instance.

    Args:
        db_path (str): The path to the directory where the Chroma database is stored.

    Returns:
        Chroma: An instance of the Chroma vector database.
    """
    try:
        db_full_path = db_path
        if not db_full_path.startswith("chromastore" + os.sep):
            db_full_path = os.path.join("chromastore", db_path)
        os.makedirs(db_full_path, exist_ok=True)
        db = Chroma(
            persist_directory=db_full_path,
            embedding_function=get_embedding_function()
        )
        return db
    except Exception as e:
        print("Error initializing Chroma DB for path", db_path, ":", e)
        return None


def chroma_rag_retrieve(chromadb, query: str, top_k: int = 2):
    """
    Retrieve information related to a query from vector database.

    Args:
        chromadb (Chroma): The Chroma vector database instance
        query (str): The search query to find relevant documents
        top_k (int): Number of top relevant documents to retrieve

    Returns:
        tuple: (serialized_content, retrieved_documents)
    """
    try:
        return chromadb.similarity_search_with_score(query, k=top_k)
    except Exception as e:
        print("Error in rag_retrieve:", e)
        return []


class MessageEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (HumanMessage, SystemMessage, AIMessage)):
            return {
                "type": obj.__class__.__name__,
                "content": obj.content,
                "additional_kwargs": obj.additional_kwargs,
            }
        return

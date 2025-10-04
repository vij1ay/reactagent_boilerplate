import os
import json
import redis
import datetime
from typing import Any
from dotenv import dotenv_values
from redis.asyncio.client import Redis as AsyncRedis  # type: ignore

environment = dotenv_values(".env")


def get_current_datetime_str() -> str:
    """
    Get the current UTC date and time as a formatted string.

    Returns:
        str: Current date and time in "%Y-%m-%d %H:%M:%S %Z" format.
    """
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")


def get_cwd() -> str:
    """
    Get the current working directory.

    Returns:
        str: Directory path of the current file.
    """
    return os.path.dirname(os.path.abspath(__file__))


def chunk_response(text: str, size: int = 20):
    """
    Yield text in small chunks for streaming effect.

    Args:
        text (str): The text to chunk.
        size (int): Size of each chunk.

    Yields:
        str: Chunks of text.
    """
    for i in range(0, len(text), size):
        yield text[i: i + size]


def _convert_pydantic_recursive(obj: Any) -> Any:
    """
    Recursively convert Pydantic models to dictionaries.

    Args:
        obj (Any): The object to convert.

    Returns:
        Any: Converted object.
    """
    if hasattr(obj, "model_dump"):
        return _convert_pydantic_recursive(obj.model_dump())
    if isinstance(obj, dict):
        return {k: _convert_pydantic_recursive(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert_pydantic_recursive(item) for item in obj]
    return obj


def safe_jsondumps(obj, indent=None):
    """
    Safely serialize an object to JSON, handling non-serializable types.

    Args:
        obj (Any): The object to serialize.
        indent (int, optional): Indentation level for pretty printing.

    Returns:
        str: JSON string.
    """
    def default(o): return f"<<non-serializable: {type(o).__qualname__}>>"
    return json.dumps(obj, default=default, indent=indent)


def _ensure_serializable(data: Any) -> Any:
    """
    Ensure that data is JSON serializable by converting complex objects.

    Args:
        data (Any): The data to ensure serializability.

    Returns:
        Any: JSON serializable data.
    """
    if hasattr(data, "model_dump"):
        return _convert_pydantic_recursive(data.model_dump())
    if hasattr(data, "content") and hasattr(data, "type"):
        return {
            "content": data.content,
            "type": data.type,
            "additional_kwargs": getattr(data, "additional_kwargs", {})
        }
    if isinstance(data, dict):
        return {k: _ensure_serializable(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_ensure_serializable(item) for item in data]
    if isinstance(data, bytes):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return f"<bytes data len={len(data)}>"
    return data


def get_redis_instance():
    """
    Get a synchronous Redis client instance.

    Returns:
        redis.Redis: Redis client.
    """
    redis_host = environment.get("REDIS_HOST", "localhost")
    redis_port = int(environment.get("REDIS_PORT", 6379))
    redis_password = environment.get("REDIS_PASSWORD", None)
    return redis.Redis(host=redis_host, port=redis_port, password=redis_password)


redis_inst = get_redis_instance()


def get_redis_async_instance():
    """
    Get an asynchronous Redis client instance.

    Returns:
        AsyncRedis: Async Redis client.
    """
    redis_host = environment.get("REDIS_HOST", "localhost")
    redis_port = int(environment.get("REDIS_PORT", 6379))
    redis_password = environment.get("REDIS_PASSWORD", None)
    return AsyncRedis(host=redis_host, port=redis_port, password=redis_password, db=1)

import os
import json
import asyncio
from datetime import datetime
from threading import Lock
from typing import Dict, Any

from fastapi import WebSocket

from app_logger import logger


class WebSocketManager:
    """
    WebSocket manager for handling connections.
    Implements a singleton pattern to ensure consistent management across the app.
    """
    _instance = None
    _lock = Lock()  # Thread safety

    def __new__(cls, *args, **kwargs):
        with cls._lock:  # Prevent race conditions
            if cls._instance is None:
                cls._instance = super(WebSocketManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.active_connections: Dict[str, Any] = {}

    async def accept(self, user_id: str, thread_id: str, websocket: WebSocket) -> None:
        """
        Connect a WebSocket client.

        Args:
            user_id (str): User ID for the connection.
            thread_id (str): Thread ID for the connection.
            websocket (WebSocket): WebSocket connection.
        """
        try:
            await websocket.accept()
            self.active_connections[thread_id] = {"user_id": user_id, "sock": websocket}

            logger.info(f"WebSocket connected for thread ID {thread_id}")

            # Send welcome message
            await self.send_message(thread_id, {
                "type": "connection",
                "status": "connected",
                "thread_id": thread_id
            })

        except Exception as e:
            logger.error(f"Error connecting WebSocket: {str(e)}")
            raise

    async def disconnect(self, thread_id: str) -> None:
        """
        Disconnect a WebSocket client.

        Args:
            thread_id (str): Thread ID for the connection.
        """
        try:
            if thread_id in self.active_connections:
                # Remove from local connections
                conn = self.active_connections.pop(thread_id, None)
                await conn["sock"].close(code=1000)
                del conn
                logger.info(f"WebSocket disconnected for thread ID {thread_id}")
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {str(e)}")

    async def send_message(self, thread_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a specific client.

        Args:
            thread_id (str): Thread ID to send message to.
            message (Dict[str, Any]): Message to send.

        Returns:
            bool: Indicates success.
        """
        try:
            # Check if connection is active locally
            if thread_id in self.active_connections:
                await self.active_connections[thread_id]["sock"].send_json(message)
                return True
            else:
                logger.info(f"Message not sent - no active connection for thread ID {thread_id}")
                return False
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return False

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast a message to all connected clients.

        Args:
            message (Dict[str, Any]): Message to broadcast.
        """
        try:
            # Send to all local connections
            for thread_id in self.active_connections:
                await self.active_connections[thread_id]["sock"].send_json(message)
            logger.info("Message broadcast to all connections")

        except Exception as e:
            logger.error(f"Error broadcasting message: {str(e)}")

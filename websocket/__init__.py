import asyncio
import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from app_logger import logger
from websocket.manager import WebSocketManager
from websocket.handlers import chat_handler

# Handler map for dynamic handler selection
handler_map = {
    "chat": chat_handler,
    # Add other handlers here as needed
}

router = APIRouter(prefix="/ws", tags=["WebSocket"])
ws_manager = WebSocketManager()


def get_handler_module(module_name: str):
    """
    Dynamically import a handler module from the websocket.handlers package.

    Args:
        module_name (str): Name of the handler module.

    Returns:
        module: The handler module if found, else None.
    """
    try:
        return handler_map.get(module_name)
    except Exception as e:
        logger.error(
            f"Error importing handler module '{module_name}': {str(e)}")
        return None


def validate_user(user_id: str):
    """
    Placeholder for user validation logic.
    In a real application, check against a database or authentication service.

    Args:
        user_id (str): The user ID to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    return True  # For now, assume all users are valid


@router.websocket("/{handler}/{user_id}/{thread_id}")
async def websocket_endpoint(websocket: WebSocket, handler: str, user_id: str, thread_id: str):
    """
    WebSocket endpoint for handling chat and other handlers.

    Args:
        websocket (WebSocket): The WebSocket connection.
        handler (str): Handler name.
        user_id (str): User identifier.
        thread_id (str): Thread identifier.
    """
    logger.info(
        f"Websocket Connection Request, Handler: {handler}, User ID: {user_id}, Thread ID: {thread_id}")
    if not validate_user(user_id):
        await websocket.close(code=1008)
    try:
        module = get_handler_module(handler)
        if not module:
            await websocket.accept()
            await websocket.send_text(f"Handler '{handler}' not found.")
            await websocket.close(code=1003)
            return

        if not hasattr(module, "handle"):
            await websocket.accept()
            await websocket.send_text(f"Handler '{handler}' is invalid.")
            await websocket.close(code=1003)
            return

        await ws_manager.accept(user_id, thread_id, websocket)
        try:
            session = module.conversation_mgr.get_session(thread_id)
            previous_messages = session.get("messages", []) if session else []
            if previous_messages:
                await ws_manager.send_message(
                    thread_id,
                    {
                        "type": "previous_messages",
                        "message_list": previous_messages,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    },
                )
        except Exception as e:
            logger.error(f"Error retrieving previous messages: {str(e)}")
        try:
            # Keep connection open and handle messages
            while True:
                data = await websocket.receive_json()
                logger.info(
                    f"Received message on thread {thread_id}: {data}",
                )
                # Placeholder for actual validation
                valid_thread_result = {"is_valid": True}
                if not valid_thread_result.get("is_valid", False):
                    # Thread ID has expired during the session
                    response = {
                        "type": "error",
                        "message": "Thread ID has expired. Please request a new thread ID.",
                        "code": "THREAD_EXPIRED",
                    }
                    await ws_manager.send_message(thread_id, response)
                    break

                # Call the handler’s entrypoint
                await module.handle(websocket.app, thread_id, user_id, data)
                # Prevent tight loop if handler is too fast
                await asyncio.sleep(0.5)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for thread {thread_id}")
            await ws_manager.disconnect(thread_id)
        finally:
            # Ensure we clean up the connection
            await ws_manager.disconnect(thread_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {handler}/{user_id}/{thread_id}")
    except Exception as e:
        logger.exception(f"Error in WebSocket connection: {e}")
        await websocket.close(code=1011)

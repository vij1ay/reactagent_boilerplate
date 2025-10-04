import asyncio
import datetime
import json
import time
import traceback
from uuid import uuid4
from typing import Dict, Any, Optional, List, Set, cast

from fastapi import FastAPI, WebSocketDisconnect
from langchain_core.runnables import RunnableConfig

from conversations.thread_manager import ConversationManager
from websocket.manager import WebSocketManager
from app_logger import logger
from utils import (
    _ensure_serializable,
    get_redis_instance,
    safe_jsondumps,
)

ws_manager = WebSocketManager()
conversation_mgr = ConversationManager()


async def _process_graph_stream(
    fastapi_app: FastAPI, thread_id: str, user_id: str, user_input: Dict[str, Any], config: RunnableConfig
) -> None:
    """
    Processes the Thread graph using astream_events, handling token streaming,
    event reporting, and session updates from a single invocation.
    """
    is_streaming_tokens = False
    latest_full_content = ""
    current_message_tokens: List[str] = []
    seen_events: Set[str] = set()
    sent_tool_results: Set[str] = set()
    tools_started: Set[str] = set()
    tool_data: Dict[str, Dict[str, Any]] = {}
    final_ai_message_content: Optional[str] = None
    structured_response_sent = False

    event_stream_config: RunnableConfig = {
        **config,
    }
    stream_kwargs = {"stream_mode": "events"}

    try:
        logger.info(f"Starting unified event stream for thread {thread_id} with config: {event_stream_config}")

        async for event in fastapi_app.state.planner_graph.astream_events(
            user_input, config=event_stream_config, version="v2", **stream_kwargs
        ):
            event_type = event.get("event")
            event_data = event.get("data", {})
            event_name = event.get("name", "")
            run_id = event.get("run_id")
            tags = event.get("tags", [])
            logger.debug(f"Event received: type={event_type}, name={event_name}, run_id={run_id}")
            if event_name == "CustomChatOpenAI":
                if event_type == "on_chain_end" or event_type == "on_node_end":
                    output = event_data.get("output")
                    if output:
                        final_ai_message_content = None
                        if isinstance(output, dict) and "messages" in output:
                            final_messages = output["messages"]
                            if final_messages and isinstance(final_messages, list):
                                for msg in reversed(final_messages):
                                    role = None
                                    content = None
                                    if isinstance(msg, dict):
                                        role = msg.get("role")
                                        content = msg.get("content")
                                    elif hasattr(msg, "type") and hasattr(msg, "content"):
                                        role = getattr(msg, "type", None) or getattr(
                                            msg, "role", None
                                        )
                                        content = getattr(msg, "content", None)
                                    if (role == "ai" or role == "assistant") and content:
                                        final_ai_message_content = content
                                        break
                        if final_ai_message_content:
                            current_time = datetime.datetime.now(
                                datetime.timezone.utc)
                            ai_message = {
                                "id": message_id,
                                "role": "internal_ai",
                                "content": final_ai_message_content,
                                "timestamp": current_time.isoformat(),
                            }
                            conversation_mgr.add_message(thread_id, ai_message)
                    continue
                else:
                    continue  # Skip other events from CustomChatOpenAI

            # Token Streaming Logic
            if event_type in ["on_chat_model_stream", "on_llm_stream"]:
                chunk = event_data.get("chunk")
                if chunk:
                    content_piece = None
                    if hasattr(chunk, "content"):
                        content_piece = chunk.content
                    elif isinstance(chunk, str):
                        content_piece = chunk

                    if content_piece:
                        if not is_streaming_tokens:
                            is_streaming_tokens = True
                            current_message_tokens = []
                            await ws_manager.send_message(
                                thread_id,
                                {
                                    "type": "msg_stream_start",
                                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                },
                            )
                            logger.info(
                                f"Started token stream for thread {thread_id}")
                            last_logged_length = 0
                            log_interval = 100

                        current_message_tokens.append(content_piece)
                        latest_full_content = "".join(current_message_tokens)
                        await ws_manager.send_message(
                            thread_id,
                            {
                                "type": "msg_stream",
                                "message": content_piece,
                                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            },
                        )
                        current_length = len(latest_full_content)
                        if current_length >= last_logged_length + log_interval:
                            logger.debug(
                                f"Streaming progress: ~{current_length} characters..."
                            )
                            last_logged_length = current_length

            # Structured Response & Final Message Logic
            if event_type == "on_chain_end" or event_type == "on_node_end":
                output = event_data.get("output")
                if output:
                    if isinstance(output, dict) and "messages" in output:
                        final_messages = output["messages"]
                        if final_messages and isinstance(final_messages, list):
                            for msg in reversed(final_messages):
                                role = None
                                content = None
                                if isinstance(msg, dict):
                                    role = msg.get("role")
                                    content = msg.get("content")
                                elif hasattr(msg, "type") and hasattr(msg, "content"):
                                    role = getattr(msg, "type", None) or getattr(
                                        msg, "role", None
                                    )
                                    content = getattr(msg, "content", None)

                                if (role == "ai" or role == "assistant") and content:
                                    final_ai_message_content = content
                                    break

                    elif (
                        isinstance(output, dict)
                        and "structured_response" in output
                        and not structured_response_sent
                    ):
                        structured_data = _ensure_serializable(
                            output["structured_response"]
                        )
                        await ws_manager.send_message(
                            thread_id,
                            {
                                "type": "structured_response",
                                "data": structured_data,
                                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            },
                        )
                        structured_response_sent = True
                        logger.info(
                            "Sent structured response data to client from event"
                        )

            node_name = event_name
            display_name = node_name.replace(
                "_", " ").title() if node_name else "Graph"
            event_id = f"{event_type}:{node_name}:{run_id}"

            if event_id in seen_events:
                continue

            normalized_event_type: Optional[str] = None
            message: Optional[str] = None
            tool_info: Dict[str, Any] = {}

            is_tool_event = event_type is not None and (
                "tool" in event_type or any(
                    tag.startswith("tool:") for tag in tags)
            )

            if event_type == "on_node_start" and not is_tool_event:
                normalized_event_type = "on_node_start"
                message = await _format_event_message(
                    normalized_event_type,
                    cast(Dict[str, Any], event_data),
                    node_name,
                    thread_id,
                )
            elif event_type == "on_node_end" and not is_tool_event:
                normalized_event_type = "on_node_end"
                message = await _format_event_message(
                    normalized_event_type,
                    cast(Dict[str, Any], event_data),
                    node_name,
                    thread_id,
                )
            elif event_type == "on_tool_start":
                normalized_event_type = "on_tool_start"
                tool_input = event_data.get("input", {})
                tool_info["name"] = node_name
                input_str = str(tool_input)
                tool_info["input"] = (
                    input_str[:100] +
                    "..." if len(input_str) > 100 else input_str
                )
                message = await _format_event_message(
                    normalized_event_type,
                    cast(Dict[str, Any], event_data),
                    node_name,
                    thread_id,
                )
                tools_started.add(node_name)
                logger.info(f"Marked tool {node_name} as started")
                if node_name not in tool_data:
                    tool_data[node_name] = {"input": tool_input}
            elif event_type == "on_tool_end":
                normalized_event_type = "on_tool_end"
                tool_output = event_data.get("output", {})
                tool_info["name"] = node_name
                output_str = str(tool_output)
                tool_info["output"] = (
                    output_str[:100] +
                    "..." if len(output_str) > 100 else output_str
                )
                message = await _format_event_message(
                    normalized_event_type,
                    cast(Dict[str, Any], event_data),
                    node_name,
                    thread_id,
                )
                if node_name in tool_data:
                    tool_data[node_name]["output"] = tool_output
                else:
                    tool_data[node_name] = {"output": tool_output}

            if normalized_event_type and message:
                seen_events.add(event_id)
                response = {
                    "type": "agent_event",
                    "event_type": normalized_event_type,
                    "node_name": node_name,
                    "display_name": display_name,
                    "message": message,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "event_order": len(seen_events),
                }
                if tool_info:
                    response["tool_info"] = tool_info

                logger.info(
                    f"Sending agent event: {normalized_event_type} - {message[:50]}..."
                )
                await ws_manager.send_message(thread_id, response)

        logger.info(f"Graph event stream finished for thread {thread_id}")
        if is_streaming_tokens:
            await ws_manager.send_message(
                thread_id,
                {"type": "msg_stream_end", "timestamp": datetime.datetime.now(
                    datetime.timezone.utc).isoformat()},
            )
            logger.info(f"Token stream ended for thread {thread_id}")

        final_content_to_save = (
            final_ai_message_content
            if final_ai_message_content is not None
            else latest_full_content
        )

        session = conversation_mgr.get_session(thread_id)
        if session:
            if final_content_to_save:
                current_thread_name = session.get(
                    "thread_name", "New Conversation")
                current_time = datetime.datetime.now(datetime.timezone.utc)
                message_id = str(uuid4())

                logger.info(
                    f"Saved final AI message to DB for thread {thread_id}")

                # Thread Naming Logic
                if current_thread_name == "New Conversation":
                    try:
                        messages = session.get("messages", [])
                        logger.info(
                            f"Session has {len(messages)} messages for thread naming"
                        )
                        user_message = ""
                        for msg in messages:
                            if msg.get("role") == "human":
                                user_message = msg.get("content", "")
                                break

                        if user_message and final_content_to_save:
                            logger.info(
                                f"Generating name for thread {thread_id} - User message: {user_message[:30]}..."
                            )
                            generated_name = (
                                await conversation_mgr.generate_thread_name(
                                    user_message=user_message,
                                    ai_message=final_content_to_save,
                                )
                            )

                            if (
                                generated_name != "New Conversation"
                                and generated_name.strip()
                            ):
                                thread_updated = (
                                    await conversation_mgr.update_thread_name(
                                        thread_id=thread_id, new_name=generated_name
                                    )
                                )

                                if thread_updated:
                                    session["thread_name"] = generated_name
                                    logger.info(
                                        f"Thread {thread_id} renamed to: {generated_name}"
                                    )

                                    await ws_manager.send_message(
                                        thread_id,
                                        {
                                            "type": "thread_name_updated",
                                            "thread_id": thread_id,
                                            "name": generated_name,
                                            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                        },
                                    )
                    except Exception as naming_err:
                        logger.error(
                            f"Error updating thread name: {naming_err}")

                if "messages" not in session:
                    session["messages"] = []

                if final_content_to_save:
                    ai_message = {
                        "id": message_id,
                        "role": "ai",
                        "content": final_content_to_save,
                        "timestamp": current_time.isoformat(),
                    }
                    cards = []  # ToDo: extract cards from structured response if available
                    if cards:
                        ai_message["cards"] = cards
                    conversation_mgr.add_message(thread_id, ai_message)

                    logger.info(f"Added AI message to session. Session now has {len(session['messages'])} messages")
                elif not any(
                    msg.get("role") == "ai" for msg in session["messages"][1:]
                ):
                    fallback_response = "I'm sorry, I wasn't able to generate a response. How else can I help you with your travel plans?"
                    logger.warning(f"No AI content generated, adding fallback response to session cache.")
                    conversation_mgr.add_message(
                        thread_id, {"role": "ai", "content": fallback_response}
                    )
                    final_content_to_save = fallback_response

                if final_content_to_save:
                    response_message = {
                        "type": "agent_response",
                        "content": final_content_to_save,
                        "agent": "planner",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }

                    await ws_manager.send_message(thread_id, response_message)
                    logger.debug("Sent complete agent response message")
                else:
                    logger.warning(
                        "No final AI content available to send as agent_response."
                    )

        await ws_manager.send_message(
            thread_id,
            {
                "type": "completed",
                "thread_id": thread_id,
                "agent": "planner",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        )

    except asyncio.CancelledError:
        logger.info(f"Thread processing task cancelled for {thread_id}")
        if is_streaming_tokens:
            try:
                await ws_manager.send_message(
                    thread_id,
                    {"type": "msg_stream_end",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()},
                )
            except Exception:
                pass
        raise

    except Exception as e:
        logger.error(
            f"Error during Thread stream processing for {thread_id}: {e}")
        logger.error(f"Stream processing traceback: {traceback.format_exc()}")

        try:
            await ws_manager.send_message(
                thread_id,
                {
                    "type": "error",
                    "message": f"Processing error: {str(e)}",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            )
        except Exception as ws_err:
            logger.error(f"Failed to send error to WebSocket: {ws_err}")

        fallback_response = "I apologize, but I encountered an error while processing your request. How else can I help you with your travel plans?"
        session = conversation_mgr.get_session(thread_id)
        if session:
            if "messages" not in session:
                session["messages"] = []
            if (
                not session["messages"]
                or session["messages"][-1].get("content") != fallback_response
            ):
                conversation_mgr.add_message(
                    thread_id, {"role": "ai", "content": fallback_response}
                )
                try:
                    fallback_message = {
                        "type": "agent_response",
                        "content": fallback_response,
                        "agent": "planner",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }

                    await ws_manager.send_message(thread_id, fallback_message)
                    logger.info("Sent error fallback response")
                except Exception as ws_err:
                    logger.error(
                        f"Failed to send fallback response to WebSocket: {ws_err}"
                    )
    finally:
        was_cancelled = False
        try:
            await ws_manager.send_message(
                thread_id,
                {
                    "type": "completed",
                    "thread_id": thread_id,
                    "agent": "planner",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            )
            logger.debug("Sent completion message in finally block")

        except asyncio.CancelledError:
            was_cancelled = True
            raise
        except Exception as final_ws_err:
            if not was_cancelled:
                logger.error(
                    f"Error sending completion message in finally block: {final_ws_err}"
                )


async def _format_event_message(
    event_type: str,
    event_data: Dict[str, Any],
    node_name: str = "",
    thread_id: str = "",
) -> Optional[str]:
    """
    Maps key LangGraph events to user-facing messages for the Thread agent.
    """
    logger.info(
        f"In Format Event Message - Thread ID: {thread_id}, Node: {node_name}, Event: {event_type}"
    )
    if not node_name:
        if event_type == "on_node_start":
            return "Starting holiday plan..."
        return None

    node_lower = node_name.lower()

    if event_type == "on_node_start":
        if "planner" in node_lower or "agent" in node_lower:
            return "Planning... 🏝️"
        elif "fetch" in node_lower or "search" in node_lower:
            return f"Starting search: {node_name.replace('_', ' ').title()}..."
        else:
            return None

    elif event_type == "on_tool_start":
        if node_name == "get_specialist_availability":
            return "Getting our specialist availability.. 🔍"
        elif node_name == "onboard_customer":
            return "Onboarding you as a new customer.. 🏨"
        elif node_lower == "case_studies_tool":
            return "Fetching case studies.. 📚"
        elif node_lower == "check_appointment_availability":
            return "Checking Appointment Availability.. 📅"
        elif node_lower == "book_appointment":
            return "Booking Appointment... 📅"
        else:
            return None

    elif event_type == "on_tool_end":
        return None

    elif event_type == "on_node_end":
        if "planner" in node_lower or "agent" in node_lower:
            return None
        else:
            return None

    return None


async def handle(fastapi_app: FastAPI, thread_id: str, user_id: str, user_input: Any):
    """
    Handles incoming user input for a chat thread, processes it through the agent,
    and streams responses and events to the WebSocket client.
    """
    try:
        logger.info(f"Received user input on thread {thread_id}: {user_input}")
        if isinstance(user_input, dict):
            user_query = user_input.get(
                "query", user_input.get("message", "")).strip()
        elif isinstance(user_input, str):
            user_query = user_input.strip()
        else:
            user_query = ""
        if user_query:
            current_time = datetime.datetime.now(datetime.timezone.utc)
            message_id = str(uuid4())
            user_message = {
                "id": message_id,
                "user_id": user_id,
                "role": "human",
                "content": user_query,
                "timestamp": current_time.isoformat(),
            }

            conversation_mgr.add_message(thread_id, user_message)
            user_input = {
                "messages": [user_message],
                "thread_id": thread_id,
                "user_id": user_id,
            }
            config: RunnableConfig = {
                "configurable": {
                    "thread_id": thread_id,
                },
            }

            await ws_manager.send_message(
                thread_id,
                {
                    "type": "processing",
                    "message": "VJ Bot thinking... 🤔",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            )

            processing_task = asyncio.create_task(
                _process_graph_stream(fastapi_app, thread_id, user_id,
                                      user_input, config)
            )

            try:
                logger.debug(
                    f"Waiting for Thread stream task for thread {thread_id}..."
                )
                await processing_task
                logger.debug(
                    f"Thread stream task completed for thread {thread_id}.")
            except asyncio.CancelledError:
                logger.info(f"Thread stream task cancelled for {thread_id}")
                raise
            except Exception as e:
                logger.error(
                    f"Error awaiting Thread stream task for {thread_id}: {e}")
                logger.error(
                    f"Stream/Save Error Traceback: {traceback.format_exc()}")
            finally:
                logger.debug(f"Finished handle_message for thread {thread_id}")
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: chat/{thread_id}")
        await ws_manager.disconnect(thread_id)
    except Exception as e:
        logger.exception(f"Error in chat handler: {str(e)}")
        await ws_manager.send_message(
            thread_id, {"type": "error", "message": f"Error: {str(e)}"}
        )

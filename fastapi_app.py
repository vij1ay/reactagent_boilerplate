# main.py
import json
import uvicorn
import websocket
import webbrowser

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.checkpoint.memory import MemorySaver
from contextlib import asynccontextmanager

from app_logger import logger
from agent_tools.planner import create_planner_graph
from utils import get_redis_instance, get_redis_async_instance, environment
from config import COMPANY_NAME, CHATBOT_NAME, COMPANY_MOTO


redis_client = get_redis_instance()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Initializes Redis checkpointer if enabled, otherwise falls back to memory saver.
    Sets up the planner graph and handles cleanup on shutdown.
    """
    if environment.get("REDIS_HOST", ""):
        try:
            async_redis_cli = get_redis_async_instance()
            checkpointer = AsyncRedisSaver(redis_client=async_redis_cli)
            await checkpointer.asetup()
        except Exception as e:
            logger.error(f"Failed to initialize Redis Checkpointer: {str(e)}")
            checkpointer = None
            if async_redis_cli:
                await async_redis_cli.aclose()
                async_redis_cli = None
            logger.info("Redis Checkpointing Errored. Using MemorySaver.")
            checkpointer = MemorySaver()  # type: ignore
    else:
        logger.info("Redis Checkpointing is disabled. Using MemorySaver.")
        checkpointer = MemorySaver()  # type: ignore

    app.state.planner_graph = create_planner_graph(checkpointer=checkpointer)
    logger.info("Planner graph initialized")

    yield

    logger.info("Shutting down application")
    if async_redis_cli:
        await async_redis_cli.aclose()
        logger.info("Redis connection closed.")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: The configured FastAPI application.
    """
    app = FastAPI(
        title="MultiAgent Boilerplate API",
        description="API for interacting with the MultiAgent Boilerplate",
        version="1.0.0",
        lifespan=lifespan
    )

    app.mount("/assets", StaticFiles(directory="assets"), name="assets")

    @app.get("/", response_class=HTMLResponse)
    async def serve_chat() -> HTMLResponse:
        """
        Serve the chat interface HTML page.

        Returns:
            HTMLResponse: The rendered chat interface HTML.
        """
        with open("assets/chat.html", "r", encoding="utf-8") as f:
            content = f.read()
            content = content.replace("@@@company_name@@@", COMPANY_NAME)
            content = content.replace("@@@chatbot_name@@@", CHATBOT_NAME)
            content = content.replace("@@@company_moto@@@", COMPANY_MOTO)
            return HTMLResponse(content=content)

    app.include_router(websocket.router)

    @app.get("/leads_generated", response_class=HTMLResponse)
    async def serve_leads_generated() -> HTMLResponse:
        """
        Serve the leads generated HTML page.

        Returns:
            HTMLResponse: The rendered leads generated HTML.
        """
        with open("assets/leads_generated.html", "r", encoding="utf-8") as f:
            content = f.read()
            content = content.replace("@@@company_name@@@", COMPANY_NAME)
            content = content.replace("@@@chatbot_name@@@", CHATBOT_NAME)
            return HTMLResponse(content=content)

    @app.get("/get_lead_datalist", response_class=JSONResponse)
    async def get_lead_datalist() -> JSONResponse:
        """
        Serve the leads generated data as JSON.

        Returns:
            JSONResponse: The leads data.
        """
        leads = redis_client.hgetall("leads_generated")
        ret = []
        for lead in leads:
            ret.append(json.loads(redis_client.hget("leads_generated", lead)))
        return JSONResponse(content=ret)

    app.include_router(websocket.router)

    # for route in app.routes:
    #     methods = getattr(route, "methods", ["WEBSOCKET"])
    #     print(f"{methods} -> {route.path}")

    return app


def main() -> None:
    """
    Initialize and start the multiagent server.

    This function:
    1. Creates the Websocket instance
    2. Initializes the FastAPI application
    3. Opens the chat interface in the default web browser
    4. Starts the uvicorn server
    """
    webserver_port = 8000
    fastapi_app = create_app()

    # Open chat interface in browser
    # webbrowser.open(f'http://localhost:{webserver_port}')

    uvicorn.run(
        fastapi_app,
        host="0.0.0.0",
        port=webserver_port,
        log_level="info"
    )


if __name__ == "__main__":
    main()

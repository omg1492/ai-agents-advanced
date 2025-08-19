"""DreamFarm Agent - FastAPI application using Responses API and server-side state."""

import os
import logging
from datetime import datetime, timezone
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import warnings

from src.models.health import HealthResponse
from src.models.chat import ChatRequest, ChatResponse
from src.models.thread import (
    CreateThreadRequest,
    CreateThreadResponse,
    Thread as ThreadModel,
    SendMessageRequest,
    SendMessageResponse,
    GetMessagesResponse,
    Message as MessageModel,
)
from src.services.openai_service import OpenAIService
from src.services.config_service import ConfigService
from src.services.rag_service import RAGService
from src.services.template_service import TemplateService


# Load environment variables
load_dotenv()

# Suppress noisy Pydantic serializer warnings emitted by OpenAI SDK when streaming
# MCP/tool events that don't match strict unions. These are benign and clutter logs.
warnings.filterwarnings(
    "ignore",
    message=r"^Pydantic serializer warnings:",
    category=UserWarning,
    module=r"pydantic\.main",
)

# Configure logging level from environment (default to INFO)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global services
openai_service: OpenAIService = None
config_service: ConfigService = None
rag_service: RAGService | None = None
template_service: TemplateService | None = None
# Minimal session and history stores (state remains in Responses API)
_threads: dict[str, ThreadModel] = {}
_history: dict[str, list[MessageModel]] = {}
_last_response_id: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global openai_service, config_service, rag_service, template_service

    # Startup
    logger.info("Starting DreamFarm Agent...")
    try:
        # Load and validate configuration (unified OpenAI/Azure envs)
        config_service = ConfigService()
        cfg = config_service.config
        # Apply log level from config if different
        logger.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))
        logger.info(
            "Config loaded: environment=%s, openai.base_url=%s, openai.model=%s",
            cfg.environment,
            cfg.openai.base_url,
            cfg.openai.model_name,
        )
        openai_service = OpenAIService(config_service.get_openai_config())
        # Initialize template service
        template_service = TemplateService()
        if not template_service.template_exists("system_prompt.j2"):
            raise RuntimeError("Required template 'system_prompt.j2' not found in src/templates")
        # Initialize RAG (optional)
        rag_service = None
        if cfg.rag.enabled:
            try:
                rag_service = RAGService(cfg)
                logger.info("RAG service initialized and enabled")
            except Exception as re:
                logger.warning(f"RAG initialization failed, continuing without RAG: {re}")
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down DreamFarm Agent...")


# Create FastAPI application
app = FastAPI(
    title="DreamFarm Agent",
    description="AI-powered assistant for Dream Farm marketplace",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.
    
    Returns:
        Health status and timestamp
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Single endpoint chat using server-side conversation state.

    Uses Responses API with store=True and previous_response_id for continuity.
    """
    try:
        # Build system prompt from template and optional RAG context
        rag_context = None
        if 'rag_service' in globals() and rag_service is not None and getattr(rag_service, 'enabled', False):
            try:
                rag_context = await rag_service.get_relevant_context(request.message)
            except Exception as re:
                logger.warning(f"RAG context fetch failed; proceeding without context: {re}")

        system_prompt = template_service.render_template(
            "system_prompt.j2",
            {
                "user_location": None,
                "seasonal_products": [],
                "user_preferences": [],
                "simple_rag": rag_context or "",
            },
        )
        logger.debug(f"Rendered system prompt for /chat:\n{system_prompt}")

        text, response_id = await openai_service.generate_response(
            user_text=request.message,
            system_prompt=system_prompt,
            previous_response_id=request.previous_response_id,
        )
        return ChatResponse(
            response_id=response_id,
            message=text,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to process chat request")


# Removed thread-based endpoints in favor of /chat with server-side state

# Lightweight /threads endpoints to satisfy frontend session handling

@app.post("/threads", response_model=CreateThreadResponse)
async def create_thread(payload: CreateThreadRequest):
    now = datetime.now(timezone.utc).isoformat()
    thread_id = os.urandom(8).hex()
    title = payload.title or f"Dream Farm Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    thread = ThreadModel(
        thread_id=thread_id,
        title=title,
        created_at=now,
        updated_at=now,
        message_count=0,
    )
    _threads[thread_id] = thread
    _history[thread_id] = []
    return CreateThreadResponse(
        thread_id=thread_id,
        title=title,
        created_at=now,
        updated_at=now,
    )


@app.get("/threads/{thread_id}", response_model=ThreadModel)
async def get_thread(thread_id: str):
    thread = _threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@app.post("/threads/{thread_id}/messages", response_model=SendMessageResponse)
async def send_message(thread_id: str, payload: SendMessageRequest):
    thread = _threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    now = datetime.now(timezone.utc).isoformat()
    message_id = os.urandom(8).hex()

    # Add user message to lightweight history
    user_msg = MessageModel(
        message_id=message_id,
        thread_id=thread_id,
        role="user",
        content=payload.message,
        timestamp=now,
    )
    _history[thread_id].append(user_msg)

    # Use provider state via Responses API
    prev_resp_id = _last_response_id.get(thread_id)
    # Build system prompt from template and optional RAG context
    rag_context = None
    if 'rag_service' in globals() and rag_service is not None and getattr(rag_service, 'enabled', False):
        try:
            rag_context = await rag_service.get_relevant_context(payload.message)
        except Exception as re:
            logger.warning(f"RAG context fetch failed; proceeding without context: {re}")

    system_prompt = template_service.render_template(
        "system_prompt.j2",
        {
            "user_location": None,
            "seasonal_products": [],
            "user_preferences": [],
            "simple_rag": rag_context or "",
        },
    )
    logger.debug(f"Rendered system prompt for /threads/{thread_id}/messages:\n{system_prompt}")
    try:
        text, response_id = await openai_service.generate_response(
            user_text=payload.message,
            system_prompt=system_prompt,
            previous_response_id=prev_resp_id,
        )
    except Exception as e:
        logger.error(f"Failed to generate AI response: {e}")
        raise HTTPException(status_code=500, detail="Failed to process message")

    # Track last response_id for this thread to maintain continuity
    if response_id:
        _last_response_id[thread_id] = response_id

    # Add assistant message to lightweight history
    assistant_msg = MessageModel(
        message_id=os.urandom(8).hex(),
        thread_id=thread_id,
        role="assistant",
        content=text,
        timestamp=now,
    )
    _history[thread_id].append(assistant_msg)

    # Update thread metadata
    thread.message_count = len(_history[thread_id])
    thread.updated_at = now

    return SendMessageResponse(
        message_id=message_id,
        thread_id=thread_id,
        user_message=payload.message,
        assistant_response=text,
        timestamp=now,
    )


@app.post("/threads/{thread_id}/messages/stream")
async def send_message_stream(thread_id: str, payload: SendMessageRequest):
    """Stream assistant response tokens for a user message in a thread.

    Streams raw text chunks so the frontend can progressively render tokens.
    Also updates lightweight history and server-side state once completed.
    """
    thread = _threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Record the user message immediately
    now_iso = datetime.now(timezone.utc).isoformat()
    user_message_id = os.urandom(8).hex()
    user_msg = MessageModel(
        message_id=user_message_id,
        thread_id=thread_id,
        role="user",
        content=payload.message,
        timestamp=now_iso,
    )
    _history.setdefault(thread_id, []).append(user_msg)

    prev_resp_id = _last_response_id.get(thread_id)

    # Build system prompt with optional RAG context
    rag_context = None
    if 'rag_service' in globals() and rag_service is not None and getattr(rag_service, 'enabled', False):
        try:
            rag_context = await rag_service.get_relevant_context(payload.message)
        except Exception as re:
            logger.warning(f"RAG context fetch failed; proceeding without context: {re}")

    system_prompt = template_service.render_template(
        "system_prompt.j2",
        {
            "user_location": None,
            "seasonal_products": [],
            "user_preferences": [],
            "simple_rag": rag_context or "",
        },
    )

    # Resolve tools once (tests may use a fake service without get_tools)
    tools = None
    try:
        if hasattr(openai_service, "get_tools"):
            tools = openai_service.get_tools()
    except Exception as e:
        logger.warning(f"Fetching tools failed; continuing without tools: {e}")

    # Server label no longer included in DF_META payload; skip computing it

    async def token_generator():
        """Internal async generator that yields text chunks and updates state on finish."""
        full_text = ""
        response_id_local = None
        last_tool_name: str | None = None
        # Track args and mapping by item_id to enrich subsequent events
        args_by_item_id: dict[str, str] = {}
        name_by_item_id: dict[str, str] = {}
        try:
            # Stream from OpenAI Responses API (unified OpenAI/Azure client)
            # Tools are optional; already resolved above
            stream_kwargs = {"tools": tools} if tools else {}
            async with openai_service.client.responses.stream(
                model=openai_service.model_name,
                instructions=system_prompt or None,
                input=payload.message,
                store=True,
                previous_response_id=prev_resp_id or None,
                reasoning={"effort": "minimal"},
                **stream_kwargs,
            ) as stream:
                async for event in stream:
                    et = getattr(event, "type", "")
                    # Collect plain text deltas
                    if et == "response.output_text.delta" or et.endswith("response.output_text.delta"):
                        delta = getattr(event, "delta", "")
                        if delta:
                            full_text += delta
                            yield delta
                    # Capture output items where the function/MCP call name is available
                    elif et in ("response.output_item.added", "response.output_item.done"):
                        item = getattr(event, "item", None)
                        if item is not None:
                            item_type = getattr(item, "type", None)
                            if item_type in ("function_call", "mcp_call", "web_search_call", "file_search_call"):
                                # Build simplified payload
                                meta = {"kind": "tool_event", "event_type": et}
                                i_name = getattr(item, "name", None)
                                if i_name:
                                    meta["tool_name"] = i_name
                                    last_tool_name = i_name
                                i_id = getattr(item, "id", None)
                                if i_id and i_name:
                                    name_by_item_id[i_id] = i_name
                                i_args = getattr(item, "arguments", None)
                                if isinstance(i_args, (str, bytes)) and i_args:
                                    meta["arguments"] = str(i_args)
                                    if i_id:
                                        args_by_item_id[i_id] = str(i_args)
                                logger.info(f"Tool event: {meta}")
                                yield "\nDF_META:" + json.dumps(meta, ensure_ascii=False) + "\n"
                    # Stream reasoning summaries (do not include in answer text)
                    elif "reasoning" in et:
                        delta = getattr(event, "delta", None) or getattr(event, "text", None)
                        if delta:
                            meta = {"kind": "reasoning", "event_type": et, "delta": delta}
                            logger.info(f"Reasoning event: {et} :: {delta}")
                            yield "\nDF_META:" + json.dumps(meta, ensure_ascii=False) + "\n"
                    # Stream tool-related events (MCP/web/file-search/function args)
                    elif ("tool" in et) or ("web_search_call" in et) or ("file_search_call" in et) or ("function_call" in et) or ("mcp" in et) or ("call." in et):
                        # Build simplified payload
                        meta = {"kind": "tool_event", "event_type": et}
                        # Pick up a name directly if present
                        direct_name = getattr(event, "tool_name", None) or getattr(event, "name", None)
                        if direct_name:
                            meta["tool_name"] = direct_name
                        # Use item_id correlations if available
                        item_id = getattr(event, "item_id", None)
                        if item_id:
                            if hasattr(event, "delta") and isinstance(getattr(event, "delta"), str):
                                d = getattr(event, "delta")
                                if d:
                                    args_by_item_id[item_id] = args_by_item_id.get(item_id, "") + d
                            if et.endswith(".done"):
                                final_args = getattr(event, "arguments", None)
                                if isinstance(final_args, (str, bytes)) and final_args:
                                    args_by_item_id[item_id] = str(final_args)
                            agg = args_by_item_id.get(item_id)
                            if agg:
                                meta["arguments"] = agg
                            known_name = name_by_item_id.get(item_id)
                            if known_name:
                                meta.setdefault("tool_name", known_name)
                        # Nested call object may carry name/args
                        for nested in (getattr(event, "call", None), getattr(event, "mcp_call", None), getattr(event, "tool", None)):
                            if nested is None:
                                continue
                            n_name = getattr(nested, "name", None)
                            if n_name:
                                meta.setdefault("tool_name", n_name)
                                last_tool_name = n_name
                            n_args = getattr(nested, "arguments", None)
                            if isinstance(n_args, (str, bytes)):
                                meta.setdefault("arguments", str(n_args))
                        # Some deltas carry args text directly
                        if hasattr(event, "delta") and isinstance(getattr(event, "delta"), str):
                            d = getattr(event, "delta")
                            if d and "arguments" not in meta:
                                meta["arguments"] = d
                        # Include error detail when a call fails
                        if et.endswith(".failed") or et.endswith("response.error"):
                            item_id = getattr(event, "item_id", None)
                            if item_id:
                                agg = args_by_item_id.get(item_id)
                                if agg and "arguments" not in meta:
                                    meta["arguments"] = agg
                                known_name = name_by_item_id.get(item_id)
                                if known_name and "tool_name" not in meta:
                                    meta["tool_name"] = known_name
                            # Capture error message if available for diagnostics
                            err_obj = getattr(event, "error", None)
                            if err_obj is not None:
                                try:
                                    # Try common shapes: str or object with message
                                    err_text = getattr(err_obj, "message", None) or str(err_obj)
                                    if err_text:
                                        meta["error"] = err_text
                                except Exception:
                                    pass
                        if last_tool_name:
                            meta.setdefault("tool_name", last_tool_name)
                        logger.info(f"Tool event: {meta}")
                        yield "\nDF_META:" + json.dumps(meta, ensure_ascii=False) + "\n"
                    elif et == "response.error" or et.endswith("response.error"):
                        err = getattr(event, "error", None)
                        logger.error(f"OpenAI stream error: {err}")
                # Get final response to retrieve response_id
                final = await stream.get_final_response()
                response_id_local = getattr(final, "id", None)
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            # Stop streaming; client will handle partial content
        finally:
            # Update server-side state/history when stream completes
            if response_id_local:
                _last_response_id[thread_id] = response_id_local
            # Append assistant message to history
            assistant_msg = MessageModel(
                message_id=os.urandom(8).hex(),
                thread_id=thread_id,
                role="assistant",
                content=full_text,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            _history[thread_id].append(assistant_msg)
            # Update thread metadata
            thread.message_count = len(_history[thread_id])
            thread.updated_at = datetime.now(timezone.utc).isoformat()

    return StreamingResponse(token_generator(), media_type="text/plain; charset=utf-8")


@app.get("/threads/{thread_id}/messages", response_model=GetMessagesResponse)
async def get_messages(thread_id: str, limit: int = 50, offset: int = 0):
    if thread_id not in _threads:
        raise HTTPException(status_code=404, detail="Thread not found")
    msgs = _history.get(thread_id, [])
    total = len(msgs)
    paginated = msgs[offset : offset + limit]
    return GetMessagesResponse(thread_id=thread_id, messages=paginated, total_count=total)


def main():
    """Main entry point for the application."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()

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
from src.services.stock_service import StockService


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
stock_service: StockService | None = None
# Minimal session and history stores (state remains in Responses API)
_threads: dict[str, ThreadModel] = {}
_history: dict[str, list[MessageModel]] = {}
_last_response_id: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global openai_service, config_service, rag_service, template_service, stock_service

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
        # Initialize Stock custom tool
        stock_service = StockService(cfg)
        if stock_service.enabled:
            logger.info("Stock service (custom tool) enabled")
        else:
            logger.info("Stock service (custom tool) disabled")
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
                # Stock data is NOT injected here; retrieved only via function calling.
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

    # Build system prompt with optional RAG and stock context (parity with non-stream endpoints)
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
            # Stock data excluded; function calling path only.
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

    # Implement the pattern from Tomáš Kubica article: loop-based streaming with tool execution
    input_messages = [{"role": "user", "content": payload.message}]
    response_id_local = prev_resp_id
    full_text = ""
    
    async def token_generator():
        """Loop-based streaming generator following proven GPT-5 reasoning pattern."""
        nonlocal input_messages, response_id_local, full_text
        
        while True:
            try:
                # Stream from OpenAI Responses API
                stream_kwargs = {"tools": tools} if tools else {}
                async with openai_service.client.responses.stream(
                    model=openai_service.model_name,
                    instructions=system_prompt or None,
                    input=input_messages,
                    store=True,
                    previous_response_id=response_id_local or None,
                    reasoning={"effort": "minimal"},
                    **stream_kwargs,
                ) as response:
                    
                    # Collect all items (reasoning + function calls) and tool outputs for next iteration
                    pending_outputs = []
                    current_reasoning_item = None
                    
                    # Process streaming events from the model
                    async for event in response:
                        if hasattr(event, "response_id"):
                            response_id_local = event.response_id
                            
                        et = getattr(event, "type", "")
                        
                        # Stream text deltas directly to client
                        if et == "response.output_text.delta":
                            delta = getattr(event, "delta", "")
                            if delta:
                                full_text += delta
                                yield delta
                                
                        # Handle function call arguments streaming
                        elif et == "response.function_call_arguments.delta":
                            # Don't yield function args to client, just log
                            delta = getattr(event, "delta", "")
                            logger.debug(f"Function arg delta: {delta}")
                            
                        # Capture reasoning and function call items when done
                        elif et == "response.output_item.done":
                            item = getattr(event, "item", None)
                            if item is not None:
                                item_type = getattr(item, "type", None)
                                
                                # Store reasoning items to pair with function calls
                                if item_type == "reasoning":
                                    current_reasoning_item = item
                                    input_messages.append(item)
                                    logger.info("Reasoning step completed")
                                
                                # Handle function calls
                                elif item_type == "function_call":
                                    # Add reasoning item first (if we have one), then function call
                                    if current_reasoning_item is not None:
                                        # Reasoning already added above, just note the pairing
                                        logger.debug(f"Paired reasoning item with function call: {getattr(item, 'name', 'unknown')}")
                                        current_reasoning_item = None  # Reset for next pair
                                    
                                    # Add function call to input messages
                                    input_messages.append(item)
                                    
                                    # Tool event meta for UI
                                    meta = {"kind": "tool_event", "event_type": et}
                                    i_name = getattr(item, "name", None)
                                    if i_name:
                                        meta["tool_name"] = i_name
                                    i_args = getattr(item, "arguments", None)
                                    if isinstance(i_args, (str, bytes)) and i_args:
                                        meta["arguments"] = str(i_args)
                                    logger.info(f"Tool event: {meta}")
                                    yield "\nDF_META:" + json.dumps(meta, ensure_ascii=False) + "\n"
                                    
                                    # Execute get_stock function
                                    if getattr(item, "name", None) == "get_stock":
                                        try:
                                            raw_args = getattr(item, "arguments", "{}")
                                            parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else {}
                                            product_ids = parsed_args.get("productIds", parsed_args.get("product_ids", []))
                                            if not isinstance(product_ids, list):
                                                product_ids = []
                                            product_ids = [str(p) for p in product_ids][:20]
                                            
                                            stock_items_result = []
                                            if product_ids and hasattr(openai_service, "_stock_service") and openai_service._stock_service and openai_service._stock_service.enabled:  # type: ignore[attr-defined]
                                                try:
                                                    stock_items = await openai_service._stock_service.get_stock(product_ids)  # type: ignore[attr-defined]
                                                    for it in stock_items:
                                                        stock_items_result.append({"product_id": it.product_id, "on_stock": it.on_stock})
                                                    logger.info(
                                                        "Stock API returned %s items (requested %s) for call %s",
                                                        len(stock_items_result),
                                                        len(product_ids),
                                                        getattr(item, "id", "unknown"),
                                                    )
                                                except Exception as se:  # noqa: BLE001
                                                    logger.warning("Stock function execution failed: %s", se)
                                            
                                            # Store function call output for next iteration
                                            pending_outputs.append({
                                                "type": "function_call_output",
                                                "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                "output": json.dumps({"items": stock_items_result}),
                                            })
                                            
                                            # Emit meta event for UI
                                            submit_meta = {
                                                "kind": "tool_event",
                                                "event_type": "tool.outputs_executed",
                                                "tool_name": "get_stock",
                                                "output_items_count": len(stock_items_result),
                                            }
                                            yield "\nDF_META:" + json.dumps(submit_meta, ensure_ascii=False) + "\n"
                                            
                                        except Exception as exec_e:  # noqa: BLE001
                                            logger.warning(f"Function execution error: {exec_e}")
                        
                        # Tool event meta for UI (for added events)
                        elif et == "response.output_item.added":
                            item = getattr(event, "item", None)
                            if item is not None:
                                item_type = getattr(item, "type", None)
                                if item_type in ("function_call", "mcp_call", "web_search_call", "file_search_call"):
                                    meta = {"kind": "tool_event", "event_type": et}
                                    i_name = getattr(item, "name", None)
                                    if i_name:
                                        meta["tool_name"] = i_name
                                    i_args = getattr(item, "arguments", None)
                                    if isinstance(i_args, (str, bytes)) and i_args:
                                        meta["arguments"] = str(i_args)
                                    logger.debug(f"Tool event (added): {meta}")
                                    yield "\nDF_META:" + json.dumps(meta, ensure_ascii=False) + "\n"
                        
                # After stream ends, check if we need to continue the loop
                if not pending_outputs:
                    break  # No more tool calls → finished
                    
                # Add results and continue loop
                input_messages.extend(pending_outputs)
                logger.info(f"Continuing reasoning loop with {len(pending_outputs)} tool output(s)")
                
            except Exception as e:
                logger.error(f"Streaming loop failed: {e}")
                break
        
        # Update server-side state when completely done
        if response_id_local:
            _last_response_id[thread_id] = response_id_local
        assistant_msg = MessageModel(
            message_id=os.urandom(8).hex(),
            thread_id=thread_id,
            role="assistant",
            content=full_text,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        _history[thread_id].append(assistant_msg)
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

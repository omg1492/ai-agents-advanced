"""DreamFarm Agent - FastAPI application using Responses API and server-side state."""

import os
import logging
import uuid
from datetime import datetime, timezone, timedelta
import io
import json
import secrets
from contextlib import asynccontextmanager

from dotenv import load_dotenv
import warnings

# Load environment variables FIRST (before any other imports that might use them)
load_dotenv()

# Initialize OpenTelemetry BEFORE importing any LLM libraries or services
service_name = os.getenv("OTEL_SERVICE_NAME", "dreamfarm-agent")
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
otel_enabled = otlp_endpoint != ""

if otel_enabled:
    try:
        # 1. Configure tracing (TracerProvider + auto-instrumentation for OpenAI, psycopg2, SQLAlchemy)
        from src.utils.otel_tracing import configure_otel_tracing
        configure_otel_tracing(
            service_name=service_name,
            otlp_endpoint=otlp_endpoint,
            instrument_openai=True,
            instrument_psycopg2=True,
            instrument_sqlalchemy=True
        )
        print(f"[OK] OpenTelemetry tracing initialized: service={service_name}")
        
        # 2. Configure logging (structured JSON logs with trace correlation)
        from src.utils.otel_logging import configure_otel_logging, add_trace_context_to_logs
        logger = configure_otel_logging(service_name, otlp_endpoint)  # Configures ROOT logger
        add_trace_context_to_logs()
        print("[OK] OpenTelemetry logging configured (root logger with OTLP)")
        
        # 3. Configure metrics (application metrics + FastAPI instrumentation)
        from src.utils.otel_metrics import configure_otel_metrics
        meter_provider, meter = configure_otel_metrics(service_name, otlp_endpoint)
        if meter:
            print("[OK] OpenTelemetry metrics configured")
        
    except Exception as e:
        print(f"[WARNING] OpenTelemetry initialization failed: {e}")
        otel_enabled = False
        meter_provider = None
        meter = None
else:
    print("[INFO] OpenTelemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
    meter_provider = None
    meter = None

# NOW import FastAPI and other libraries AFTER OpenTelemetry initialization
# This ensures auto-instrumentation works for OpenAI, database, etc.
from fastapi import FastAPI, HTTPException, Request, Depends, status, Query, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Import models
from src.models.health import HealthResponse
from src.models.chat import ChatRequest, ChatResponse
from src.models.file import FileUploadResponse
from src.models.thread import (
    CreateThreadRequest,
    CreateThreadResponse,
    Thread as ThreadModel,
    SendMessageRequest,
    SendMessageResponse,
    GetMessagesResponse,
    Message as MessageModel,
    ThreadRenameRequest,
)

# Import services (these may import OpenAI, Anthropic, etc. - auto-instrumented now)
from src.services.openai_service import OpenAIService
from src.services.config_service import ConfigService
from src.services.rag_service import RAGService
from src.services.template_service import TemplateService
from src.services.stock_service import StockService
from src.services.semantic_cache_service import SemanticCacheService
from src.services.agentic_search import AgenticSearchService
from src.services.auth_service import AuthService
from src.services.conversation_store import ConversationStore
from src.services.memory_search_service import MemorySearchService
from src.services.user_profile_service import UserProfileService
from src.services.voice_service import VoiceService

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
semantic_cache_service: SemanticCacheService | None = None
auth_service: AuthService | None = None
agentic_search_service: AgenticSearchService | None = None
conversation_store: ConversationStore | None = None
memory_search_service: MemorySearchService | None = None
user_profile_service: UserProfileService | None = None
voice_service: VoiceService | None = None
# Granular memory feature flags (legacy MEMORY_FEATURES_ENABLED still supported as umbrella fallback)
_legacy_memory_enabled = os.getenv("MEMORY_FEATURES_ENABLED", "").lower() in ["true","1","yes","on"]
_conversation_store_enabled = os.getenv("CONVERSATION_STORE_ENABLED", "true" if _legacy_memory_enabled else "false").lower() in ["true","1","yes","on"]
_memory_search_enabled_flag = os.getenv("MEMORY_SEARCH_ENABLED", "true" if _legacy_memory_enabled else "false").lower() in ["true","1","yes","on"]
_user_profile_enabled = os.getenv("USER_PROFILE_ENABLED", "true" if _legacy_memory_enabled else "false").lower() in ["true","1","yes","on"]
# Minimal session and history stores (state remains in Responses API)
_threads: dict[str, ThreadModel] = {}
_history: dict[str, list[MessageModel]] = {}
_last_response_id: dict[str, str] = {}
_semantic_cache_bootstrap: dict[str, dict] = {}  # thread_id -> {user:str, assistant:str, injected:bool}
# Temp cache for code interpreter generated files: file_id -> {container_id, filename, created_at}
_generated_file_registry: dict[str, dict[str, object]] = {}
_GENERATED_FILE_TTL_SECONDS = 60 * 60  # 1 hour TTL for container/file mappings
# Artifact registry for custom HTML visualizations: artifact_id -> {html, created_at, thread_id}
_html_artifact_registry: dict[str, dict[str, object]] = {}
_HTML_ARTIFACT_TTL_SECONDS = 60 * 60  # 1 hour TTL for HTML artifacts


def _register_generated_file(file_id: str, container_id: str | None, filename: str | None) -> str | None:
    """Store generated file metadata for later download requests.

    Returns a short-lived access token that can be used as a query parameter
    when Authorization headers are not available (e.g., <img> tags).
    """
    if not file_id:
        return None
    _cleanup_generated_file_registry()
    download_token = secrets.token_urlsafe(24)
    _generated_file_registry[file_id] = {
        "container_id": container_id,
        "filename": filename or file_id,
        "created_at": datetime.now(timezone.utc),
        "token": download_token,
    }
    return download_token


def _cleanup_generated_file_registry() -> None:
    """Remove expired generated file metadata entries."""
    if not _generated_file_registry:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_GENERATED_FILE_TTL_SECONDS)
    stale_ids = [fid for fid, meta in _generated_file_registry.items()
                 if isinstance(meta.get("created_at"), datetime) and meta["created_at"] < cutoff]
    for fid in stale_ids:
        _generated_file_registry.pop(fid, None)


def _register_html_artifact(artifact_id: str, html: str, thread_id: str) -> None:
    """Store HTML visualization artifact for later retrieval.
    
    Args:
        artifact_id: Unique identifier for the artifact
        html: Sanitized HTML content
        thread_id: Thread ID this artifact belongs to
    """
    _cleanup_html_artifacts()
    _html_artifact_registry[artifact_id] = {
        "html": html,
        "created_at": datetime.now(timezone.utc),
        "thread_id": thread_id,
    }
    logger.info(f"Registered HTML artifact: id={artifact_id} size={len(html)} thread={thread_id}")


def _cleanup_html_artifacts() -> None:
    """Remove expired HTML artifact entries."""
    if not _html_artifact_registry:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_HTML_ARTIFACT_TTL_SECONDS)
    stale_ids = [aid for aid, meta in _html_artifact_registry.items()
                 if isinstance(meta.get("created_at"), datetime) and meta["created_at"] < cutoff]
    for aid in stale_ids:
        _html_artifact_registry.pop(aid, None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global openai_service, config_service, rag_service, template_service, stock_service, semantic_cache_service

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
        # Initialize semantic cache (optional, high-threshold first-turn accelerator)
        semantic_cache_service = None
        if getattr(cfg, "semantic_cache", None) and cfg.semantic_cache.enabled:
            try:
                semantic_cache_service = SemanticCacheService(cfg)
                logger.info(
                    "Semantic cache enabled (threshold=%.3f)",
                    cfg.semantic_cache.similarity_threshold,
                )
            except Exception as sce:  # pragma: no cover
                logger.warning(f"Semantic cache initialization failed: {sce}")
        # Agentic search service (tool-based retrieval)
        if getattr(cfg, "agentic_search", None) and cfg.agentic_search.enabled:  # type: ignore[attr-defined]
            try:
                from src.services.agentic_search import AgenticSearchService as _ASS
                global agentic_search_service
                agentic_search_service = _ASS(cfg)
                logger.info("Agentic search service enabled")
            except Exception as ase:  # pragma: no cover
                logger.warning(f"Agentic search initialization failed: {ase}")
                agentic_search_service = None
        # Auth service (Keycloak JWT validation)
        if cfg.auth and cfg.auth.enabled:
            try:
                from src.services.auth_service import AuthService as _AS
                global auth_service
                auth_service = _AS(cfg.auth.issuer, cfg.auth.audience, cfg.auth.jwks_url)
                logger.info(
                    "Auth enabled (issuer=%s audience=%s)",
                    cfg.auth.issuer,
                    cfg.auth.audience,
                )
            except Exception as ae:  # pragma: no cover
                logger.error(f"Auth initialization failed: {ae}")
                auth_service = None
        else:
            logger.info("Auth disabled")
        logger.info("Services initialized successfully")
        # Initialize conversation persistence (granular flag)
        global conversation_store
        if _conversation_store_enabled:
            try:
                from src.services.conversation_store import ConversationStore as _CS  # local import to avoid startup cost if disabled
                conversation_store = _CS(cfg)
                logger.info("Conversation store enabled")
            except Exception as ce:  # pragma: no cover
                logger.warning(f"ConversationStore initialization failed: {ce}")
                conversation_store = None
        else:
            conversation_store = None
        # Memory search service (granular flag)
        global memory_search_service
        try:
            if _memory_search_enabled_flag and getattr(cfg, "memory_search", None) and cfg.memory_search.enabled:  # type: ignore[attr-defined]
                from src.services.memory_search_service import MemorySearchService as _MS  # local import
                memory_search_service = _MS(cfg)
                logger.info("Memory search service enabled")
            else:
                memory_search_service = None
        except Exception as me:  # pragma: no cover
            logger.warning(f"Memory search initialization failed: {me}")
            memory_search_service = None
        # User profile service (read-only personalization context)
        global user_profile_service
        try:
            if _user_profile_enabled:
                user_profile_service = UserProfileService(cfg)
                logger.info("User profile service enabled")
            else:
                user_profile_service = None
        except Exception as upe:  # pragma: no cover
            logger.warning(f"UserProfileService initialization failed: {upe}")
            user_profile_service = None
        # Log consolidated feature flag states
        logger.info(
            "Feature flags: conversation_store=%s memory_search=%s user_profile=%s (legacy_memory_flag=%s)",
            bool(conversation_store),
            bool(memory_search_service and memory_search_service.enabled),
            bool(user_profile_service),
            _legacy_memory_enabled,
        )
        # Voice service (optional, requires Realtime API support)
        # Note: VoiceService creates its own AsyncOpenAI client with api-version=2025-08-28
        # for the Realtime API, separate from the text chat client (preview version)
        global voice_service
        voice_enabled = os.getenv("VOICE_ENABLED", "false").lower() in ["true","1","yes","on"]
        if voice_enabled:
            try:
                voice_service = VoiceService(
                    config=cfg,
                    conversation_store=conversation_store,
                    memory_search_service=memory_search_service,
                    agentic_search_service=agentic_search_service,  # Add agentic search for voice
                    user_profile_service=user_profile_service,
                )
                logger.info("Voice service enabled")
            except Exception as ve:  # pragma: no cover
                logger.warning(f"Voice service initialization failed: {ve}")
                voice_service = None
        else:
            logger.info("Voice service disabled")
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

# Instrument FastAPI with OpenTelemetry (after app creation)
if otel_enabled:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        # Exclude health check endpoint from tracing (reduces noise)
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health"  # Don't create spans for health checks
        )
        print("[OK] FastAPI instrumented with OpenTelemetry tracing (excluding /health)")
        
        # Add FastAPI metrics instrumentation
        if meter_provider and meter:
            from src.utils.otel_metrics import instrument_fastapi_metrics, create_custom_metrics
            instrument_fastapi_metrics(app, meter_provider, meter)
            
            # Create custom business metrics
            custom_metrics = create_custom_metrics(meter)
            # Store metrics in app state for access in routes
            app.state.custom_metrics = custom_metrics
        
    except Exception as e:
        print(f"[WARNING] FastAPI instrumentation failed: {e}")

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# OpenTelemetry business dimensions middleware
@app.middleware("http")
async def add_business_dimensions(request: Request, call_next):
    """Add business context attributes to OpenTelemetry spans and propagate via context."""
    if otel_enabled:
        from opentelemetry import trace as otel_trace
        from opentelemetry import context as otel_context
        
        span = otel_trace.get_current_span()
        if span and span.is_recording():
            # Set static agent_type dimension
            span.set_attribute("agent_type", "dreamfarm")
            
            # Set experiment dimension (static for now, could be from config)
            experiment = os.getenv("OTEL_EXPERIMENT", "production")
            span.set_attribute("experiment", experiment)
            
            # Extract user context from Authorization header if present
            user_id = "anonymous"
            is_vip = False
            
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer ") and auth_service is not None:
                try:
                    token = auth_header.split(" ", 1)[1].strip()
                    claims = auth_service.validate(token)
                    user_id, is_vip = auth_service.extract_identity(claims)
                except Exception:
                    pass  # Keep defaults
            
            # Set user dimensions on span
            span.set_attribute("user_id", user_id)
            span.set_attribute("is_vip", is_vip)
            
            # Propagate custom dimensions via OpenTelemetry context
            # This makes them available to child spans (database, OpenAI, etc.)
            ctx = otel_context.get_current()
            ctx = otel_context.set_value("user_id", user_id, ctx)
            ctx = otel_context.set_value("is_vip", is_vip, ctx)
            ctx = otel_context.set_value("agent_type", "dreamfarm", ctx)
            ctx = otel_context.set_value("experiment", experiment, ctx)
            
            # Extract thread_id from path if present (for /threads/{thread_id} endpoints)
            path = request.url.path
            if "/threads/" in path:
                # Parse thread_id from path like /threads/{thread_id}/messages
                parts = path.split("/")
                if len(parts) > 2 and parts[1] == "threads":
                    thread_id = parts[2]
                    if thread_id:  # Not empty
                        span.set_attribute("thread_id", thread_id)
                        ctx = otel_context.set_value("thread_id", thread_id, ctx)
            
            # Execute request with propagated context
            token_ctx = otel_context.attach(ctx)
            try:
                response = await call_next(request)
                return response
            finally:
                otel_context.detach(token_ctx)
        else:
            response = await call_next(request)
            return response
    else:
        response = await call_next(request)
        return response


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


def _require_user(request: Request) -> tuple[str, bool, dict]:
    """Dependency to validate JWT and extract identity.

    Returns (username, is_vip, claims). Raises HTTPException on failure.
    """
    if auth_service is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth service not ready")
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    try:
        claims = auth_service.validate(token)
        username, is_vip = auth_service.extract_identity(claims)
        return username, is_vip, claims
    except ValueError as ve:
        logger.warning(f"Auth failed: {ve}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@app.get("/debug/user-profile/{user_id}")
async def debug_user_profile(user_id: str, user_ctx: tuple[str, bool, dict] = Depends(_require_user)):
    """Debug endpoint to view raw user profile from database."""
    username, is_vip, _ = user_ctx
    # Only allow users to see their own profile or admin access (simplified check)
    if username != user_id and not is_vip:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not user_profile_service:
        raise HTTPException(status_code=503, detail="User profile service not available")
    
    try:
        profile = user_profile_service.get_profile(user_id)
        return {"user_id": user_id, "profile": profile, "found": profile is not None}
    except Exception as e:
        logger.error(f"Debug profile fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Profile fetch failed")


@app.post("/files/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    user_ctx: tuple[str, bool, dict] = Depends(_require_user)
):
    """Upload a file for code interpreter processing.
    
    Accepts CSV, Excel, JSON, TXT, PDF, and image files up to 30MB.
    Returns Azure OpenAI file ID that can be attached to messages.
    
    Args:
        file: Uploaded file from multipart/form-data
        user_ctx: Authenticated user context
        
    Returns:
        FileUploadResponse with file_id and metadata
        
    Raises:
        HTTPException: On validation errors or upload failures
    """
    username, is_vip, _ = user_ctx
    logger.info(f"/files/upload user={username} filename={file.filename} content_type={file.content_type}")
    
    # Check if code interpreter is enabled
    if not (config_service.config.code_interpreter and config_service.config.code_interpreter.enabled):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Code interpreter is not enabled"
        )
    
    # Validate file type
    allowed_extensions = {'.csv', '.xlsx', '.xls', '.json', '.txt', '.pdf', '.png', '.jpg', '.jpeg', '.gif'}
    allowed_content_types = {
        'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/json',
        'text/plain',
        'application/pdf',
        'image/png',
        'image/jpeg',
        'image/gif'
    }
    
    # Check extension
    if file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}"
            )
    
    # Check content type (if provided)
    if file.content_type and file.content_type not in allowed_content_types:
        logger.warning(f"Content type {file.content_type} not in allowed list, but extension is valid")
    
    # Read file content and check size (30MB limit per Responses API)
    MAX_SIZE = 30 * 1024 * 1024  # 30MB in bytes
    content = await file.read()
    size_bytes = len(content)
    
    if size_bytes > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large: {size_bytes} bytes. Maximum: {MAX_SIZE} bytes (30MB)"
        )
    
    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )
    
    # Upload to Azure OpenAI Files API
    try:
        # Create a file-like object for the OpenAI SDK
        import io
        file_obj = io.BytesIO(content)
        file_obj.name = file.filename or "uploaded_file"
        
        # Upload using OpenAI service client
        response = await openai_service.client.files.create(
            file=file_obj,
            purpose="assistants"
        )
        
        logger.info(f"File uploaded successfully: file_id={response.id} filename={file.filename} size={size_bytes}")
        
        return FileUploadResponse(
            file_id=response.id,
            filename=file.filename or "unknown",
            size_bytes=size_bytes,
            purpose="assistants",
            status="uploaded"
        )
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to Azure OpenAI: {str(e)}"
        )


@app.get("/files/{file_id}/content")
async def download_generated_file(
    file_id: str,
    request: Request,
    token: str | None = Query(None)
):
    """Proxy generated file content from Azure OpenAI container storage."""
    if openai_service is None:
        raise HTTPException(status_code=503, detail="OpenAI service not ready")

    _cleanup_generated_file_registry()
    meta = _generated_file_registry.get(file_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Generated file not found or expired")

    if token:
        expected = meta.get("token")
        if not isinstance(expected, str) or not secrets.compare_digest(token, expected):
            raise HTTPException(status_code=401, detail="Invalid download token")
    elif auth_service is not None:
        # Fall back to header-based auth when tokens are not provided
        _require_user(request)

    container_id = meta.get("container_id")
    if container_id is not None and not isinstance(container_id, str):
        container_id = None

    filename = str(meta.get("filename") or file_id)

    try:
        content_bytes, content_type = await openai_service.download_generated_file(
            file_id=file_id,
            container_id=container_id,
        )
    except FileNotFoundError:
        logger.warning(f"Generated file not found in container: file_id={file_id} container_id={container_id}")
        raise HTTPException(status_code=404, detail="File no longer available")
    except Exception as exc:  # pragma: no cover - network errors
        logger.exception(f"Failed to fetch generated file {file_id}: {exc}")
        raise HTTPException(status_code=502, detail="Failed to fetch generated file")

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"'
    }
    media_type = content_type or "application/octet-stream"
    return StreamingResponse(io.BytesIO(content_bytes), media_type=media_type, headers=headers)


@app.get("/artifacts/{artifact_id}")
async def get_html_artifact(
    artifact_id: str,
    request: Request
):
    """Retrieve a stored HTML visualization artifact.
    
    Returns sanitized HTML content for rendering in a sandboxed iframe.
    Public endpoint (no auth required) since:
    - Artifacts are scoped by unique UUID (hard to guess)
    - Artifacts expire after 1 hour
    - Browsers cannot pass auth headers to iframe src
    """
    _cleanup_html_artifacts()
    
    artifact = _html_artifact_registry.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found or expired")
    
    html = artifact.get("html")
    if not html or not isinstance(html, str):
        raise HTTPException(status_code=500, detail="Invalid artifact content")
    
    # Return HTML with text/html content type for iframe rendering
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html, status_code=200)


# ============================================================================
# Test API Endpoint (for PyRIT / Security Testing)
# ============================================================================

# Conditionally register test endpoints only if TEST_API_ENABLED=true
if os.getenv("TEST_API_ENABLED", "").lower() == "true":
    @app.post("/test/chat")
    async def test_chat(chat_request: ChatRequest, request: Request):
        """Simple non-streaming chat endpoint for automated security testing.
        
        **IMPORTANT**: This endpoint uses the SAME system prompt, tools, and safety
        guardrails as the production /chat endpoint. This ensures security testing
        validates the actual production behavior, not a simplified mock.
        
        Differences from production /chat:
        - ✅ SAME: System prompt with safety guardrails
        - ✅ SAME: All tools enabled (Chef, Farmer, Stock, MCP, etc.)
        - ✅ SAME: RAG context if enabled
        - ❌ DIFFERENT: No streaming (returns simple JSON response)
        - ❌ DIFFERENT: Simple API key auth (not OAuth/JWT)
        - ❌ DIFFERENT: No conversation history/threads (stateless)
        - ❌ DIFFERENT: No semantic cache
        - ❌ DIFFERENT: No user profile personalization
        
        This design ensures PyRIT and other security testing tools can validate:
        - System prompt prevents harmful outputs
        - Tools don't enable malicious actions
        - Content filters work correctly
        - Jailbreak attempts are blocked
        
        Requires TEST_API_KEY environment variable and X-Test-API-Key header.
        """
        # Require API key authentication
        test_api_key = os.getenv("TEST_API_KEY")
        if not test_api_key:
            raise HTTPException(
                status_code=500,
                detail="TEST_API_KEY not configured on server"
            )
        
        provided_key = request.headers.get("x-test-api-key")
        if not provided_key or provided_key != test_api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing X-Test-API-Key header"
            )
        
        logger.info(f"/test/chat message_length={len(chat_request.message)}")
        
        try:
            # Build SAME system prompt as production /chat endpoint
            # This ensures we're testing the actual system prompt with all safety guardrails
            rag_context = None
            if 'rag_service' in globals() and rag_service is not None and getattr(rag_service, 'enabled', False):
                try:
                    rag_context = await rag_service.get_relevant_context(chat_request.message)
                except Exception as re:
                    logger.warning(f"RAG context fetch failed in test endpoint: {re}")
            
            # Use static test user profile (no personalization in tests)
            user_profile_json = ""
            
            # Render the SAME system prompt template as production
            system_prompt = template_service.render_template(
                "system_prompt.j2",
                {
                    "user_location": None,
                    "seasonal_products": [],
                    "user_preferences": [],
                    "simple_rag": rag_context or "",
                    "user_profile": user_profile_json,
                    "user_id": "test-user",
                    "config": config_service.config,
                    "memory_write_profile_enabled": False,
                },
            )
            logger.debug(f"Test endpoint system prompt:\n{system_prompt}")
            
            # Call generate_response with SAME parameters as production
            # This includes all tools (Chef, Farmer, Stock, etc.) and safety guardrails
            text, response_id = await openai_service.generate_response(
                user_text=chat_request.message,
                system_prompt=system_prompt,
                previous_response_id=None,  # No conversation continuity in tests
                user_is_vip=False,
                user_id="test-user",
            )
            
            # Extract just the text response (same as production /chat)
            logger.info(f"/test/chat completed response_length={len(text)}")
            
            return ChatResponse(
                response_id=response_id,
                message=text,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        
        except Exception as e:
            logger.error(f"/test/chat failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Chat processing failed: {str(e)}"
            )


    @app.get("/test/health")
    async def test_health():
        """Health check for test API (no authentication required)."""
        return {"status": "healthy", "endpoint": "test"}
    
    logger.info("Test API enabled (/test/chat and /test/health endpoints registered)")
else:
    logger.info("Test API disabled (TEST_API_ENABLED not set to 'true')")


# ============================================================================
# Production Chat Endpoints
# ============================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user_ctx: tuple[str, bool, dict] = Depends(_require_user)):
    """Single endpoint chat using server-side conversation state.

    Uses Responses API with store=True and previous_response_id for continuity.
    """
    try:
        username, is_vip, _ = user_ctx
        logger.info("/chat user=%s vip=%s", username, is_vip)
        # Semantic cache: only when there is no previous_response_id (first turn)
        if (
            request.previous_response_id in (None, "")
            and 'semantic_cache_service' in globals()
            and semantic_cache_service is not None
            and getattr(semantic_cache_service, 'enabled', False)
        ):
            try:
                hit = await semantic_cache_service.lookup(request.message)
            except Exception as e:  # pragma: no cover
                logger.warning(f"Semantic cache lookup failed (/chat): {e}")
                hit = None
            if hit:
                logger.info("/chat semantic cache hit; skipping model call")
                return ChatResponse(
                    response_id="",  # no provider response id yet
                    message=hit.answer,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
        # Build system prompt from template and optional RAG context
        rag_context = None
        if 'rag_service' in globals() and rag_service is not None and getattr(rag_service, 'enabled', False):
            try:
                rag_context = await rag_service.get_relevant_context(request.message)
            except Exception as re:
                logger.warning(f"RAG context fetch failed; proceeding without context: {re}")
        user_profile_json = ""
        if _user_profile_enabled and user_profile_service is not None:
            try:
                prof = user_profile_service.get_profile(username)
                if prof:
                    user_profile_json = json.dumps(prof, ensure_ascii=False)
            except Exception as pe:  # pragma: no cover
                logger.warning(f"User profile fetch failed user={username}: {pe}")

        system_prompt = template_service.render_template(
            "system_prompt.j2",
            {
                "user_location": None,
                "seasonal_products": [],
                "user_preferences": [],
                "simple_rag": rag_context or "",
                "user_profile": user_profile_json,
                "user_id": username,
                "config": config_service.config,
                "memory_write_profile_enabled": bool(_user_profile_enabled and user_profile_service is not None),
            },
        )
        logger.debug(f"Rendered system prompt for /chat:\n{system_prompt}")

        text, response_id = await openai_service.generate_response(
            user_text=request.message,
            system_prompt=system_prompt,
            previous_response_id=request.previous_response_id,
            user_is_vip=is_vip,
            user_id=username,
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
async def create_thread(payload: CreateThreadRequest, user_ctx: tuple[str, bool, dict] = Depends(_require_user)):
    now = datetime.now(timezone.utc).isoformat()
    username, is_vip, _ = user_ctx
    logger.info("/threads create user=%s vip=%s", username, is_vip)
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
    # Persist empty conversation row immediately
    if conversation_store is not None:
        try:
            conversation_store.create_thread(thread_id=thread_id, user_id=username, title=title)
        except Exception as ce:  # pragma: no cover
            logger.warning(f"Persist empty thread failed thread={thread_id}: {ce}")
    return CreateThreadResponse(
        thread_id=thread_id,
        title=title,
        created_at=now,
        updated_at=now,
    )


@app.get("/threads", response_model=list[ThreadModel])
async def list_threads(limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0), user_ctx: tuple[str, bool, dict] = Depends(_require_user)):
    """List threads for current user (paged, newest first). Falls back to in-memory threads if persistence disabled."""
    username, _, _ = user_ctx
    if conversation_store is None:
        # Build list from in-memory only (no ordering guarantee besides insertion) – dev fallback
        threads = list(_threads.values())
        threads.sort(key=lambda t: t.updated_at, reverse=True)
        return threads[offset: offset + limit]
    try:
        rows = conversation_store.list_threads(user_id=username, limit=limit, offset=offset)
        result = []
        for r in rows:
            result.append(
                ThreadModel(
                    thread_id=r["thread_id"],
                    title=r["title"],
                    created_at=r["created_at"].isoformat() if hasattr(r["created_at"], 'isoformat') else str(r["created_at"]),
                    updated_at=r["updated_at"].isoformat() if hasattr(r["updated_at"], 'isoformat') else str(r["updated_at"]),
                    message_count=r["message_count"],
                )
            )
        return result
    except Exception as e:
        logger.error(f"Failed listing threads: {e}")
        raise HTTPException(status_code=500, detail="Failed to list threads")


@app.get("/threads/{thread_id}", response_model=ThreadModel)
async def get_thread(thread_id: str, user_ctx: tuple[str, bool, dict] = Depends(_require_user)):
    username, _, _ = user_ctx
    thread = _threads.get(thread_id)
    if thread is None and conversation_store is not None:
        # Hydrate metadata from DB if available
        try:
            meta = conversation_store.get_thread_metadata(thread_id, username)
        except Exception as he:  # pragma: no cover
            logger.warning(f"Hydration metadata failed thread={thread_id}: {he}")
            meta = None
        if meta:
            thread = ThreadModel(
                thread_id=meta["thread_id"],
                title=meta["title"],
                created_at=meta["created_at"].isoformat() if hasattr(meta["created_at"], 'isoformat') else str(meta["created_at"]),
                updated_at=meta["updated_at"].isoformat() if hasattr(meta["updated_at"], 'isoformat') else str(meta["updated_at"]),
                message_count=meta["message_count"],
            )
            _threads[thread_id] = thread
            # Load messages into in-memory history lazily
            try:
                msgs = conversation_store.hydrate_messages_if_missing(thread_id, username)
                # Persisted messages now only contain role+content. We synthesize timestamps
                # for in-memory display using thread created_at (or current time) and monotonic
                # ordering (not stored back to DB).
                base_ts = datetime.now(timezone.utc).isoformat()
                synthesized = []
                for idx, m in enumerate(msgs):
                    synthesized.append(
                        MessageModel(
                            message_id=os.urandom(8).hex(),
                            thread_id=thread_id,
                            role=m.get("role"),
                            content=m.get("content"),
                            timestamp=base_ts,
                        )
                    )
                _history[thread_id] = synthesized
            except Exception as me:  # pragma: no cover
                logger.warning(f"Hydration messages failed thread={thread_id}: {me}")
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@app.post("/threads/{thread_id}/messages", response_model=SendMessageResponse)
async def send_message(thread_id: str, payload: SendMessageRequest, user_ctx: tuple[str, bool, dict] = Depends(_require_user)):
    thread = _threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    username, is_vip, _ = user_ctx
    logger.info("/threads/%s/messages user=%s vip=%s", thread_id, username, is_vip)

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
    # Persist user message immediately for durability
    if conversation_store is not None:
        try:
            conversation_store.upsert_message(
                thread_id=thread_id,
                user_id=username,
                message=conversation_store.build_message("user", payload.message),
            )
        except Exception as pe:  # pragma: no cover
            logger.warning(f"Persist user message failed thread={thread_id}: {pe}")

    # Use provider state via Responses API (if we already have a provider-generated response)
    prev_resp_id = _last_response_id.get(thread_id)

    # Semantic cache only for very first user turn (history length == 1 just added)
    if (
        semantic_cache_service is not None
        and getattr(semantic_cache_service, 'enabled', False)
        and len(_history[thread_id]) == 1
    ):
        try:
            hit = await semantic_cache_service.lookup(payload.message)
        except Exception as e:  # pragma: no cover
            logger.warning(f"Semantic cache lookup failed: {e}")
            hit = None
        if hit:
            from src.services.semantic_cache_service import SemanticCacheService as _SCS
            _SCS.seed_history_with_hit(_history[thread_id], thread_id, hit, MessageModel)
            _semantic_cache_bootstrap[thread_id] = {
                "user": payload.message,
                "assistant": hit.answer,
                "injected": False,
            }
            thread.message_count = len(_history[thread_id])
            thread.updated_at = now
            logger.info("Responded from semantic cache; skipping model call")
            return SendMessageResponse(
                message_id=message_id,
                thread_id=thread_id,
                user_message=payload.message,
                assistant_response=hit.answer,
                timestamp=now,
            )
    # Build system prompt from template and optional RAG context
    rag_context = None
    if 'rag_service' in globals() and rag_service is not None and getattr(rag_service, 'enabled', False):
        try:
            rag_context = await rag_service.get_relevant_context(payload.message)
        except Exception as re:
            logger.warning(f"RAG context fetch failed; proceeding without context: {re}")
    user_profile_json = ""
    if _user_profile_enabled and user_profile_service is not None:
        try:
            prof = user_profile_service.get_profile(username)
            if prof:
                user_profile_json = json.dumps(prof, ensure_ascii=False)
        except Exception as pe:  # pragma: no cover
            logger.warning(f"User profile fetch failed user={username}: {pe}")

    base_prompt = template_service.render_template(
        "system_prompt.j2",
        {
            "user_location": None,
            "seasonal_products": [],
            "user_preferences": [],
            "simple_rag": rag_context or "",
            "user_profile": user_profile_json,
            "user_id": username,
            "config": config_service.config,
            "memory_write_profile_enabled": bool(_user_profile_enabled and user_profile_service is not None),
        },
    )
    # Inject prior cached turn transcript if applicable (first real LLM turn)
    if prev_resp_id is None and thread_id in _semantic_cache_bootstrap and not _semantic_cache_bootstrap[thread_id]["injected"]:
        boot = _semantic_cache_bootstrap[thread_id]
        user_q = boot["user"].replace("</conversation_history>", "</conversation_history_escaped>")
        assist_a = boot["assistant"].replace("</conversation_history>", "</conversation_history_escaped>")
        transcript = (
            "\n<conversation_history>\n"
            f"User: {user_q}\n"
            f"Assistant: {assist_a}\n"
            "</conversation_history>\n"
        )
        system_prompt = base_prompt + transcript
        _semantic_cache_bootstrap[thread_id]["injected"] = True
        logger.info("Injected semantic cache transcript into first real LLM turn")
    else:
        system_prompt = base_prompt
    logger.debug(f"Rendered system prompt for /threads/{thread_id}/messages:\n{system_prompt}")
    try:
        text, response_id = await openai_service.generate_response(
            user_text=payload.message,
            system_prompt=system_prompt,
            previous_response_id=prev_resp_id,
            user_is_vip=is_vip,
            user_id=username,
            attachments=payload.attachments if payload.attachments else None,
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
    if conversation_store is not None:
        try:
            conversation_store.upsert_message(
                thread_id=thread_id,
                user_id=username,
                message=conversation_store.build_message("assistant", text),
            )
        except Exception as pe:  # pragma: no cover
            logger.warning(f"Persist assistant message failed thread={thread_id}: {pe}")

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
async def send_message_stream(thread_id: str, payload: SendMessageRequest, user_ctx: tuple[str, bool, dict] = Depends(_require_user)):
    """Stream assistant response tokens for a user message in a thread.

    Streams raw text chunks so the frontend can progressively render tokens.
    Also updates lightweight history and server-side state once completed.
    """
    thread = _threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    username, is_vip, _ = user_ctx
    logger.info("/threads/%s/messages/stream user=%s vip=%s", thread_id, username, is_vip)

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
    if conversation_store is not None:
        try:
            conversation_store.upsert_message(
                thread_id=thread_id,
                user_id=username,
                message=conversation_store.build_message("user", payload.message),
            )
        except Exception as pe:  # pragma: no cover
            logger.warning(f"Persist streaming user message failed thread={thread_id}: {pe}")

    prev_resp_id = _last_response_id.get(thread_id)

    # Semantic cache fast path for first turn (streaming variant)
    if (
        semantic_cache_service is not None
        and getattr(semantic_cache_service, 'enabled', False)
        and len(_history[thread_id]) == 1
    ):
        try:
            hit = await semantic_cache_service.lookup(payload.message)
        except Exception as e:  # pragma: no cover
            logger.warning(f"Semantic cache lookup failed (stream): {e}")
            hit = None
        if hit:
            from src.services.semantic_cache_service import SemanticCacheService as _SCS
            _SCS.seed_history_with_hit(_history[thread_id], thread_id, hit, MessageModel)
            _semantic_cache_bootstrap[thread_id] = {
                "user": payload.message,
                "assistant": hit.answer,
                "injected": False,
            }
            thread.message_count = len(_history[thread_id])
            thread.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info("Streaming fast path: semantic cache hit")
            # Return single-chunk streaming response
            async def single_chunk():
                yield hit.answer
            return StreamingResponse(single_chunk(), media_type="text/plain; charset=utf-8")

    # Build system prompt with optional RAG and stock context (parity with non-stream endpoints)
    rag_context = None
    if 'rag_service' in globals() and rag_service is not None and getattr(rag_service, 'enabled', False):
        try:
            rag_context = await rag_service.get_relevant_context(payload.message)
        except Exception as re:
            logger.warning(f"RAG context fetch failed; proceeding without context: {re}")
    user_profile_json = ""
    if _user_profile_enabled and user_profile_service is not None:
        try:
            prof = user_profile_service.get_profile(username)
            if prof:
                user_profile_json = json.dumps(prof, ensure_ascii=False)
        except Exception as pe:  # pragma: no cover
            logger.warning(f"User profile fetch failed user={username}: {pe}")

    base_prompt = template_service.render_template(
        "system_prompt.j2",
        {
            "user_location": None,
            "seasonal_products": [],
            "user_preferences": [],
            "simple_rag": rag_context or "",
            "user_profile": user_profile_json,
            "user_id": username,
            "config": config_service.config,
            # Stock data excluded; function calling path only.
                "memory_write_profile_enabled": bool(_user_profile_enabled and user_profile_service is not None),
        },
    )
    # Inject transcript if semantic cache provided first answer and first real LLM turn
    if prev_resp_id is None and thread_id in _semantic_cache_bootstrap and not _semantic_cache_bootstrap[thread_id]["injected"]:
        boot = _semantic_cache_bootstrap[thread_id]
        user_q = boot["user"].replace("</conversation_history>", "</conversation_history_escaped>")
        assist_a = boot["assistant"].replace("</conversation_history>", "</conversation_history_escaped>")
        transcript = (
            "\n<conversation_history>\n"
            f"User: {user_q}\n"
            f"Assistant: {assist_a}\n"
            "</conversation_history>\n"
        )
        system_prompt = base_prompt + transcript
        _semantic_cache_bootstrap[thread_id]["injected"] = True
        logger.info("Injected semantic cache transcript into first real LLM turn (stream)")
    else:
        system_prompt = base_prompt

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
    attachments_local = payload.attachments  # Capture for use in nested function
    
    async def token_generator():
        """Loop-based streaming generator following proven GPT-5 reasoning pattern."""
        nonlocal input_messages, response_id_local, full_text, tools
        # Capture last graph search products for optional fallback if model emits no text
        last_graph_products: list[dict] = []
        # Track files generated by code_interpreter for URL replacement
        generated_files: dict[str, str] = {}  # filename -> file_id mapping
        
        while True:
            try:
                # Get tools with file_ids included in code_interpreter container
                current_tools = openai_service.get_tools(file_ids=attachments_local)
                stream_kwargs = {"tools": current_tools} if current_tools else {}
                    
                async with openai_service.client.responses.stream(
                    model=openai_service.model_name,
                    instructions=system_prompt or None,
                    input=input_messages,
                    store=True,
                    previous_response_id=response_id_local or None,
                    reasoning={"effort": getattr(config_service.config, 'reasoning_effort', 'minimal')},
                    **stream_kwargs,
                ) as response:
                    
                    # Collect all items (reasoning + function calls) and tool outputs for next iteration
                    pending_outputs = []
                    current_reasoning_item = None
                    
                    # Capture response_id from the stream object (try multiple attributes)
                    if hasattr(response, 'id'):
                        response_id_local = response.id
                        logger.info(f"Captured response_id from stream.id: {response_id_local}")
                    elif hasattr(response, 'response_id'):
                        response_id_local = response.response_id
                        logger.info(f"Captured response_id from stream.response_id: {response_id_local}")
                    else:
                        logger.warning("Could not find response_id attribute on stream object")
                    
                    # Process streaming events from the model
                    async for event in response:
                        # Try to capture response_id from any event that has it
                        if hasattr(event, "response_id"):
                            if response_id_local is None:
                                response_id_local = event.response_id
                                logger.info(f"✓ Captured response_id from event.response_id: {response_id_local}")
                        
                        # Also check for 'id' attribute on event
                        if response_id_local is None and hasattr(event, "id"):
                            response_id_local = event.id
                            logger.info(f"✓ Captured response_id from event.id: {response_id_local}")
                            
                        et = getattr(event, "type", "")
                        
                        # Stream text deltas directly to client
                        if et == "response.output_text.delta":
                            delta = getattr(event, "delta", "")
                            if delta:
                                # Replace sandbox:// URLs with our API endpoint URLs
                                # This makes generated file links (e.g., plots) clickable
                                import re
                                def replace_sandbox_url(match):
                                    filename = match.group(1)
                                    file_id = generated_files.get(filename)
                                    if file_id:
                                        # Replace with our API endpoint
                                        logger.info(f"Replacing sandbox URL: {filename} -> /files/{file_id}/content")
                                        return f'/files/{file_id}/content'
                                    else:
                                        logger.warning(f"No file_id found for {filename}, mapping: {generated_files}")
                                        return match.group(0)  # Keep original if not found
                                
                                # Check if delta contains sandbox URLs
                                if 'sandbox:' in delta:
                                    logger.info(f"Text delta contains sandbox URL: {delta}")
                                    logger.info(f"Current generated_files mapping: {generated_files}")
                                
                                delta = re.sub(
                                    r'sandbox:/mnt/data/([a-zA-Z0-9_\-\.]+)',
                                    replace_sandbox_url,
                                    delta
                                )
                                full_text += delta
                                yield delta
                        
                        # Code interpreter events
                        elif et == "response.code_interpreter_call.in_progress":
                            # Emit meta event when code interpreter starts
                            meta = {
                                "kind": "tool_event",
                                "event_type": et,
                                "tool_name": "code_interpreter",
                                "status": "in_progress"
                            }
                            logger.info(f"Code interpreter started: {meta}")
                            yield "\nDF_META:" + json.dumps(meta, ensure_ascii=False) + "\n"
                        
                        elif et == "response.code_interpreter_call.interpreting":
                            # Emit meta event during interpretation
                            meta = {
                                "kind": "tool_event",
                                "event_type": et,
                                "tool_name": "code_interpreter",
                                "status": "interpreting"
                            }
                            logger.debug(f"Code interpreter interpreting: {meta}")
                            yield "\nDF_META:" + json.dumps(meta, ensure_ascii=False) + "\n"
                        
                        elif et == "response.code_interpreter_call_code.delta":
                            # Code being streamed - silently captured
                            pass
                        
                        elif et == "response.code_interpreter_call_code.done":
                            # Code finalized
                            code = getattr(event, "code", "")
                            logger.info(f"Code interpreter code finalized: {len(code)} chars")
                        
                        elif et == "response.code_interpreter_call.completed":
                            # Note: streaming events don't contain outputs - will be retrieved in response.completed
                            meta = {
                                "kind": "tool_event",
                                "event_type": et,
                                "tool_name": "code_interpreter",
                                "status": "completed"
                            }
                            logger.info(f"Code interpreter completed: {meta}")
                            yield "\nDF_META:" + json.dumps(meta, ensure_ascii=False) + "\n"
                        
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
                                
                                # Handle code_interpreter_call items (check for output files)
                                elif item_type == "code_interpreter_call":
                                    # Add to input messages
                                    input_messages.append(item)
                                    
                                    # Note: outputs are NOT available in streaming output_item.done events
                                    # We'll retrieve them in response.completed event
                                    logger.info("Code interpreter call item received (outputs not available in streaming)")
                                
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
                                    name = getattr(item, "name", None)
                                    if name == "get_stock":
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
                                    elif name in {"semantic_product_search", "keyword_product_search"}:
                                        try:
                                            if agentic_search_service and agentic_search_service.enabled:
                                                raw_args = getattr(item, "arguments", "{}")
                                                parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else {}
                                                output_json = await agentic_search_service.execute(getattr(item, "name", ""), parsed_args, user_is_vip=is_vip)
                                                pending_outputs.append({
                                                    "type": "function_call_output",
                                                    "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                    "output": output_json,
                                                })
                                                submit_meta = {
                                                    "kind": "tool_event",
                                                    "event_type": "tool.outputs_executed",
                                                    "tool_name": getattr(item, "name", ""),
                                                }
                                                yield "\nDF_META:" + json.dumps(submit_meta, ensure_ascii=False) + "\n"
                                            else:
                                                pending_outputs.append({
                                                    "type": "function_call_output",
                                                    "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                    "output": json.dumps({"products": []}),
                                                })
                                        except Exception as exec_e:  # noqa: BLE001
                                            logger.warning(f"Agentic search function execution error: {exec_e}")
                                    elif name in {"graph_dfs_similarity_search", "graph_bfs_taxonomy_search"}:
                                        try:
                                            # Access underlying graph search service via openai_service (if initialized)
                                            gs = getattr(openai_service, "_graph_search", None)
                                            if gs and getattr(gs, "enabled", False):
                                                raw_args = getattr(item, "arguments", "{}")
                                                try:
                                                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else {}
                                                except Exception:
                                                    parsed_args = {}
                                                try:
                                                    output_json = await gs.execute(name, parsed_args, user_is_vip=is_vip)  # type: ignore[func-returns-value]
                                                except Exception as ge:  # noqa: BLE001
                                                    logger.warning(f"Graph search execution failed (stream) {ge}")
                                                    output_json = json.dumps({"products": []})
                                                # Parse for fallback products capture
                                                try:
                                                    payload = json.loads(output_json)
                                                except Exception:
                                                    payload = {"products": []}
                                                prods = payload.get("products") if isinstance(payload, dict) else []
                                                if isinstance(prods, list):
                                                    last_graph_products = prods
                                                logger.info(
                                                    "Graph tool executed (stream) name=%s products=%d", name, len(last_graph_products)
                                                )
                                                if last_graph_products:
                                                    logger.debug(
                                                        "Graph tool sample product_ids=%s",
                                                        [p.get("product_id") for p in last_graph_products[:5]],
                                                    )
                                                pending_outputs.append({
                                                    "type": "function_call_output",
                                                    "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                    "output": output_json,
                                                })
                                                submit_meta = {
                                                    "kind": "tool_event",
                                                    "event_type": "tool.outputs_executed",
                                                    "tool_name": name,
                                                    "products_count": len(last_graph_products),
                                                }
                                                yield "\nDF_META:" + json.dumps(submit_meta, ensure_ascii=False) + "\n"
                                            else:
                                                pending_outputs.append({
                                                    "type": "function_call_output",
                                                    "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                    "output": json.dumps({"products": []}),
                                                })
                                        except Exception as exec_e:  # noqa: BLE001
                                            logger.warning(f"Graph search function execution error: {exec_e}")
                                    elif name == "memory_search":
                                        try:
                                            if memory_search_service and memory_search_service.enabled:
                                                raw_args = getattr(item, "arguments", "{}")
                                                try:
                                                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else {}
                                                except Exception:
                                                    parsed_args = {}
                                                output_json = await memory_search_service.execute(parsed_args, user_id=username)
                                                pending_outputs.append({
                                                    "type": "function_call_output",
                                                    "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                    "output": output_json,
                                                })
                                                submit_meta = {
                                                    "kind": "tool_event",
                                                    "event_type": "tool.outputs_executed",
                                                    "tool_name": "memory_search",
                                                }
                                                yield "\nDF_META:" + json.dumps(submit_meta, ensure_ascii=False) + "\n"
                                            else:
                                                pending_outputs.append({
                                                    "type": "function_call_output",
                                                    "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                    "output": json.dumps({"memories": []}),
                                                })
                                        except Exception as exec_e:  # noqa: BLE001
                                            logger.warning(f"Memory search function execution error: {exec_e}")
                                    elif name == "memory_write_profile":
                                        logger.info(f"memory_write_profile called in streaming path: user_id={username}")
                                        try:
                                            prof_enabled_flag = os.getenv("USER_PROFILE_ENABLED", "false").lower() in ["true","1","yes","on"]
                                            if username and prof_enabled_flag and user_profile_service:
                                                raw_args = getattr(item, "arguments", "{}")
                                                try:
                                                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else {}
                                                except Exception:
                                                    parsed_args = {}
                                                patch = parsed_args.get("patch", {})
                                                logger.info(f"memory_write_profile executing patch: {patch}")
                                                
                                                try:
                                                    report = user_profile_service.apply_patch_with_report(username, patch)
                                                    logger.info(f"memory_write_profile result: applied={report.get('applied')} updated={report.get('updated')}")
                                                    
                                                    pending_outputs.append({
                                                        "type": "function_call_output",
                                                        "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                        "output": json.dumps(report),
                                                    })
                                                    submit_meta = {
                                                        "kind": "tool_event",
                                                        "event_type": "tool.outputs_executed",
                                                        "tool_name": "memory_write_profile",
                                                        "applied": report.get("applied"),
                                                        "updated_fields": report.get("updated", []),
                                                    }
                                                    yield "\nDF_META:" + json.dumps(submit_meta, ensure_ascii=False) + "\n"
                                                except Exception as pe:
                                                    logger.error(f"memory_write_profile execution failed: {pe}")
                                                    pending_outputs.append({
                                                        "type": "function_call_output",
                                                        "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                        "output": json.dumps({"applied": False, "error": "execution_failed"}),
                                                    })
                                            else:
                                                logger.warning(f"memory_write_profile disabled: user_id={username} enabled={prof_enabled_flag} service={bool(user_profile_service)}")
                                                pending_outputs.append({
                                                    "type": "function_call_output",
                                                    "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                    "output": json.dumps({"applied": False, "error": "disabled"}),
                                                })
                                        except Exception as exec_e:  # noqa: BLE001
                                            logger.warning(f"Memory write profile function execution error: {exec_e}")
                                    elif name == "query_chef_services":
                                        # Chef Agent tool - delegate culinary service queries to specialized agent
                                        logger.info("=" * 80)
                                        logger.info("🍳 DREAMFARM: Model decided to call query_chef_services")
                                        try:
                                            chef_client = getattr(openai_service, "_chef_agent", None)
                                            if chef_client:
                                                raw_args = getattr(item, "arguments", "{}")
                                                try:
                                                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else {}
                                                except Exception:
                                                    parsed_args = {}
                                                
                                                user_message = parsed_args.get("message", "")
                                                logger.info("🍳 DREAMFARM: Extracted message: %s", user_message[:100])
                                                logger.info("🍳 DREAMFARM: Calling Chef Agent client...")
                                                
                                                try:
                                                    chef_response = await chef_client.query(user_message)
                                                    logger.info("✅ DREAMFARM: Chef Agent returned response (%d chars)", len(chef_response))
                                                    logger.info("Response preview: %s", chef_response[:150])
                                                    logger.info("=" * 80)
                                                    
                                                    pending_outputs.append({
                                                        "type": "function_call_output",
                                                        "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                        "output": chef_response,
                                                    })
                                                    submit_meta = {
                                                        "kind": "tool_event",
                                                        "event_type": "tool.outputs_executed",
                                                        "tool_name": "query_chef_services",
                                                        "response_length": len(chef_response),
                                                    }
                                                    yield "\nDF_META:" + json.dumps(submit_meta, ensure_ascii=False) + "\n"
                                                except Exception as ce:
                                                    logger.error("❌ DREAMFARM: Chef Agent execution failed: %s", ce)
                                                    logger.error("=" * 80)
                                                    pending_outputs.append({
                                                        "type": "function_call_output",
                                                        "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                        "output": json.dumps({"error": "Chef Agent query failed", "details": str(ce)}),
                                                    })
                                            else:
                                                logger.warning("⚠️ DREAMFARM: query_chef_services disabled - chef_client not available")
                                                pending_outputs.append({
                                                    "type": "function_call_output",
                                                    "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                                    "output": json.dumps({"error": "Chef Agent not available"}),
                                                })
                                        except Exception as exec_e:  # noqa: BLE001
                                            logger.warning("❌ DREAMFARM: Chef Agent function execution error: %s", exec_e)
                                    else:
                                        # Unknown/unhandled function call - add empty output to avoid breaking loop
                                        logger.warning(f"Unhandled function call in streaming: {name}")
                                        pending_outputs.append({
                                            "type": "function_call_output",
                                            "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                                            "output": json.dumps({"error": "unhandled_function"}),
                                        })
                        
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
                        
                # After stream ends (still inside async with response block), assemble the final response snapshot.
                logger.info(f"Stream processing completed, response_id_local={response_id_local}")

                final_response = None

                # Preferred path: leverage the stream helper to obtain the accumulated response without another API call.
                if hasattr(response, "get_final_response"):
                    try:
                        final_response = await response.get_final_response()
                        if final_response is not None:
                            logger.info("✓ Obtained final response from stream manager")
                            # Always capture/update response_id from final_response if available
                            final_resp_id = getattr(final_response, "id", None)
                            if final_resp_id:
                                response_id_local = final_resp_id
                                logger.info(f"✓ Captured response_id from final_response.id: {response_id_local}")
                            elif response_id_local is None:
                                logger.warning("final_response has no 'id' attribute and response_id_local is None")
                    except Exception as stream_final_err:  # pragma: no cover
                        logger.warning(f"Unable to obtain final response from stream manager: {stream_final_err}")

                # Fallback: perform explicit retrieval if we still lack the full response object.
                if final_response is None and response_id_local:
                    try:
                        logger.info(f"Retrieving full response {response_id_local} for code_interpreter file annotations...")
                        final_response = await openai_service.client.responses.retrieve(response_id_local)
                    except Exception as retrieve_err:  # pragma: no cover
                        logger.exception(f"Failed to retrieve response {response_id_local} for annotations: {retrieve_err}")

                if final_response is not None:
                    output_files = []
                    visualization_artifacts = []
                    
                    if hasattr(final_response, 'output'):
                        for item in final_response.output:
                            # Look for message items with content
                            if item.type == 'message' and hasattr(item, 'content'):
                                for content_block in item.content:
                                    # Check for annotations containing file references
                                    if hasattr(content_block, 'annotations') and content_block.annotations:
                                        for annotation in content_block.annotations:
                                            if hasattr(annotation, 'file_id'):
                                                container_id = getattr(annotation, 'container_id', None)
                                                file_id = getattr(annotation, 'file_id', None)
                                                filename = getattr(annotation, 'filename', None)

                                                if file_id and filename:
                                                    generated_files[filename] = file_id
                                                    download_token = _register_generated_file(file_id, container_id, filename)
                                                    logger.info(f"✓ Extracted from annotation: {filename} -> {file_id} (container: {container_id})")

                                                    output_files.append({
                                                        "type": "file",
                                                        "file_id": file_id,
                                                        "container_id": container_id,
                                                        "filename": filename,
                                                        "download_token": download_token,
                                                    })
                                                else:
                                                    logger.warning(f"Annotation missing file_id or filename: {annotation}")
                            
                            # Look for MCP tool calls (visualization artifacts)
                            elif item.type == 'mcp_call':
                                tool_name = getattr(item, 'name', None)
                                logger.debug(f"Found MCP tool call: {tool_name}")
                                if tool_name == 'generate_infographic':
                                    # Check if tool has output
                                    output_content = getattr(item, 'output', None)
                                    logger.debug(f"MCP output_content type: {type(output_content)}, value: {output_content}")
                                    if output_content:
                                        try:
                                            # Parse output (should be JSON with html field)
                                            if isinstance(output_content, str):
                                                logger.debug(f"Parsing output as string (length: {len(output_content)})")
                                                output_data = json.loads(output_content)
                                            elif isinstance(output_content, list) and len(output_content) > 0:
                                                logger.debug(f"Parsing output as list (length: {len(output_content)})")
                                                # Output may be array of content items
                                                text_item = next((c for c in output_content if getattr(c, 'type', None) == 'text'), None)
                                                if text_item:
                                                    output_data = json.loads(getattr(text_item, 'text', '{}'))
                                                else:
                                                    output_data = {}
                                            else:
                                                logger.debug(f"Output format not recognized: {type(output_content)}")
                                                output_data = {}
                                            
                                            logger.debug(f"Parsed output_data keys: {output_data.keys() if isinstance(output_data, dict) else 'not a dict'}")
                                            
                                            if output_data.get('type') == 'custom_ui' and output_data.get('html'):
                                                html_content = output_data['html']
                                                artifact_id = str(uuid.uuid4())
                                                
                                                # Register HTML artifact
                                                _register_html_artifact(artifact_id, html_content, thread_id)
                                                logger.info(f"✓ Registered visualization artifact: {artifact_id} ({len(html_content)} chars)")
                                                logger.debug(f"HTML preview (first 200 chars): {html_content[:200]}")
                                                
                                                visualization_artifacts.append({
                                                    "artifact_id": artifact_id,
                                                    "tool_name": tool_name,
                                                    "html_length": len(html_content),
                                                })
                                            else:
                                                logger.warning(f"MCP output missing 'type:custom_ui' or 'html' field. Keys: {output_data.keys() if isinstance(output_data, dict) else type(output_data)}")
                                        except Exception as viz_err:  # noqa: BLE001
                                            logger.exception(f"Failed to parse MCP tool output: {viz_err}")
                                    else:
                                        logger.warning(f"MCP tool {tool_name} has no output content")

                    if output_files:
                        files_meta = {
                            "kind": "tool_event",
                            "event_type": "code_interpreter.files_generated",
                            "tool_name": "code_interpreter",
                            "files": output_files
                        }
                        logger.info(f"Sending {len(output_files)} file mappings to frontend: {files_meta}")
                        yield "\nDF_META:" + json.dumps(files_meta, ensure_ascii=False) + "\n"
                    else:
                        logger.info("No file annotations found in response")
                    
                    # Emit visualization artifact events
                    for viz_artifact in visualization_artifacts:
                        artifact_meta = {
                            "kind": "tool_event",
                            "event_type": "visualization.artifact_created",
                            "tool_name": viz_artifact["tool_name"],
                            "artifact_id": viz_artifact["artifact_id"],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        logger.info(f"Sending visualization artifact to frontend: {artifact_meta}")
                        yield "\nDF_META:" + json.dumps(artifact_meta, ensure_ascii=False) + "\n"
                        
                        # Insert artifact link in response text for rendering
                        artifact_link = f"\n\n[View Visualization](/artifacts/{viz_artifact['artifact_id']})\n\n"
                        yield artifact_link
                        
                elif response_id_local:
                    logger.warning(f"Final response not available even after retrieval attempt (response_id={response_id_local})")
                else:
                    logger.warning("Final response not available and response_id could not be determined")
                
                # Check if we need to continue the loop
                if not pending_outputs:
                    break  # No more tool calls → finished
                    
                # Replace input with tool outputs (previous context is in previous_response_id)
                # We MUST NOT include the original messages again, as that causes duplicate ID errors
                input_messages = pending_outputs
                logger.info(f"Continuing reasoning loop with {len(pending_outputs)} tool output(s)")
                
            except Exception as e:
                logger.error(f"Streaming loop failed: {e}", exc_info=True)
                # Try to extract more details from OpenAI API errors
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    logger.error(f"API response body: {e.response.text}")
                elif hasattr(e, 'body'):
                    logger.error(f"Error body: {e.body}")
                break
        
        # Auto-fallback if model produced no text but we have graph products
        if not full_text and last_graph_products:
            lines = ["(Auto-summary) Výsledky z grafového nástroje:"]
            for p in last_graph_products[:10]:
                lines.append(
                    f"- {p.get('product_name')} ({p.get('producer_name')}) score={p.get('similarity_score')}"
                )
            fallback_text = "\n".join(lines)
            full_text = fallback_text
            logger.info(
                "Synthesized fallback text (stream) from %d graph products", len(last_graph_products)
            )
            # Yield fallback to client
            yield fallback_text

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
        if conversation_store is not None:
            try:
                conversation_store.upsert_message(
                    thread_id=thread_id,
                    user_id=username,
                    message=conversation_store.build_message("assistant", full_text),
                )
            except Exception as pe:  # pragma: no cover
                logger.warning(f"Persist streaming assistant message failed thread={thread_id}: {pe}")
        thread.message_count = len(_history[thread_id])
        thread.updated_at = datetime.now(timezone.utc).isoformat()

    return StreamingResponse(token_generator(), media_type="text/plain; charset=utf-8")


@app.get("/threads/{thread_id}/messages", response_model=GetMessagesResponse)
async def get_messages(thread_id: str, limit: int = 50, offset: int = 0, user_ctx: tuple[str, bool, dict] = Depends(_require_user)):
    username, is_vip, _ = user_ctx
    if thread_id not in _threads:
        # Attempt lazy hydration if persistence available
        if conversation_store is not None:
            try:
                meta = conversation_store.get_thread_metadata(thread_id, username)
            except Exception as he:  # pragma: no cover
                logger.warning(f"Hydration (messages) metadata failed thread={thread_id}: {he}")
                meta = None
            if meta:
                hydrated = ThreadModel(
                    thread_id=meta["thread_id"],
                    title=meta["title"],
                    created_at=meta["created_at"].isoformat() if hasattr(meta["created_at"], 'isoformat') else str(meta["created_at"]),
                    updated_at=meta["updated_at"].isoformat() if hasattr(meta["updated_at"], 'isoformat') else str(meta["updated_at"]),
                    message_count=meta["message_count"],
                )
                _threads[thread_id] = hydrated
                try:
                    msgs = conversation_store.hydrate_messages_if_missing(thread_id, username)
                    base_ts = datetime.now(timezone.utc).isoformat()
                    _history[thread_id] = [
                        MessageModel(
                            message_id=os.urandom(8).hex(),
                            thread_id=thread_id,
                            role=m.get("role"),
                            content=m.get("content"),
                            timestamp=base_ts,
                        ) for m in msgs
                    ]
                except Exception as me:  # pragma: no cover
                    logger.warning(f"Hydration (messages) failed thread={thread_id}: {me}")
        if thread_id not in _threads:
            raise HTTPException(status_code=404, detail="Thread not found")
    logger.info("/threads/%s/messages GET user=%s vip=%s", thread_id, username, is_vip)
    msgs = _history.get(thread_id, [])
    total = len(msgs)
    paginated = msgs[offset : offset + limit]
    return GetMessagesResponse(thread_id=thread_id, messages=paginated, total_count=total)


@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str, user_ctx: tuple[str, bool, dict] = Depends(_require_user)):
    """Delete a conversation thread (memory + persistence)."""
    username, _, _ = user_ctx
    existed = thread_id in _threads
    _threads.pop(thread_id, None)
    _history.pop(thread_id, None)
    _last_response_id.pop(thread_id, None)
    _semantic_cache_bootstrap.pop(thread_id, None)
    db_deleted = 0
    if conversation_store is not None:
        try:
            db_deleted = conversation_store.delete_conversation(thread_id, username)
        except Exception as de:  # pragma: no cover
            logger.warning(f"Failed deleting persisted conversation thread={thread_id}: {de}")
    if not existed and db_deleted == 0:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"thread_id": thread_id, "deleted": True}


def _rename_thread_internal(thread_id: str, new_title: str, username: str) -> ThreadModel:
    """Internal helper to rename a thread (in-memory + persistence)."""
    if thread_id not in _threads and conversation_store is not None:
        meta = conversation_store.get_thread_metadata(thread_id, username)
        if meta:
            hydrated = ThreadModel(
                thread_id=meta["thread_id"],
                title=meta["title"],
                created_at=meta["created_at"].isoformat() if hasattr(meta["created_at"], 'isoformat') else str(meta["created_at"]),
                updated_at=meta["updated_at"].isoformat() if hasattr(meta["updated_at"], 'isoformat') else str(meta["updated_at"]),
                message_count=meta["message_count"],
            )
            _threads[thread_id] = hydrated
    thread = _threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if conversation_store is not None:
        try:
            updated = conversation_store.rename_thread(thread_id, username, new_title)
            if updated == 0:
                raise HTTPException(status_code=404, detail="Thread not found")
        except HTTPException:
            raise
        except Exception as e:  # pragma: no cover
            logger.warning(f"Rename failed persisted thread={thread_id}: {e}")
    thread.title = new_title
    thread.updated_at = datetime.now(timezone.utc).isoformat()
    return thread


@app.put("/threads/{thread_id}/title", response_model=ThreadModel)
async def rename_thread(thread_id: str, payload: ThreadRenameRequest, user_ctx: tuple[str, bool, dict] = Depends(_require_user)):
    """Rename a thread title (single canonical endpoint using PUT)."""
    username, _, _ = user_ctx
    return _rename_thread_internal(thread_id, payload.title, username)


@app.websocket("/voice/{thread_id}")
async def voice_endpoint(websocket: WebSocket, thread_id: str):
    """WebSocket endpoint for voice/realtime conversations.
    
    Handles speech-to-speech interaction via OpenAI Realtime API.
    Persists transcripts with mode='voice' flag.
    """


    await websocket.accept()
    
    # Extract auth from query params (WebSocket doesn't support headers easily)
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return
    
    # Validate token
    if auth_service is None:
        await websocket.close(code=4003, reason="Auth service not available")
        return
    
    try:
        claims = auth_service.validate(token)
        username, is_vip = auth_service.extract_identity(claims)
    except Exception as e:
        logger.warning(f"Voice auth failed: {e}")
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    # Check voice service availability
    if voice_service is None:
        await websocket.close(code=4003, reason="Voice service not available")
        return
    
    logger.info("Voice session starting: thread=%s user=%s vip=%s", thread_id, username, is_vip)
    
    # Build system prompt with user profile
    user_profile_json = ""
    if _user_profile_enabled and user_profile_service is not None:
        try:
            prof = user_profile_service.get_profile(username)
            if prof:
                user_profile_json = json.dumps(prof, ensure_ascii=False)
        except Exception as pe:
            logger.warning(f"User profile fetch failed user={username}: {pe}")
    
    system_prompt = template_service.render_template(
        "system_prompt.j2",
        {
            "user_location": None,
            "seasonal_products": [],
            "user_preferences": [],
            "simple_rag": "",
            "user_profile": user_profile_json,
            "user_id": username,
            "config": config_service.config,
            "memory_write_profile_enabled": False,  # Disabled in voice mode
        },
    )
    
    # Handle voice session
    try:
        enable_heavy = websocket.query_params.get("enable_heavy_tools", "false").lower() == "true"
        await voice_service.handle_voice_session(
            websocket=websocket,
            thread_id=thread_id,
            user_id=username,
            system_prompt=system_prompt,
            enable_heavy_tools=enable_heavy,
        )
    except WebSocketDisconnect:
        logger.info("Voice session disconnected: thread=%s user=%s", thread_id, username)
    except Exception as e:
        logger.error(f"Voice session error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass


def main():
    """Main entry point for the application."""
    import uvicorn
    
    # Get uvicorn logging config that uses OTLP-enabled root logger
    if otel_enabled:
        from src.utils.otel_logging import get_uvicorn_log_config
        log_config = get_uvicorn_log_config()
        uvicorn.run(app, host="0.0.0.0", port=8001, log_config=log_config)
    else:
        uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()

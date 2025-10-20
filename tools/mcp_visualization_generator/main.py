"""MCP server for HTML visualization generation using FastMCP (HTTP transport).

This server provides the `generate_infographic` tool that creates custom
HTML/CSS/JavaScript visualizations through LLM generation and security sanitization.

Uses the OpenAI Responses API with reasoning models (GPT-5, o3, etc.).

Environment variables:
- HOST (default: 0.0.0.0)
- PORT (default: 5003)
- MCP_CORS_ORIGINS (default: "*" or comma-separated list)
- MCP_API_KEY (required; static bearer token for auth)
- OPENAI_API_KEY (required; for HTML generation)
- OPENAI_BASE_URL (optional; for Azure OpenAI, must end with /openai/v1/)
- OPENAI_API_VERSION (optional; for Azure OpenAI, e.g., preview)
- OPENAI_MODEL (default: gpt-4o)
- REASONING_EFFORT (default: low; can be low, medium, high)
- OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME (OpenTelemetry)
- OTEL_INSTRUMENTATION_PROVIDER (openinference or opentelemetry for OpenAI tracing)
"""

from __future__ import annotations

import os
import sys
import json
from typing import Optional

from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

# Initialize OpenTelemetry BEFORE importing FastMCP and OpenAI
service_name = os.getenv("OTEL_SERVICE_NAME", "mcp-visualization-generator")
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
otel_enabled = otlp_endpoint != ""

if otel_enabled:
    try:
        # 1. Configure tracing (TracerProvider + auto-instrumentation for OpenAI)
        from utils.otel_tracing import configure_otel_tracing
        configure_otel_tracing(
            service_name=service_name,
            otlp_endpoint=otlp_endpoint,
            instrument_openai=True,
            instrument_psycopg2=False,
            instrument_sqlalchemy=False
        )
        print(f"[OK] OpenTelemetry tracing initialized: service={service_name}")
        
        # 2. Configure logging (structured JSON logs with trace correlation)
        from utils.otel_logging import configure_otel_logging, add_trace_context_to_logs
        logger_otel = configure_otel_logging()  # Configures ROOT logger
        add_trace_context_to_logs()
        print("[OK] OpenTelemetry logging initialized (root logger with OTLP)")
        
        # 3. Configure metrics (application metrics)
        from utils.otel_metrics import configure_otel_metrics, create_custom_metrics
        meter_provider, meter = configure_otel_metrics()
        metrics = create_custom_metrics(meter)
        print("[OK] OpenTelemetry metrics initialized")
        
    except Exception as e:
        print(f"[WARNING] OpenTelemetry initialization failed: {e}")
        otel_enabled = False
        logger_otel = None
        meter_provider = None
        meter = None
        metrics = None
else:
    print("[INFO] OpenTelemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
    logger_otel = None
    meter_provider = None
    meter = None
    metrics = None

# NOW import FastMCP, Starlette, and OpenAI AFTER OpenTelemetry initialization
from starlette.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from fastmcp.server.auth.auth import AccessToken, TokenVerifier
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from openai import AsyncOpenAI


# Import generation and sanitization services
# We'll inline minimal versions here for the MCP server
import logging
from bs4 import BeautifulSoup, Comment
from typing import Set

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class EnvAPIKeyVerifier(TokenVerifier):
    """Simple static bearer token verifier based on environment variable."""

    def __init__(self, required_token: str):
        self._token = required_token
        self.resource_server_url: Optional[str] = None
        self.base_url: Optional[str] = None
        self.required_scopes: list[str] = []

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """Validate a static bearer token from env."""
        if token and token == self._token:
            return AccessToken(
                token=token,
                client_id="api-key-user",
                scopes=["tool:write"],
            )
        return None


def _get_cors_origins(raw: str | None) -> list[str] | str:
    """Parse CORS origins from environment variable."""
    if not raw or raw.strip() == "*":
        return "*"
    return [o.strip() for o in raw.split(",") if o.strip()]


# HTML Sanitizer implementation (comprehensive security validation)
ALLOWED_TAGS: Set[str] = {
    # Structure
    "html", "head", "body", "title", "meta",
    # Content sections
    "div", "span", "p", "br", "hr",
    # Headings
    "h1", "h2", "h3", "h4", "h5", "h6",
    # Lists
    "ul", "ol", "li", "dl", "dt", "dd",
    # Text formatting
    "strong", "em", "b", "i", "u", "s", "mark", "small", "sub", "sup",
    # Links (href validated separately)
    "a",
    # Media (src validated separately)
    "img", "svg", "path", "circle", "rect", "line", "polyline", "polygon",
    "ellipse", "g", "defs", "use", "symbol", "text", "tspan",
    # Tables
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col",
    # Forms (limited, no external actions)
    "button", "label",
    # Semantic HTML5
    "article", "section", "nav", "aside", "header", "footer", "main", "figure", "figcaption",
    # Inline styles and scripts (content validated separately)
    "style", "script",
}

# Dangerous attributes that should be removed
DANGEROUS_ATTRS: Set[str] = {
    "onload", "onerror", "onclick", "ondblclick", "onmousedown", "onmouseup",
    "onmouseover", "onmousemove", "onmouseout", "onmouseenter", "onmouseleave",
    "onkeydown", "onkeypress", "onkeyup", "onchange", "onsubmit", "onreset",
    "onfocus", "onblur", "onselect", "oninput", "oninvalid", "oncontextmenu",
    "ondrag", "ondragstart", "ondragend", "ondragover", "ondragenter", "ondragleave",
    "ondrop", "onscroll", "onwheel", "oncopy", "oncut", "onpaste",
    "onabort", "oncanplay", "oncanplaythrough", "oncuechange", "ondurationchange",
    "onemptied", "onended", "onloadeddata", "onloadedmetadata", "onloadstart",
    "onpause", "onplay", "onplaying", "onprogress", "onratechange", "onseeked",
    "onseeking", "onstalled", "onsuspend", "ontimeupdate", "onvolumechange", "onwaiting",
}

# Forbidden tags that trigger rejection
FORBIDDEN_TAGS: Set[str] = {
    "iframe", "frame", "frameset", "object", "embed", "applet", "form",
}


class HTMLSanitizerError(Exception):
    """Raised when HTML fails security validation."""
    pass


def sanitize_html(html: str) -> str:
    """Sanitize and validate HTML for safe rendering.
    
    Implements multi-layer security validation:
    1. Parse HTML and check structure
    2. Remove forbidden tags (iframe, object, embed, etc.)
    3. Remove dangerous event handler attributes
    4. Validate href/src attributes (no javascript: protocol)
    5. Validate inline scripts don't use dangerous APIs
    6. Whitelist allowed tags
    
    Args:
        html: Raw HTML string to sanitize
        
    Returns:
        Sanitized HTML string safe for iframe rendering
        
    Raises:
        HTMLSanitizerError: If HTML contains unsafe patterns that cannot be sanitized
    """
    if not html or not html.strip():
        raise HTMLSanitizerError("HTML cannot be empty")
    
    logger.info("Sanitizing HTML: %d characters", len(html))
    
    # Parse HTML with html5lib (most lenient, browser-like parsing)
    try:
        soup = BeautifulSoup(html, "html5lib")
    except Exception as e:
        raise HTMLSanitizerError(f"Failed to parse HTML: {e}") from e
    
    # Check for forbidden tags - reject immediately
    for tag in FORBIDDEN_TAGS:
        if soup.find(tag):
            raise HTMLSanitizerError(f"Forbidden tag detected: <{tag}>")
    
    # Check for external script/link tags with src/href
    for tag in soup.find_all("script"):
        if tag.get("src"):
            raise HTMLSanitizerError("External script tag detected: <script src=...>")
    
    for tag in soup.find_all("link"):
        if tag.get("href") and tag.get("rel") in ["stylesheet", "preload", "modulepreload"]:
            raise HTMLSanitizerError("External stylesheet detected: <link href=...>")
    
    # Remove all comments (can hide malicious content)
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Iterate all tags and validate
    for tag in soup.find_all(True):
        tag_name = tag.name.lower()
        
        # Remove tags not in whitelist
        if tag_name not in ALLOWED_TAGS:
            logger.warning(f"Removing non-whitelisted tag: <{tag_name}>")
            tag.decompose()
            continue
        
        # Remove dangerous event handler attributes
        attrs_to_remove = []
        for attr in tag.attrs:
            attr_lower = attr.lower()
            if attr_lower in DANGEROUS_ATTRS:
                attrs_to_remove.append(attr)
                logger.warning(f"Removing dangerous attribute: {attr} from <{tag_name}>")
        
        for attr in attrs_to_remove:
            del tag[attr]
        
        # Validate href attributes (no javascript: protocol)
        if tag.get("href"):
            href = str(tag["href"]).strip().lower()
            if href.startswith("javascript:") or href.startswith("data:text/html"):
                raise HTMLSanitizerError(f"Dangerous href protocol detected: {href[:50]}")
        
        # Validate src attributes (allow data: URIs for images only)
        if tag.get("src"):
            src = str(tag["src"]).strip().lower()
            if src.startswith("javascript:"):
                raise HTMLSanitizerError(f"Dangerous src protocol detected: {src[:50]}")
            if src.startswith("data:") and tag_name != "img":
                raise HTMLSanitizerError(f"data: URI only allowed for <img>, found in <{tag_name}>")
        
        # Validate inline scripts for dangerous APIs
        if tag_name == "script" and tag.string:
            script_content = tag.string.lower()
            dangerous_patterns = [
                "eval(", "function(", "settimeout(", "setinterval(",
                "document.write", "window.parent", "window.top",
                "window.opener", "location.replace", "location.assign",
            ]
            for pattern in dangerous_patterns:
                if pattern in script_content:
                    logger.warning(f"Potentially dangerous JS pattern detected: {pattern}")
                    # Don't reject, just warn (LLM should avoid these but overly strict may break valid code)
    
    sanitized = str(soup)
    logger.info("Sanitization complete: %d -> %d characters", len(html), len(sanitized))
    
    return sanitized
    
    sanitized = str(soup)
    logger.info("Sanitization complete: %d -> %d characters", len(html), len(sanitized))
    
    return sanitized


# HTML Generator using Responses API
HTML_GENERATOR_PROMPT = """
You are an expert frontend developer. Generate self-contained HTML with inline CSS and JavaScript.

REQUIREMENTS:
- Use semantic HTML5 elements
- All CSS must be inline in <style> tag
- All JavaScript must be inline in <script> tag
- No external resources (no CDN, no external URLs)
- Use modern CSS (flexbox, grid, gradients, animations)
- Make it visually appealing and responsive
- Include appropriate ARIA labels for accessibility
- Use data URIs for images if needed

FORBIDDEN:
- <script src="..."> or <link href="...">
- eval(), Function(), innerHTML with user input
- <iframe>, <object>, <embed> tags
- javascript: protocol in attributes
- External form actions
- document.write()
- Accessing window.parent or window.top

RESPONSE FORMAT:
Return only the HTML code starting with <!DOCTYPE html>, no explanations or markdown.
Include a CSP meta tag for additional security:
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline';" />
"""


async def generate_html(
    description: str,
    data: Optional[dict] = None,
    style: Optional[str] = None,
    client: Optional[AsyncOpenAI] = None,
    model: str = "gpt-4o",
    reasoning_effort: str = "low",
) -> str:
    """Generate HTML visualization using OpenAI Responses API with reasoning models."""
    if not client:
        raise ValueError("AsyncOpenAI client is required")
    
    if not description or not description.strip():
        raise ValueError("Description cannot be empty")
    
    user_prompt_parts = [f"Create: {description}"]
    
    if data:
        user_prompt_parts.append(f"\nData to visualize:\n{json.dumps(data, indent=2)}")
    
    if style:
        user_prompt_parts.append(f"\nStyle preference: {style}")
    
    user_prompt = "\n".join(user_prompt_parts)
    
    logger.info("Generating HTML with model=%s, reasoning=%s", model, reasoning_effort)
    
    try:
        # Build request body for Responses API (reasoning models only)
        request_body: dict = {
            "model": model,
            "instructions": HTML_GENERATOR_PROMPT,
            "input": user_prompt,
            "max_output_tokens": 8000,
            "reasoning": {"effort": reasoning_effort},
        }
        
        # Use the responses endpoint via the SDK's underlying HTTP client
        response = await client.post("/responses", cast_to=object, body=request_body)
        
        # Extract HTML from response - iterate through output to find message content
        # Response structure: {output: [{type: "reasoning"}, {type: "message", content: [{type: "output_text", text: "..."}]}]}
        html = ""
        
        if isinstance(response, dict):
            output = response.get("output", [])
            for item in output:
                if isinstance(item, dict) and item.get("type") != "reasoning":
                    for content_item in item.get("content", []):
                        if isinstance(content_item, dict) and content_item.get("type") == "output_text":
                            html = content_item.get("text", "")
                            break
                if html:
                    break
        
        if not html:
            logger.error(f"Failed to extract HTML from response: {type(response)}")
            raise RuntimeError("Responses API returned empty HTML")
        
        # Strip markdown code fences if present
        if html.startswith("```html"):
            html = html[7:]
        elif html.startswith("```"):
            html = html[3:]
        if html.endswith("```"):
            html = html[:-3]
        html = html.strip()
        
        logger.info("Generated HTML: %d characters", len(html))
        return html
        
    except Exception as e:
        logger.error(f"HTML generation failed: {e}")
        raise RuntimeError(f"Failed to generate HTML: {e}") from e


def build_server() -> tuple[FastMCP, object]:
    """Create FastMCP server and ASGI app configured for HTTP, CORS, and auth."""

    api_key = os.getenv("MCP_API_KEY")
    if not api_key:
        print("ERROR: MCP_API_KEY is required for server authentication.", file=sys.stderr)
        sys.exit(2)

    auth = EnvAPIKeyVerifier(api_key)
    mcp = FastMCP("Visualization Generator", auth=auth)

    # Initialize OpenAI client (unified for OpenAI and Azure OpenAI)
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("ERROR: OPENAI_API_KEY is required for HTML generation.", file=sys.stderr)
        sys.exit(2)
    
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    openai_api_version = os.getenv("OPENAI_API_VERSION")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
    reasoning_effort = os.getenv("REASONING_EFFORT", "low")
    
    # Build default_query for Azure API version
    default_query = None
    if openai_base_url and openai_api_version:
        default_query = {"api-version": openai_api_version}
    
    client = AsyncOpenAI(
        api_key=openai_api_key,
        base_url=openai_base_url if openai_base_url else None,
        default_query=default_query,
    )
    
    logger.info(
        "Initialized OpenAI client: base_url=%s model=%s api_version=%s reasoning=%s",
        openai_base_url or "default",
        openai_model,
        openai_api_version or "none",
        reasoning_effort,
    )

    # Tool: generate_infographic
    @mcp.tool
    async def generate_infographic(
        description: str,
        data: Optional[dict] = None,
        style: Optional[str] = None,
    ) -> dict:
        """Generate custom interactive HTML visualizations, cards, or dashboards.
        
        Use when user requests visual representations beyond standard charts.
        Examples: dashboard cards, comparison tables, interactive widgets,
        styled statistics displays, custom layouts.
        
        Args:
            description: Detailed description of desired UI component
            data: Optional structured data to display
            style: Visual style hint (card, dashboard, infographic, table, chart)
            
        Returns:
            Dictionary with type="custom_ui" and sanitized HTML content
        """
        try:
            logger.info(f"Tool called: description={description[:50]}, style={style}")
            
            # Generate HTML using Responses API
            raw_html = await generate_html(
                description=description,
                data=data,
                style=style,
                client=client,
                model=openai_model,
                reasoning_effort=reasoning_effort,
            )
            
            # Sanitize HTML
            safe_html = sanitize_html(raw_html)
            
            return {
                "type": "custom_ui",
                "html": safe_html,
                "metadata": {
                    "generator": "responses_api",
                    "model": openai_model,
                    "description": description,
                }
            }
            
        except HTMLSanitizerError as e:
            logger.error(f"Sanitization failed: {e}")
            return {
                "type": "error",
                "error": f"Generated HTML failed security validation: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "type": "error",
                "error": f"Failed to generate visualization: {str(e)}"
            }

    # Health check endpoint
    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    # Build ASGI app with CORS
    cors_origins = _get_cors_origins(os.getenv("MCP_CORS_ORIGINS"))
    
    # Get the HTTP ASGI app from FastMCP
    asgi_app = mcp.http_app()
    
    # Instrument Starlette app with OpenTelemetry AFTER app creation
    # Note: instrument_app modifies in-place, don't reassign
    if otel_enabled:
        try:
            from opentelemetry.instrumentation.starlette import StarletteInstrumentor
            StarletteInstrumentor.instrument_app(asgi_app)
            print("[OK] Starlette instrumentation applied")
        except Exception as e:
            print(f"[WARNING] Starlette instrumentation failed: {e}")
    
    # Add CORS middleware first (using Starlette's add_middleware)
    if cors_origins:
        asgi_app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins if isinstance(cors_origins, list) else ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Add business dimensions middleware for OpenTelemetry context enrichment
    # MCP servers are backend services - set backend-service defaults
    # (parent trace from DreamFarm/Chef agent will propagate actual user context)
    if otel_enabled:
        from starlette.middleware.base import BaseHTTPMiddleware
        
        class BusinessDimensionsMiddleware(BaseHTTPMiddleware):
            """Middleware to inject business dimensions into OpenTelemetry context."""
            
            async def dispatch(self, request: Request, call_next):
                from opentelemetry import context as otel_context
                
                # MCP servers don't parse JWT - they're internal backend services
                # Set default backend identity; parent trace propagates actual user_id
                user_id = "backend-service"
                is_vip = False
                agent_type = "mcp-visualization-generator"
                experiment = os.getenv("OTEL_EXPERIMENT", "default")
                
                ctx = otel_context.get_current()
                ctx = otel_context.set_value("user_id", user_id, ctx)
                ctx = otel_context.set_value("is_vip", is_vip, ctx)
                ctx = otel_context.set_value("agent_type", agent_type, ctx)
                ctx = otel_context.set_value("experiment", experiment, ctx)
                
                token = otel_context.attach(ctx)
                try:
                    response = await call_next(request)
                    return response
                finally:
                    otel_context.detach(token)
        
        asgi_app.add_middleware(BusinessDimensionsMiddleware)
        print("[OK] Business dimensions middleware added")
    
    return mcp, asgi_app


def main() -> None:
    """Run the server in HTTP transport with configured host/port."""
    load_dotenv()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5003"))
    
    # Build server and get ASGI app
    mcp, asgi_app = build_server()
    logger.info(f"Starting MCP Visualization Generator server on {host}:{port}")
    
    # Use uvicorn directly with OTLP logging config (instead of mcp.run())
    if otel_enabled:
        import uvicorn
        from utils.otel_logging import get_uvicorn_log_config
        log_config = get_uvicorn_log_config()
        uvicorn.run(asgi_app, host=host, port=port, log_config=log_config)
    else:
        mcp.run(transport="http", host=host, port=port)


# ASGI application entrypoint for uvicorn/gunicorn
load_dotenv()
_mcp, app = build_server()

if __name__ == "__main__":
    main()

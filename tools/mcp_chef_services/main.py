"""MCP server for chef and catering services using FastMCP (HTTP transport).

Features
- Mock data for chefs, services, availability with deterministic IDs
- Streamable HTTP transport (default)
- Wildcard CORS (configurable)
- Simple static API key auth via Authorization: Bearer <TOKEN>
- Tools: search_chefs, search_services, check_availability, calculate_pricing, place_order

Environment variables
- HOST (default: 0.0.0.0)
- PORT (default: 8013)
- MCP_CORS_ORIGINS (default: "*" or comma-separated list)
- MCP_API_KEY (required; static bearer token for auth)
- OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME (OpenTelemetry)
"""

from __future__ import annotations

import os
import sys
from typing import Optional
from datetime import datetime, timedelta

from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

# Initialize OpenTelemetry BEFORE importing FastMCP or Starlette
service_name = os.getenv("OTEL_SERVICE_NAME", "mcp-chef-services")
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
otel_enabled = otlp_endpoint != ""

if otel_enabled:
    try:
        # 1. Configure tracing (TracerProvider + custom span processor)
        from utils.otel_tracing import configure_otel_tracing
        configure_otel_tracing(
            service_name=service_name,
            otlp_endpoint=otlp_endpoint,
            instrument_openai=False,
            instrument_psycopg2=False,
            instrument_sqlalchemy=False
        )
        print(f"[OK] OpenTelemetry tracing initialized: service={service_name}")
        
        # 2. Configure logging (structured JSON logs with trace correlation)
        from utils.otel_logging import configure_otel_logging
        logger_otel = configure_otel_logging()
        print("[OK] OpenTelemetry logging initialized")
        
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

# NOW import FastMCP and Starlette AFTER OpenTelemetry initialization
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastmcp import FastMCP
from fastmcp.server.auth.auth import AccessToken, TokenVerifier
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from typing import Callable, Awaitable
import asyncio

# Import mock data and helper functions
from mock_data import (
    MOCK_CHEFS,
    MOCK_SERVICES,
    MOCK_AVAILABILITY,
    get_next_order_id,
    parse_date,
    is_date_available,
    get_next_available_date,
)


# ============================================================================
# Auth & Middleware (copied from farmer_tools pattern)
# ============================================================================

class DeferDeleteMiddleware:
    """ASGI middleware that intercepts DELETE /mcp and responds 200 immediately.

    This is a pragmatic workaround for clients that may prematurely close MCP
    sessions. By short-circuiting DELETE, we keep FastMCP's in-memory session
    alive so follow-up POSTs within a short window can still succeed.
    """

    def __init__(self, app: Callable[..., Awaitable], target_path: str = "/mcp"):
        self.app = app
        self._target_path = target_path.rstrip("/")
        try:
            self._defer_seconds = int(os.getenv("MCP_DEFER_DELETE_SECONDS", "60"))
        except ValueError:
            self._defer_seconds = 60

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and self._defer_seconds > 0:
            path = (scope.get("path") or "").rstrip("/")
            method = scope.get("method") or ""
            if method.upper() == "DELETE" and path == self._target_path:
                print(
                    f"MCP DELETE intercepted at {scope.get('path')}; deferring close for {self._defer_seconds}s"
                )
                orig_headers = scope.get("headers") or []
                scheme = scope.get("scheme", "http")
                server = scope.get("server")
                client = scope.get("client")
                http_version = scope.get("http_version", "1.1")
                body_chunks: list[bytes] = []
                more = True
                try:
                    while more:
                        msg = await receive()
                        if msg.get("type") != "http.request":
                            break
                        data = msg.get("body") or b""
                        if data:
                            body_chunks.append(data)
                        more = msg.get("more_body", False)
                except Exception:
                    body_chunks = []
                buffered_body = b"".join(body_chunks)

                async def _drain_send(_message):
                    return

                async def _body_receive():
                    nonlocal buffered_body
                    b = buffered_body
                    buffered_body = b""
                    return {"type": "http.request", "body": b, "more_body": False}

                async def _delayed_invoke():
                    try:
                        await asyncio.sleep(self._defer_seconds)
                        delayed_scope = {
                            "type": "http",
                            "asgi": {"version": "3.0"},
                            "http_version": http_version,
                            "method": "DELETE",
                            "scheme": scheme,
                            "path": self._target_path,
                            "raw_path": self._target_path.encode("utf-8"),
                            "query_string": b"",
                            "headers": orig_headers,
                            "server": server,
                            "client": client,
                        }
                        await self.app(delayed_scope, _body_receive, _drain_send)
                    except Exception as ex:
                        print(f"Deferred MCP DELETE failed: {ex}")

                asyncio.create_task(_delayed_invoke())
                headers = [(b"content-type", b"text/plain; charset=utf-8")]
                await send({"type": "http.response.start", "status": 200, "headers": headers})
                await send({"type": "http.response.body", "body": b"OK"})
                return
        await self.app(scope, receive, send)


class EnvAPIKeyVerifier(TokenVerifier):
    """Very simple static bearer token verifier based on environment variable.

    This is suitable for basic protection only. For production-grade auth,
    prefer JWT verification or OAuth (see FastMCP auth docs).
    """

    def __init__(self, required_token: str):
        super().__init__(base_url=None)
        self._token = required_token

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """Validate a static bearer token from env and return an access token."""
        if token and token == self._token:
            return AccessToken(
                token=token,
                client_id="api-key-user",
                scopes=["*"],
            )
        return None


def _get_cors_origins(raw: str | None) -> list[str] | str:
    if not raw or raw.strip() == "*":
        return "*"
    return [o.strip() for o in raw.split(",") if o.strip()]


# ============================================================================
# Server & Tools
# ============================================================================

def build_server() -> tuple[FastMCP, object]:
    """Create FastMCP server and ASGI app configured for HTTP, CORS, and auth."""

    api_key = os.getenv("MCP_API_KEY")
    if not api_key:
        print("ERROR: MCP_API_KEY is required for server authentication.", file=sys.stderr)
        sys.exit(2)

    auth = EnvAPIKeyVerifier(api_key)
    mcp = FastMCP("Chef Services", auth=auth)

    # Health check route at "/health"
    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    # ========================================================================
    # MCP Tools
    # ========================================================================

    @mcp.tool()
    def search_chefs(
        specialty: str | None = None,
        event_type: str | None = None,
        max_results: int = 5
    ) -> list[dict]:
        """Search for chefs by specialty or event type.
        
        Finds professional chefs based on their culinary specialties (e.g., Italian, 
        BBQ, Vegan) or event types (e.g., wedding, corporate, private dinner). Returns 
        ranked results with chef details including rates, experience, and certifications.
        
        Args:
            specialty: Optional cuisine specialty to filter by (case-insensitive, 
                      partial match). Examples: "Italian", "vegan", "BBQ"
            event_type: Optional event type for matching (e.g., "wedding", "corporate", 
                       "dinner party"). Will match against specialties and bios.
            max_results: Maximum number of results to return (default: 5, max: 20)
            
        Returns:
            List of chef profiles sorted by relevance, each containing:
            - chef_id: Unique identifier
            - name: Chef's full name
            - specialties: List of cuisine specialties
            - experience_years: Years of professional experience
            - rate_per_hour: Hourly rate in USD
            - bio: Brief professional description
            - certifications: List of certifications and credentials
            - match_score: Relevance score (higher is better)
        
        Examples:
            search_chefs(specialty="Italian")
            search_chefs(event_type="wedding", max_results=3)
            search_chefs(specialty="vegan", event_type="corporate")
        """
        # Validate and cap max_results
        max_results = min(max(1, max_results), 20)
        
        # Start with all chefs
        results = []
        
        # Normalize search terms
        specialty_lower = specialty.lower() if specialty else None
        event_type_lower = event_type.lower() if event_type else None
        
        for chef in MOCK_CHEFS:
            match_score = 0
            reasons = []
            
            # Match specialty (check against each specialty in list)
            if specialty_lower:
                for chef_specialty in chef["specialties"]:
                    if specialty_lower in chef_specialty.lower():
                        match_score += 10
                        reasons.append(f"specialty:{chef_specialty}")
                        break
            
            # Match event type (check specialties and bio)
            if event_type_lower:
                # Check specialties
                for chef_specialty in chef["specialties"]:
                    if event_type_lower in chef_specialty.lower():
                        match_score += 5
                        reasons.append(f"event_type_in_specialty:{chef_specialty}")
                        break
                
                # Check bio for event type keywords
                bio_lower = chef["bio"].lower()
                
                # Event type mapping to keywords (search bio for these terms)
                event_keywords = {
                    "wedding": ["wedding", "elegant", "special", "plated", "fine dining"],
                    "corporate": ["corporate", "business", "professional", "catering"],
                    "dinner": ["dinner", "intimate", "private", "home"],
                    "party": ["party", "casual", "gathering", "entertaining"],
                    "fine dining": ["fine dining", "michelin", "gourmet"],
                }
                
                # Get keywords for this event type
                keywords_to_check = event_keywords.get(event_type_lower, [event_type_lower])
                
                # Check if any keyword appears in bio
                for keyword in keywords_to_check:
                    if keyword in bio_lower:
                        match_score += 3
                        reasons.append(f"event_type_in_bio:{keyword}")
                        break
            
            # If no filters provided, give all chefs a base score
            if not specialty_lower and not event_type_lower:
                match_score = 1
            
            # Only include chefs with some match
            if match_score > 0:
                result = {
                    **chef,  # Include all chef fields
                    "match_score": match_score,
                    "match_reasons": reasons  # For debugging/transparency
                }
                results.append(result)
        
        # Sort by match score (descending), then by experience (descending)
        results.sort(key=lambda x: (x["match_score"], x["experience_years"]), reverse=True)
        
        # Limit results
        results = results[:max_results]
        
        # Remove match_reasons from final output (internal debugging only)
        for result in results:
            result.pop("match_reasons", None)
        
        return results

    # ============================================================================
    # Tool: search_services
    # ============================================================================
    
    @mcp.tool()
    def search_services(
        service_type: str,
        guest_count: int | None = None,
        cuisine: str | None = None,
        max_results: int = 5
    ) -> list[dict]:
        """Search for culinary services (catering, delivery, meal prep, private chef).
        
        Filters services by type, guest count capacity, and optional cuisine preference.
        Returns matching services sorted by relevance and capacity fit.
        
        Args:
            service_type: Required service type. Valid values:
                - "catering": Event catering with setup and service
                - "delivery": Food delivery without service staff
                - "meal_prep": Weekly meal preparation service
                - "private_chef": Private chef for intimate dining
            guest_count: Optional number of guests. Filters by min/max capacity.
            cuisine: Optional cuisine preference (e.g., "Italian", "BBQ", "vegan").
                Matches against service names and descriptions.
            max_results: Maximum number of results to return (default 5, max 20).
        
        Returns:
            List of service dicts with fields:
                - service_id: Unique service identifier
                - type: Service type
                - name: Service name
                - base_price_per_person: Base price per person (USD)
                - min_guests: Minimum guest count
                - max_guests: Maximum guest count
                - includes: List of what's included
                - description: Service description
                - match_score: Relevance score (higher = better match)
        
        Examples:
            >>> search_services(service_type="catering", guest_count=50)
            >>> search_services(service_type="private_chef", guest_count=6)
            >>> search_services(service_type="catering", guest_count=100, cuisine="BBQ")
        """
        # Validate and normalize max_results
        max_results = min(max(1, max_results), 20)
        
        # Validate service_type
        valid_types = ["catering", "delivery", "meal_prep", "private_chef"]
        service_type_lower = service_type.lower()
        if service_type_lower not in valid_types:
            return []  # Invalid service type
        
        results = []
        
        # Normalize cuisine search term if provided
        cuisine_lower = cuisine.lower() if cuisine else None
        
        for service in MOCK_SERVICES:
            # Filter by service type (required)
            if service["type"] != service_type_lower:
                continue
            
            match_score = 10  # Base score for type match
            reasons = [f"type:{service_type_lower}"]
            
            # Filter by guest count capacity
            if guest_count is not None:
                if guest_count < service["min_guests"] or guest_count > service["max_guests"]:
                    continue  # Outside capacity range
                
                # Bonus for optimal capacity fit (middle 50% of range)
                capacity_range = service["max_guests"] - service["min_guests"]
                optimal_min = service["min_guests"] + (capacity_range * 0.25)
                optimal_max = service["min_guests"] + (capacity_range * 0.75)
                
                if optimal_min <= guest_count <= optimal_max:
                    match_score += 5
                    reasons.append(f"optimal_capacity:{guest_count}")
                else:
                    match_score += 2
                    reasons.append(f"within_capacity:{guest_count}")
            
            # Match cuisine preference (check name and description)
            if cuisine_lower:
                cuisine_found = False
                
                # Check service name
                if cuisine_lower in service["name"].lower():
                    match_score += 8
                    reasons.append(f"cuisine_in_name:{cuisine_lower}")
                    cuisine_found = True
                
                # Check service description
                elif cuisine_lower in service["description"].lower():
                    match_score += 5
                    reasons.append(f"cuisine_in_description:{cuisine_lower}")
                    cuisine_found = True
                
                # If cuisine specified but not found, lower the score
                if not cuisine_found:
                    match_score -= 3
            
            # Add to results
            result = {
                **service,  # Include all service fields
                "match_score": match_score,
                "match_reasons": reasons  # For debugging/transparency
            }
            results.append(result)
        
        # Sort by match score (descending), then by price (ascending for value)
        results.sort(key=lambda x: (x["match_score"], -x["base_price_per_person"]), reverse=True)
        
        # Limit results
        results = results[:max_results]
        
        # Remove match_reasons from final output
        for result in results:
            result.pop("match_reasons", None)
        
        return results

    # ============================================================================
    # Tool: check_availability
    # ============================================================================
    
    @mcp.tool()
    def check_availability(
        date: str,
        chef_id: str | None = None,
        service_id: str | None = None,
        duration_hours: int | None = None
    ) -> dict:
        """Check availability of a chef or service for a specific date.
        
        Verifies if a chef is available on the requested date and suggests alternatives
        if unavailable. For services, checks general availability (services are always
        available unless a specific chef is assigned).
        
        Args:
            date: Required date to check in YYYY-MM-DD format (must be future date).
            chef_id: Optional chef identifier (e.g., "chef_001"). If provided, checks
                specific chef's availability.
            service_id: Optional service identifier (e.g., "svc_001"). Used for context
                but services are generally available.
            duration_hours: Optional duration in hours. Not currently used for blocking,
                but included for pricing context.
        
        Returns:
            Dict with availability information:
                - available: Boolean indicating if chef/service is available
                - date: Requested date (YYYY-MM-DD)
                - chef_id: Chef ID if specified, None otherwise
                - chef_name: Chef name if chef_id provided, None otherwise
                - service_id: Service ID if specified, None otherwise
                - service_name: Service name if service_id provided, None otherwise
                - conflicts: List of reasons if unavailable (e.g., ["chef_blocked"])
                - next_available_date: Next available date (YYYY-MM-DD) if blocked,
                    empty string if available or not applicable
                - message: Human-readable status message
        
        Examples:
            >>> check_availability(date="2025-11-15", chef_id="chef_001")
            >>> check_availability(date="2025-12-25", service_id="svc_002")
            >>> check_availability(date="2025-11-20", chef_id="chef_003", duration_hours=4)
        
        Raises:
            Returns error dict if date is invalid or in the past.
        """
        # Parse and validate date
        parsed_date = parse_date(date)
        if parsed_date is None:
            return {
                "available": False,
                "date": date,
                "chef_id": chef_id,
                "service_id": service_id,
                "conflicts": ["invalid_date_format"],
                "next_available_date": "",
                "message": f"Invalid date format '{date}'. Expected YYYY-MM-DD."
            }
        
        # Check if date is in the future
        today = datetime.now().date()
        if parsed_date <= today:
            return {
                "available": False,
                "date": date,
                "chef_id": chef_id,
                "service_id": service_id,
                "conflicts": ["date_in_past"],
                "next_available_date": (today + timedelta(days=1)).strftime("%Y-%m-%d"),
                "message": f"Date {date} is in the past or today. Please choose a future date."
            }
        
        # Initialize response
        response = {
            "available": True,
            "date": date,
            "chef_id": chef_id,
            "chef_name": None,
            "service_id": service_id,
            "service_name": None,
            "conflicts": [],
            "next_available_date": "",
            "message": ""
        }
        
        # Check chef availability if chef_id provided
        if chef_id:
            # Verify chef exists
            chef = next((c for c in MOCK_CHEFS if c["chef_id"] == chef_id), None)
            if chef is None:
                response["available"] = False
                response["conflicts"].append("chef_not_found")
                response["message"] = f"Chef with ID '{chef_id}' not found."
                return response
            
            response["chef_name"] = chef["name"]
            
            # Check if chef is blocked on this date
            if not is_date_available(chef_id, date):
                response["available"] = False
                response["conflicts"].append("chef_blocked")
                response["next_available_date"] = get_next_available_date(chef_id, parsed_date)
                response["message"] = (
                    f"Chef {chef['name']} is not available on {date}. "
                    f"Next available: {response['next_available_date']}"
                )
                return response
        
        # Check service if service_id provided
        if service_id:
            # Verify service exists
            service = next((s for s in MOCK_SERVICES if s["service_id"] == service_id), None)
            if service is None:
                response["available"] = False
                response["conflicts"].append("service_not_found")
                response["message"] = f"Service with ID '{service_id}' not found."
                return response
            
            response["service_name"] = service["name"]
        
        # Build success message
        if chef_id and service_id:
            response["message"] = (
                f"Chef {response['chef_name']} is available for "
                f"{response['service_name']} on {date}."
            )
        elif chef_id:
            response["message"] = f"Chef {response['chef_name']} is available on {date}."
        elif service_id:
            response["message"] = f"{response['service_name']} is available on {date}."
        else:
            response["message"] = f"Date {date} is available for booking."
        
        if duration_hours:
            response["message"] += f" (Duration: {duration_hours} hours)"
        
        return response

    # ============================================================================
    # Tool: calculate_pricing
    # ============================================================================
    
    # Helper function for pricing calculation (used by both tools)
    def _calculate_price(
        guest_count: int,
        chef_id: str | None,
        service_id: str | None,
        duration_hours: int | None,
        menu_complexity: str | None,
        additional_services: list[str] | None
    ) -> dict:
        """Internal pricing calculation logic."""
        # Validate guest_count
        if guest_count <= 0:
            return {"error": "invalid_guest_count", "message": "guest_count must be a positive number.", "total": 0}
        
        # Validate at least one pricing basis
        if not chef_id and not service_id:
            return {"error": "missing_pricing_basis", "message": "Either chef_id or service_id must be provided.", "total": 0}
        
        # Set default duration if None (but validate if explicitly provided)
        if duration_hours is None:
            duration_hours = 4
        elif duration_hours <= 0:
            return {"error": "invalid_duration", "message": "duration_hours must be positive.", "total": 0}
        
        # Initialize response
        response = {
            "total": 0, "base_cost": 0, "guest_count": guest_count,
            "chef_id": chef_id, "chef_name": None,
            "service_id": service_id, "service_name": None,
            "duration_hours": duration_hours,
            "menu_complexity": menu_complexity or "moderate",
            "complexity_multiplier": 1.0,
            "breakdown": [], "additional_services_cost": 0
        }

        
        # Calculate base cost (service takes precedence)
        if service_id:
            service = next((s for s in MOCK_SERVICES if s["service_id"] == service_id), None)
            if service is None:
                return {"error": "service_not_found", "message": f"Service with ID '{service_id}' not found.", "total": 0}
            
            response["service_name"] = service["name"]
            if guest_count < service["min_guests"] or guest_count > service["max_guests"]:
                return {"error": "guest_count_out_of_range", "message": f"Service '{service['name']}' requires {service['min_guests']}-{service['max_guests']} guests. Requested: {guest_count}.", "total": 0}
            
            base_cost = service["base_price_per_person"] * guest_count
            response["base_cost"] = base_cost
            response["breakdown"].append({"item": f"{service['name']} ({guest_count} guests)", "calculation": f"${service['base_price_per_person']}/person × {guest_count} guests", "amount": base_cost})
        
        elif chef_id:
            chef = next((c for c in MOCK_CHEFS if c["chef_id"] == chef_id), None)
            if chef is None:
                return {"error": "chef_not_found", "message": f"Chef with ID '{chef_id}' not found.", "total": 0}
            
            response["chef_name"] = chef["name"]
            base_cost = chef["rate_per_hour"] * response["duration_hours"]
            response["base_cost"] = base_cost
            response["breakdown"].append({"item": f"Chef {chef['name']} ({response['duration_hours']} hours)", "calculation": f"${chef['rate_per_hour']}/hour × {response['duration_hours']} hours", "amount": base_cost})
        
        # Apply complexity
        complexity_map = {"simple": 1.0, "moderate": 1.3, "complex": 1.6}
        complexity_level = response["menu_complexity"].lower()
        if complexity_level not in complexity_map:
            complexity_level = "moderate"
            response["menu_complexity"] = "moderate"
        
        response["complexity_multiplier"] = complexity_map[complexity_level]
        if response["complexity_multiplier"] != 1.0:
            complexity_adjustment = response["base_cost"] * (response["complexity_multiplier"] - 1.0)
            response["breakdown"].append({"item": f"Menu complexity adjustment ({response['menu_complexity']})", "calculation": f"Base × {response['complexity_multiplier']}", "amount": complexity_adjustment})
        
        subtotal = response["base_cost"] * response["complexity_multiplier"]
        
        # Add additional services
        additional_cost = 0
        if additional_services:
            service_prices = {"wine_pairing": 15, "specialty_dessert": 12, "premium_ingredients": 20, "staff_service": 25, "equipment_rental": 100}
            for addon in additional_services:
                addon_lower = addon.lower().replace(" ", "_")
                if addon_lower in service_prices:
                    price = service_prices[addon_lower]
                    if addon_lower == "equipment_rental":
                        additional_cost += price
                        response["breakdown"].append({"item": f"Additional: {addon}", "calculation": "Flat fee", "amount": price})
                    else:
                        addon_cost = price * guest_count
                        additional_cost += addon_cost
                        response["breakdown"].append({"item": f"Additional: {addon}", "calculation": f"${price}/person × {guest_count} guests", "amount": addon_cost})
        
        response["additional_services_cost"] = additional_cost
        response["total"] = round(subtotal + additional_cost, 2)
        return response
    
    @mcp.tool()
    def calculate_pricing(
        guest_count: int,
        chef_id: str | None = None,
        service_id: str | None = None,
        duration_hours: int | None = None,
        menu_complexity: str | None = None,
        additional_services: list[str] | None = None
    ) -> dict:
        """Calculate pricing for chef services or catering packages.
        
        Calculates total cost based on chef hourly rates OR service per-person pricing,
        with adjustments for menu complexity and additional services. Returns detailed
        breakdown of all cost components.
        
        Args:
            guest_count: Required number of guests (must be positive).
            chef_id: Optional chef identifier (e.g., "chef_001"). If provided, uses
                chef's hourly rate × duration_hours.
            service_id: Optional service identifier (e.g., "svc_001"). If provided,
                uses service's per-person rate × guest_count.
            duration_hours: Optional duration in hours. Required if chef_id provided,
                optional for services (default: 4 hours if not specified).
            menu_complexity: Optional complexity level affecting pricing:
                - "simple": 1.0x multiplier (no change)
                - "moderate": 1.3x multiplier (+30%)
                - "complex": 1.6x multiplier (+60%)
                Default: "moderate" if not specified.
            additional_services: Optional list of additional services, each adds cost:
                - "wine_pairing": +$15 per person
                - "specialty_dessert": +$12 per person
                - "premium_ingredients": +$20 per person
                - "staff_service": +$25 per person
                - "equipment_rental": +$100 flat fee
        
        Returns:
            Dict with pricing breakdown:
                - total: Total cost (USD)
                - base_cost: Base cost before adjustments
                - guest_count: Number of guests
                - chef_id: Chef ID if provided
                - chef_name: Chef name if chef_id provided
                - service_id: Service ID if provided
                - service_name: Service name if service_id provided
                - duration_hours: Duration used in calculation
                - menu_complexity: Complexity level applied
                - complexity_multiplier: Multiplier value (1.0, 1.3, or 1.6)
                - breakdown: List of cost components with descriptions
                - additional_services_cost: Total cost of additional services
        
        Examples:
            >>> calculate_pricing(guest_count=20, chef_id="chef_001", duration_hours=4)
            >>> calculate_pricing(guest_count=50, service_id="svc_002", menu_complexity="complex")
            >>> calculate_pricing(guest_count=10, service_id="svc_003", 
            ...                   additional_services=["wine_pairing", "specialty_dessert"])
        
        Raises:
            Returns error dict if guest_count invalid, chef/service not found, or
            duration_hours missing when chef_id provided.
        """
        # Delegate to helper function
        return _calculate_price(
            guest_count=guest_count,
            chef_id=chef_id,
            service_id=service_id,
            duration_hours=duration_hours,
            menu_complexity=menu_complexity,
            additional_services=additional_services
        )


    @mcp.tool()
    def place_order(
        date: str,
        guest_count: int,
        contact_info: dict,
        chef_id: str | None = None,
        service_id: str | None = None,
        duration_hours: int | None = None,
        menu_notes: str | None = None,
        menu_complexity: str = "moderate",
        additional_services: list[str] | None = None
    ) -> dict:
        """
        Place an order for chef services or catering.
        
        This tool validates availability, calculates final pricing, generates an order ID,
        blocks the date, and returns a confirmation with complete order details.
        
        Args:
            date: Event date (YYYY-MM-DD format, must be future date).
            guest_count: Number of guests (must be positive).
            contact_info: Customer contact information (dict with keys: name, email, phone).
            chef_id: Optional chef identifier (e.g., "chef_001"). Either chef_id or 
                service_id must be provided.
            service_id: Optional service identifier (e.g., "svc_001"). Takes precedence
                over chef_id if both provided.
            duration_hours: Optional duration in hours (defaults to 4). Required for 
                chef-based orders.
            menu_notes: Optional special requests or dietary restrictions.
            menu_complexity: Menu complexity level (simple, moderate, complex). 
                Defaults to "moderate".
            additional_services: Optional list of additional services to include
                (wine_pairing, specialty_dessert, premium_ingredients, staff_service, 
                equipment_rental).
        
        Returns:
            dict: Order confirmation with structure:
                {
                    "order_id": str,
                    "status": "confirmed",
                    "date": str,
                    "guest_count": int,
                    "chef_id": str | None,
                    "chef_name": str | None,
                    "service_id": str | None,
                    "service_name": str | None,
                    "total_cost": float,
                    "breakdown": list[dict],
                    "contact": dict,
                    "menu_notes": str | None,
                    "created_at": str (ISO timestamp)
                }
            
            On error, returns dict with "error", "message", and "order_id": None.
        
        Examples:
            >>> place_order(
            ...     date="2025-12-25",
            ...     guest_count=30,
            ...     chef_id="chef_002",
            ...     duration_hours=5,
            ...     contact_info={"name": "John Doe", "email": "john@example.com", "phone": "555-1234"}
            ... )
            >>> place_order(
            ...     date="2026-01-15",
            ...     guest_count=100,
            ...     service_id="svc_002",
            ...     menu_complexity="complex",
            ...     additional_services=["wine_pairing", "equipment_rental"],
            ...     contact_info={"name": "Jane Smith", "email": "jane@example.com", "phone": "555-5678"}
            ... )
        """
        # Initialize response structure
        response = {
            "order_id": None,
            "status": "error",
            "date": date,
            "guest_count": guest_count,
            "chef_id": chef_id,
            "chef_name": None,
            "service_id": service_id,
            "service_name": None,
            "total_cost": 0.0,
            "breakdown": [],
            "contact": contact_info,
            "menu_notes": menu_notes,
            "created_at": None
        }
        
        # Validate contact info
        if not contact_info or not isinstance(contact_info, dict):
            response["error"] = "invalid_contact_info"
            response["message"] = "contact_info must be a dict with name, email, and phone"
            return response
        
        required_fields = ["name", "email", "phone"]
        missing = [f for f in required_fields if f not in contact_info or not contact_info[f]]
        if missing:
            response["error"] = "missing_contact_fields"
            response["message"] = f"contact_info missing required fields: {', '.join(missing)}"
            return response
        
        # Validate that either chef_id or service_id is provided
        if not chef_id and not service_id:
            response["error"] = "missing_booking_basis"
            response["message"] = "Either chef_id or service_id must be provided"
            return response
        
        # Validate guest count
        if guest_count <= 0:
            response["error"] = "invalid_guest_count"
            response["message"] = "guest_count must be positive"
            return response
        
        # Validate date format and ensure it's in the future
        try:
            event_date = datetime.fromisoformat(date)
        except (ValueError, TypeError):
            response["error"] = "invalid_date_format"
            response["message"] = "date must be in YYYY-MM-DD format"
            return response
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if event_date.date() <= today.date():
            response["error"] = "past_date"
            response["message"] = f"Cannot book for past or today. Date must be after {today.date()}"
            return response
        
        # Check availability (reuse check_availability logic)
        target_chef_id = None
        if service_id:
            # Find service and get recommended chef
            service = next((s for s in MOCK_SERVICES if s["service_id"] == service_id), None)
            if not service:
                response["error"] = "service_not_found"
                response["message"] = f"Service {service_id} not found"
                return response
            
            response["service_name"] = service["name"]
            
            # Validate guest count against service capacity
            if guest_count < service["min_guests"] or guest_count > service["max_guests"]:
                response["error"] = "guest_count_out_of_range"
                response["message"] = f"Service requires {service['min_guests']}-{service['max_guests']} guests"
                return response
        
        if chef_id:
            # Validate chef exists
            chef = next((c for c in MOCK_CHEFS if c["chef_id"] == chef_id), None)
            if not chef:
                response["error"] = "chef_not_found"
                response["message"] = f"Chef {chef_id} not found"
                return response
            
            response["chef_name"] = chef["name"]
            target_chef_id = chef_id
        
        # Check if date is blocked
        if target_chef_id and date in MOCK_AVAILABILITY.get(target_chef_id, []):
            response["error"] = "date_unavailable"
            response["message"] = f"Chef {target_chef_id} is not available on {date}"
            
            # Suggest next available date
            blocked_dates = MOCK_AVAILABILITY.get(target_chef_id, [])
            blocked_set = {datetime.fromisoformat(d).date() for d in blocked_dates}
            search_date = event_date.date() + timedelta(days=1)
            for _ in range(90):
                if search_date not in blocked_set:
                    response["next_available_date"] = search_date.isoformat()
                    break
                search_date += timedelta(days=1)
            
            return response
        
        # Calculate pricing using helper function
        pricing = _calculate_price(
            guest_count=guest_count,
            chef_id=chef_id,
            service_id=service_id,
            duration_hours=duration_hours,
            menu_complexity=menu_complexity,
            additional_services=additional_services
        )
        
        # Check if pricing calculation failed
        if "error" in pricing:
            response["error"] = pricing["error"]
            response["message"] = pricing["message"]
            return response
        
        # Generate order ID using helper function
        order_id = get_next_order_id(event_date)
        
        # Block the date for the chef
        if target_chef_id:
            if target_chef_id not in MOCK_AVAILABILITY:
                MOCK_AVAILABILITY[target_chef_id] = []
            MOCK_AVAILABILITY[target_chef_id].append(date)
        
        # Build successful response
        response.update({
            "order_id": order_id,
            "status": "confirmed",
            "chef_name": pricing.get("chef_name"),
            "service_name": pricing.get("service_name"),
            "total_cost": pricing["total"],
            "breakdown": pricing["breakdown"],
            "created_at": datetime.now().isoformat()
        })
        
        return response

    # Build ASGI app and attach CORS
    app = mcp.http_app()
    
    # Instrument Starlette with OpenTelemetry (FastMCP uses Starlette)
    # Note: instrument_app modifies in-place and returns the app (don't reassign to None)
    if otel_enabled:
        try:
            from opentelemetry.instrumentation.starlette import StarletteInstrumentor
            StarletteInstrumentor.instrument_app(app)
            print("[OK] Starlette instrumented with OpenTelemetry")
        except Exception as e:
            print(f"[WARNING] Starlette instrumentation failed: {e}")
    
    # Add CORS middleware using Starlette's add_middleware (before ASGI wrapping)
    allow_origins = _get_cors_origins(os.getenv("MCP_CORS_ORIGINS", "*"))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins if isinstance(allow_origins, list) else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    
    # Add business dimensions middleware (ASGI-style wrapper)
    if otel_enabled:
        from starlette.middleware.base import BaseHTTPMiddleware
        
        class BusinessDimensionsMiddleware(BaseHTTPMiddleware):
            """Add business context attributes to OpenTelemetry spans."""
            
            async def dispatch(self, request: Request, call_next):
                from opentelemetry import trace as otel_trace
                from opentelemetry import context as otel_context
                
                span = otel_trace.get_current_span()
                if span and span.is_recording():
                    # Set static agent_type dimension
                    agent_type = "mcp-chef-services"
                    span.set_attribute("agent_type", agent_type)
                    
                    # Set experiment dimension
                    experiment = os.getenv("OTEL_EXPERIMENT", "production")
                    span.set_attribute("experiment", experiment)
                    
                    # MCP servers are backend services - user context propagated from parent
                    user_id = "backend-service"
                    is_vip = False
                    
                    span.set_attribute("user_id", user_id)
                    span.set_attribute("is_vip", is_vip)
                    
                    # Propagate custom dimensions via context
                    ctx = otel_context.get_current()
                    ctx = otel_context.set_value("user_id", user_id, ctx)
                    ctx = otel_context.set_value("is_vip", is_vip, ctx)
                    ctx = otel_context.set_value("agent_type", agent_type, ctx)
                    ctx = otel_context.set_value("experiment", experiment, ctx)
                    
                    token_ctx = otel_context.attach(ctx)
                    try:
                        response = await call_next(request)
                        return response
                    finally:
                        otel_context.detach(token_ctx)
                else:
                    response = await call_next(request)
                    return response
        
        app.add_middleware(BusinessDimensionsMiddleware)
        print("[OK] Business dimensions middleware added")
    
    # Wrap with DeferDeleteMiddleware (ASGI-style, must be last)
    app = DeferDeleteMiddleware(app, target_path="/mcp")
    return mcp, app


def main() -> None:
    """Run the server in HTTP transport with configured host/port."""
    load_dotenv()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8013"))
    mcp, _ = build_server()
    print(f"Starting Chef Services MCP Server on {host}:{port}")
    print(f"Health endpoint: http://{host}:{port}/health")
    print(f"MCP endpoint: http://{host}:{port}/mcp/")
    mcp.run(transport="http", host=host, port=port)


# ASGI application entrypoint for uvicorn/gunicorn
load_dotenv()
_mcp, app = build_server()

if __name__ == "__main__":
    main()

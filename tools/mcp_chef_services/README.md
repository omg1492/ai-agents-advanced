# MCP Chef Services (FastMCP)

A specialized MCP server providing chef and catering service tools using FastMCP 2.0. This server enables AI agents to search for chefs, check availability, calculate pricing, and place orders for culinary services.

## Features

- **5 Specialized Tools**: Comprehensive chef and catering service operations
- **Mock Data Layer**: 10 chefs, 8 catering services with deterministic IDs
- **HTTP Transport**: Streamable MCP endpoint at `/mcp/`
- **Authentication**: Simple Bearer token auth via `MCP_API_KEY`
- **CORS Support**: Configurable cross-origin access (wildcard by default)
- **Date Blocking**: Session-based availability management for order placement
- **Detailed Pricing**: Cost breakdowns with complexity multipliers and add-ons
- **Comprehensive Testing**: 79 passing unit tests across all tools

## Tools Catalog

### 1. search_chefs
Find professional chefs based on specialty or event type.

**Parameters:**
- `specialty` (optional string): Cuisine type (e.g., "Italian", "BBQ", "Vegan")
- `event_type` (optional string): Event keyword (e.g., "wedding", "corporate", "private")
- `max_results` (optional int, default 5): Maximum results to return (capped at 20)

**Returns:** List of chefs with `chef_id`, `name`, `specialties`, `experience_years`, `rate_per_hour`, `bio`, `certifications`

**Example:**
```json
{
  "specialty": "Italian",
  "max_results": 3
}
```

### 2. search_services
Search for catering and culinary services by type, guest count, or cuisine.

**Parameters:**
- `service_type` (required string): One of `catering`, `delivery`, `meal_prep`, `private_chef`
- `guest_count` (optional int): Number of guests (filters by service capacity)
- `cuisine` (optional string): Cuisine preference (matches in name/description)
- `max_results` (optional int, default 5): Maximum results to return (capped at 50)

**Returns:** List of services with `service_id`, `type`, `name`, `base_price_per_person`, `min_guests`, `max_guests`, `includes`, `description`

**Example:**
```json
{
  "service_type": "catering",
  "guest_count": 50,
  "cuisine": "Mediterranean"
}
```

### 3. check_availability
Check if a chef or service is available on a specific date.

**Parameters:**
- `date` (required string): Date in YYYY-MM-DD format (must be future date)
- `chef_id` (optional string): Chef identifier (e.g., "chef_001")
- `service_id` (optional string): Service identifier (e.g., "svc_001")
- `duration_hours` (optional int): Duration for the event

**Returns:** Availability status, conflicts array, and `next_available_date` if blocked

**Example:**
```json
{
  "date": "2025-12-25",
  "chef_id": "chef_001"
}
```

### 4. calculate_pricing
Calculate detailed pricing for chef services or catering packages.

**Parameters:**
- `guest_count` (required int): Number of guests (must be positive)
- `chef_id` (optional string): Chef identifier for hourly-based pricing
- `service_id` (optional string): Service identifier for per-person pricing
- `duration_hours` (optional int, default 4): Hours of service (required for chefs)
- `menu_complexity` (optional string): One of `simple` (1.0x), `moderate` (1.3x), `complex` (1.6x)
- `additional_services` (optional list[string]): Add-ons like `wine_pairing`, `specialty_dessert`, `premium_ingredients`, `staff_service`, `equipment_rental`

**Returns:** Total cost with detailed breakdown, complexity multiplier, and itemized calculations

**Example:**
```json
{
  "guest_count": 20,
  "chef_id": "chef_001",
  "duration_hours": 4,
  "menu_complexity": "moderate",
  "additional_services": ["wine_pairing", "specialty_dessert"]
}
```

### 5. place_order
Place an order for chef services or catering (blocks the date).

**Parameters:**
- `date` (required string): Event date in YYYY-MM-DD format
- `guest_count` (required int): Number of guests
- `contact_info` (required object): Must include `name`, `email`, `phone`
- `chef_id` (optional string): Book a specific chef
- `service_id` (optional string): Book a catering service
- `duration_hours` (optional int): Event duration
- `menu_notes` (optional string): Special menu requests or dietary restrictions
- `additional_services` (optional list[string]): Add-on services

**Returns:** Order confirmation with `order_id` (format: `ORD_YYYYMMDD_NNN`), status, pricing breakdown, timestamps

**Example:**
```json
{
  "date": "2025-12-31",
  "guest_count": 30,
  "chef_id": "chef_001",
  "duration_hours": 5,
  "menu_notes": "2 vegetarian guests, 1 gluten-free",
  "contact_info": {
    "name": "John Smith",
    "email": "john@example.com",
    "phone": "+1-555-0123"
  },
  "additional_services": ["wine_pairing"]
}
```

**Note:** Successfully placing an order blocks the date in `MOCK_AVAILABILITY` for the session.

## Local Setup

### Prerequisites
- Python 3.12+
- `uv` package manager installed

### Installation

1. **Copy environment template:**
```bash
cp .env.template .env
```

2. **Set MCP API key in `.env`:**
```bash
MCP_API_KEY=your-secure-api-key-here
```

3. **Install dependencies:**
```bash
uv sync
```

4. **Run the server:**
```bash
uv run python main.py
```

The server starts at `http://localhost:8013`:
- **MCP Endpoint**: `http://localhost:8013/mcp/`
- **Health Check**: `http://localhost:8013/health`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8013` | Server port |
| `MCP_API_KEY` | *(required)* | Bearer token for authentication |
| `MCP_CORS_ORIGINS` | `*` | CORS allowed origins (comma-separated or `*`) |

## Mock Data Description

### Chefs (10 total)
Deterministic chef data with varied cuisines and experience levels:
- **chef_001**: Alessandro Rossi (Italian, $120/hr, 15 years)
- **chef_002**: Marcus Johnson (BBQ, $100/hr, 12 years)
- **chef_003**: Yuki Tanaka (Japanese/Sushi, $150/hr, 18 years)
- **chef_004**: Marie Dubois (French/Pastry, $130/hr, 14 years)
- **chef_005**: Carlos Rodriguez (Mexican, $95/hr, 10 years)
- **chef_006**: Priya Sharma (Indian/Vegan, $105/hr, 11 years)
- **chef_007**: Thomas Weber (German/Fine Dining, $140/hr, 16 years)
- **chef_008**: Sophia Chen (Chinese/Dim Sum, $110/hr, 13 years)
- **chef_009**: Emma Thompson (British/Farm-to-Table, $90/hr, 9 years)
- **chef_010**: Ahmed Al-Mansour (Middle Eastern, $115/hr, 17 years)

Each chef includes specialties, bio, certifications, and dynamically generated availability (blocked dates within next 60 days).

### Services (8 total)
Four types of culinary services:
- **Catering**: Wedding Catering, Corporate Event Catering
- **Private Chef**: Private Chef Experience, Chef's Table
- **Delivery**: Gourmet Meal Delivery, Family Meal Plan
- **Meal Prep**: Weekly Meal Prep Service, Performance Meal Prep

Each service defines `base_price_per_person`, capacity range (`min_guests`/`max_guests`), and included items.

### Availability
Chef availability is dynamically generated on server startup:
- Each chef has 3-5 blocked dates within the next 60 days
- Dates chosen deterministically based on chef_id for consistency
- `place_order` updates availability in-memory (session-level)
- Date format: YYYY-MM-DD

### Order IDs
Sequential order IDs with format: `ORD_YYYYMMDD_NNN`
- Example: `ORD_20251231_001`, `ORD_20251231_002`
- Counter persists per session (resets on server restart)

## Docker Usage

### Build and Run Locally

```bash
# Build image
docker build -t mcp-chef-services:local .

# Run container
docker run --rm -it \
  -e MCP_API_KEY=dev-secret-key \
  -p 8013:8013 \
  mcp-chef-services:local
```

### GitHub Actions
The workflow `.github/workflows/build-mcp-chef-services.yml` automatically builds and publishes to GitHub Container Registry on push to `tools/mcp_chef_services/**`.

Image: `ghcr.io/<owner>/<repo>/mcp-chef-services:latest`

## Testing

### Run All Tests
```bash
uv run pytest tests/ -v
```

**Expected:** 79 tests passing
- `test_search_chefs.py`: 10 tests
- `test_search_services.py`: 17 tests
- `test_check_availability.py`: 15 tests
- `test_calculate_pricing.py`: 20 tests
- `test_place_order.py`: 17 tests

### Run Specific Test File
```bash
uv run pytest tests/test_place_order.py -v
```

### Test Coverage
Tests validate:
- Tool registration and schema
- Happy path scenarios
- Validation errors (missing params, invalid formats)
- Availability checking and date blocking
- Pricing calculations with complexity multipliers
- Service capacity constraints
- Order placement workflow

## Using with AI Agents

### OpenAI Responses API
Configure the MCP server as a tool provider:

```python
{
  "type": "mcp",
  "servers": {
    "chef-services": {
      "url": "https://your-chef-services.example.com/mcp",
      "headers": {
        "Authorization": "Bearer your-api-key"
      }
    }
  }
}
```

### GitHub Copilot
Add to your MCP configuration:

```json
{
  "chef-services": {
    "url": "https://chef-services.example.com/mcp",
    "type": "http",
    "headers": {
      "Authorization": "Bearer your-api-key"
    }
  }
}
```

## Integration Examples

### Example 1: Find and Book a Chef
```
User: "I need an Italian chef for 20 people on December 25th"

Agent workflow:
1. search_chefs(specialty="Italian", max_results=3)
2. check_availability(date="2025-12-25", chef_id="chef_001")
3. calculate_pricing(chef_id="chef_001", guest_count=20, duration_hours=4)
4. place_order(chef_id="chef_001", date="2025-12-25", guest_count=20, contact_info={...})
```

### Example 2: Compare Catering Options
```
User: "Show me catering services for 50 people with Mediterranean food"

Agent workflow:
1. search_services(service_type="catering", guest_count=50, cuisine="Mediterranean")
2. calculate_pricing(service_id="svc_001", guest_count=50, menu_complexity="moderate")
3. calculate_pricing(service_id="svc_002", guest_count=50, menu_complexity="moderate")
```

## Architecture

### Code Structure
```
tools/mcp_chef_services/
├── main.py                 # FastMCP server, auth, middleware, 5 tools
├── mock_data.py            # Mock chefs, services, availability, helpers
├── pyproject.toml          # Dependencies (fastmcp, python-dotenv, starlette)
├── .env.template           # Environment variable template
├── .python-version         # Python 3.12
├── Dockerfile              # Container build
├── README.md               # This file
└── tests/
    ├── test_search_chefs.py
    ├── test_search_services.py
    ├── test_check_availability.py
    ├── test_calculate_pricing.py
    └── test_place_order.py
```

### Key Design Decisions
- **Stateless Tools**: Each tool call is independent (except date blocking in session)
- **Deterministic IDs**: Same chef names always map to same IDs for consistency
- **Session-based Blocking**: Order placement blocks dates in-memory (no persistence)
- **Helper Function Pattern**: Shared pricing logic between tools via `_calculate_price()`
- **Comprehensive Validation**: Date format, capacity, availability checked at every step

## Development Notes

### Adding New Tools
1. Add tool function in `main.py` with `@mcp.tool()` decorator
2. Include comprehensive docstring (FastMCP uses for schema generation)
3. Implement validation and error handling
4. Return structured dict or primitive types
5. Create test file in `tests/` with FastMCP Client pattern
6. Update this README's Tools Catalog section

### Extending Mock Data
Edit `mock_data.py`:
- Add chefs to `MOCK_CHEFS` list (use sequential `chef_NNN` IDs)
- Add services to `MOCK_SERVICES` list (use sequential `svc_NNN` IDs)
- Availability is auto-generated on import

### Testing Guidelines
- Use `pytest` with `pytest-asyncio`
- Import `_mcp` from `main.py` (pre-configured FastMCP instance)
- Use FastMCP `Client` for tool invocation
- Mock external dependencies (none currently)
- Test happy paths AND error conditions

## Common Issues

### Tool Not Found
**Symptom:** MCP client reports tool not available  
**Solution:** Verify tool is decorated with `@mcp.tool()` and server restarted

### Authorization Failed
**Symptom:** 401/403 responses  
**Solution:** Check `Authorization: Bearer <token>` header matches `MCP_API_KEY`

### Date Already Blocked
**Symptom:** `place_order` returns date unavailable error  
**Solution:** Order was already placed this session; restart server to reset or choose different date

### Tests Failing
**Symptom:** Import errors or tool not registered  
**Solution:** Run `uv sync` to ensure dependencies installed; check `pytest.ini` configuration

## Future Enhancements (Out of Scope)

- Persistent storage (database for orders and availability)
- Real-time chef availability calendars
- Payment processing integration
- Multi-day event booking
- Chef ratings and reviews
- Dietary restriction filtering
- Geographic location filtering
- Price negotiation workflows

## License

See repository root for license information.

## Support

For issues or questions about this MCP server, refer to:
- Main repository documentation: `docs/`
- Lesson plan: `lessons/L08_multi_agent/plan.md`
- Implementation log: `docs/ImplementationLog.md`

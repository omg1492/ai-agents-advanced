# MCP Chef Services (FastMCP)

MCP server for chef and catering services with mock data. This server exposes tools for searching chefs, services, checking availability, calculating pricing, and placing orders.

## Features

- Single-file server (`main.py`) using FastMCP 2.0
- HTTP transport (streamable) by default; MCP endpoint at `/mcp/`
- Mock data with deterministic IDs for testing
- Tools (to be implemented in Phase 1.3):
  - `search_chefs` - Find chefs by specialty, experience, rate
  - `search_services` - Find catering services by type, capacity, price
  - `check_availability` - Check chef availability for specific dates
  - `calculate_pricing` - Calculate total pricing for service + chef
  - `place_order` - Create mock order with order ID
- Wildcard CORS enabled by default (override via `MCP_CORS_ORIGINS`)
- Simple Bearer token auth using `MCP_API_KEY`
- Runs locally with uv; Dockerfile and GHCR publishing workflow to be added

## Run Locally

**Prerequisites:** Python 3.12+, uv installed.

1. Copy `.env.template` to `.env` and set `MCP_API_KEY`:
   ```bash
   cp .env.template .env
   # Edit .env and set MCP_API_KEY=your-secret-key
   ```

2. Install dependencies and run:
   ```bash
   uv sync
   uv run python main.py
   ```

3. Server starts on `http://localhost:8013`
   - MCP endpoint: `http://localhost:8013/mcp/`
   - Health check: `http://localhost:8013/health`

## Mock Data

The server uses in-memory mock data with **dynamic availability generation**:

### Chefs (10 entries)
- Alessandro Rossi (Italian) - $120/hr
- Marcus Johnson (BBQ) - $100/hr
- Yuki Tanaka (Japanese) - $150/hr
- Marie Dubois (French Pastry) - $130/hr
- Carlos Rodriguez (Mexican) - $95/hr
- Priya Sharma (Indian Vegetarian) - $105/hr
- Thomas Weber (German Fine Dining) - $140/hr
- Sophia Chen (Chinese) - $110/hr
- Emma Thompson (British Farm-to-Table) - $90/hr
- Ahmed Al-Mansour (Middle Eastern) - $115/hr

### Services (8 types)
- Corporate Lunch Catering - $25/person (10-200 guests)
- Wedding Catering Premium - $75/person (50-300 guests)
- Private Dinner Service - $95/person (2-12 guests)
- Weekly Meal Prep - $120/person (1-6 guests)
- Cocktail Party Catering - $45/person (20-150 guests)
- Event Delivery Service - $15/person (10-100 guests)
- Cooking Class Experience - $85/person (4-10 guests)
- BBQ Outdoor Catering - $35/person (25-200 guests)

### Availability (Dynamic)
Chef availability is **automatically generated** on server start:
- Each chef has 3-8 randomly blocked dates
- Covers next 60 days from current date
- Uses deterministic seeding (consistent per server session)
- Dates are in YYYY-MM-DD format

Example: If started on 2025-10-10, availability spans through 2025-12-09.

### Mock Data Structure
All mock data is defined in `mock_data.py`:
- `MOCK_CHEFS`: List of chef profiles with specialties, rates, bios
- `MOCK_SERVICES`: List of service offerings with pricing and capacity
- `MOCK_AVAILABILITY`: Dict of chef_id → list of blocked date strings
- Helper functions: `parse_date()`, `is_date_available()`, `get_next_available_date()`

## Docker

**To be implemented in Phase 1.4**

Build and run locally:
```bash
docker build -t mcp-chef-services:local .
docker run --rm -it -e MCP_API_KEY=dev-secret-key -p 8013:8013 mcp-chef-services:local
```

## Testing with GitHub Copilot

Add this configuration to test the MCP server:

```json
"chef-services": {
  "url": "http://localhost:8013/mcp",
  "type": "http",
  "headers": {
    "Authorization": "Bearer dev-chef-secret"
  }
}
```

For production deployment, use HTTPS URL and secure API key.

## Implementation Status

- ✅ Phase 1.1: Project structure (pyproject.toml, .env, main.py)
- ✅ Phase 1.2: Mock data layer (MOCK_CHEFS, MOCK_SERVICES, MOCK_AVAILABILITY)
- ⏳ Phase 1.3: MCP tools implementation (search_chefs, search_services, etc.)
- ⏳ Phase 1.4: Docker & infrastructure
- ⏳ Phase 1.5: Tests

See `lessons/L08_multi_agent/plan.md` for complete implementation plan.

## Notes

- This server is designed for lesson L08 (Multi-Agent Architecture)
- Mock data uses deterministic IDs (chef_001, svc_001, etc.)
- Order IDs are generated sequentially (resets on restart)
- For production use, replace mock data with real database queries
- Follow repository `AGENTS.md` guidelines for code style and documentation

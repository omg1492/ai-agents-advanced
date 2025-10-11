# Lesson 08: Multi-Agent Architecture - Implementation Plan

## Overview
Implement a multi-agent system where a specialized Chef Agent handles culinary service queries (chefs, catering, availability, pricing) via MCP tools, and integrates with the main DreamFarm Agent using agent-as-tool pattern.

## Implementation Strategy
- **Phase 1**: MCP Chef Services Server (tools + mocks) ✅ Complete
- **Phase 2**: Azure Deployment for Chef Services MCP ✅ Complete
- **Phase 3**: Chef Agent (stateless API using Responses API + remote MCP)
- **Phase 4**: Integration (Chef Agent as tool in DreamFarm Agent)
- **Phase 5**: Documentation & Demo

## Key Architectural Decisions
1. **MCP Server**: Cloud-hosted on Azure Container Apps (not local)
2. **MCP Integration**: Responses API native MCP support (no custom HTTP client)
3. **Agent Language**: Czech system prompt for consistent UX
4. **Configuration**: Unified OpenAI config pattern (matches DreamFarm agent)
5. **Testing**: Separate unit tests (mocked) + integration tests (real Azure MCP)

---

## Phase 1: Chef Services MCP Server

### 1.1 Create Project Structure ✅
- [x] Create directory `tools/mcp_chef_services/`
- [x] Copy template files from `mcp_public_farmer_tools`:
  - [x] `pyproject.toml` (update name to "mcp-chef-services")
  - [x] `.env.template`
  - [x] `.python-version` (3.12)
  - [ ] `Dockerfile`
- [x] Create `main.py` with FastMCP boilerplate
- [x] Create `.env` from template with `MCP_API_KEY=dev-chef-secret`
- [x] Create `README.md` with usage instructions

### 1.2 Implement Mock Data Layer ✅
- [x] Create in-memory mock data structures in `main.py`:
  - [x] `MOCK_CHEFS` - List of 10 chefs with:
    - `chef_id` (deterministic: `chef_001`, `chef_002`, etc.)
    - `name` (realistic names)
    - `specialties` (list: Italian, BBQ, vegan, pastry, etc.)
    - `experience_years` (int)
    - `rate_per_hour` (int, USD)
    - `bio` (short description)
    - `certifications` (list: Michelin-trained, ServSafe, etc.)
  - [x] `MOCK_SERVICES` - List of 8 services with:
    - `service_id` (deterministic: `svc_001`, etc.)
    - `type` (catering, delivery, meal_prep, private_chef)
    - `name` (descriptive name)
    - `base_price_per_person` (int, USD)
    - `min_guests` / `max_guests` (int)
    - `includes` (list of what's included)
    - `description` (text)
  - [x] `MOCK_AVAILABILITY` - Dict mapping `chef_id` to list of blocked dates
  - [x] `_order_counter` - Session-level order ID counter
- [x] Server tested and running on port 8013
- [x] Health endpoint verified at `/health`

### 1.3 Implement MCP Tools

#### Tool: search_chefs ✅
- [x] Define tool with parameters:
  - `specialty` (optional str)
  - `event_type` (optional str)
  - `max_results` (optional int, default 5)
- [x] Implement filtering logic:
  - [x] Filter by specialty (case-insensitive partial match)
  - [x] Filter by event_type (keyword matching in bio + specialties)
  - [x] Sort by match score (relevance + experience)
  - [x] Limit results (capped at 20)
- [x] Return structured JSON with chef details
- [x] Tests: 10 passing tests in `tests/test_search_chefs.py`

#### Tool: search_services ✅
- [x] Define tool with parameters:
  - `service_type` (required: catering, delivery, meal_prep, private_chef)
  - `guest_count` (optional int)
  - `cuisine` (optional str)
  - `max_results` (optional int, default 5)
- [x] Implement filtering logic:
  - [x] Filter by service_type (validated against allowed values)
  - [x] Filter by guest_count capacity (min/max range checking)
  - [x] Filter by cuisine (case-insensitive matching in name/description)
  - [x] Optimal capacity scoring (bonus for middle 50% of range)
  - [x] Sort by match score then price (descending score, ascending price)
- [x] Return structured JSON with service details
- [x] Tests: 17 passing tests in `tests/test_search_services.py`

#### Tool: check_availability ✅
- [x] Define tool with parameters:
  - `date` (required str, YYYY-MM-DD format)
  - `chef_id` (optional str)
  - `service_id` (optional str)
  - `duration_hours` (optional int)
- [x] Implement availability logic:
  - [x] Parse and validate date (must be future, rejects past/today)
  - [x] Check chef blocked dates from MOCK_AVAILABILITY
  - [x] Return availability status + conflicts array
  - [x] Suggest next_available_date if chef blocked
  - [x] Validate chef_id and service_id exist
  - [x] Handle date-only, chef-only, service-only, and combined checks
- [x] Return structured JSON with complete response
- [x] Tests: 15 passing tests in `tests/test_check_availability.py`

#### Tool: calculate_pricing
- [x] Define tool with parameters:
  - `chef_id` (optional str)
  - `service_id` (optional str)
  - `guest_count` (required int)
  - `duration_hours` (optional int)
  - `menu_complexity` (optional: simple, moderate, complex)
  - `additional_services` (optional list[str])
- [x] Implement pricing calculation:
  - [x] Base: chef hourly rate × duration OR service per-person × guest_count
  - [x] Complexity multiplier (1.0, 1.3, 1.6)
  - [x] Additional services surcharges (wine_pairing, specialty_dessert, premium_ingredients, staff_service, equipment_rental)
  - [x] Build detailed breakdown with calculation explanations
  - [x] Service takes precedence when both chef_id and service_id provided
- [x] Return structured JSON with total + breakdown
- [x] Tests: 20 passing tests in `tests/test_calculate_pricing.py`

#### Tool: place_order
- [x] Define tool with parameters:
  - `chef_id` (optional str)
  - `service_id` (optional str)
  - `date` (required str)
  - `guest_count` (required int)
  - `duration_hours` (optional int)
  - `menu_notes` (optional str)
  - `contact_info` (required object with name, email, phone)
- [x] Implement order logic:
  - [x] Validate date availability
  - [x] Generate sequential order ID: `ORD_YYYYMMDD_NNN`
  - [x] Calculate total cost using pricing logic
  - [x] Update mock availability (block the date)
  - [x] Return confirmation with order details
- [x] Return structured JSON
- [x] Tests: 17 passing tests in `tests/test_place_order.py`

**Phase 1.3 Complete: All 5 MCP tools implemented with 79 passing tests!**

### 1.4 Add Server Infrastructure
- [x] Implement auth using `EnvAPIKeyVerifier` (already done)
- [x] Add CORS middleware configuration (already done)
- [ ] Add `/health` endpoint
- [x] Add `DeferDeleteMiddleware` (already done)
- [x] Create ASGI app export for uvicorn (already done)

### 1.5 Write Unit Tests
- [x] Create test files for all 5 tools:
  - [x] `tests/test_search_chefs.py` - 10 tests
  - [x] `tests/test_search_services.py` - 17 tests  
  - [x] `tests/test_check_availability.py` - 15 tests
  - [x] `tests/test_calculate_pricing.py` - 20 tests
  - [x] `tests/test_place_order.py` - 17 tests
- [x] Use FastMCP test client pattern
- [x] Test scenarios:
  - [x] `search_chefs` with various filters
  - [x] `search_services` by type and guest count
  - [x] `check_availability` for available and blocked dates
  - [x] `calculate_pricing` with different configurations
  - [x] `place_order` happy path
  - [x] `place_order` validation errors (past date, unavailable)
  - [ ] Auth: valid token vs invalid token (pending integration tests)
- [x] Run tests: All 79 tests passing!

### 1.6 Create README
- [x] Create `tools/mcp_chef_services/README.md`
- [x] Document:
  - [x] Purpose and features
  - [x] Mock data description (10 chefs, 8 services, dynamic availability)
  - [x] Tool catalog with examples (all 5 tools with parameters and examples)
  - [x] Local setup instructions
  - [x] Docker usage
  - [x] Testing instructions (79 tests, how to run)
  - [x] Integration examples with AI agents
  - [x] Architecture and design decisions
  - [x] Common issues and troubleshooting
  - [x] Development notes for extending

**Phase 1 Complete: Chef Services MCP Server fully implemented with 79 passing tests and comprehensive documentation!**

---

## Phase 2: Azure Deployment for Chef Services MCP

### 2.1 Create Dockerfile ✅
- [x] Copy Dockerfile from `mcp_public_farmer_tools`
- [x] Update base image if needed (using python:3.12-slim)
- [x] Update EXPOSE port to 8013
- [x] Update CMD to run `main.py` (includes mock_data.py)
- [x] Test local build: `docker build -t mcp-chef-services:local .`
- [x] Test local run: `docker run -p 8013:8013 -e MCP_API_KEY=test mcp-chef-services:local`
- [x] Verified health endpoint responds with OK

### 2.2 Add GitHub Actions Workflow ✅
- [x] Create `.github/workflows/build-mcp-chef-services.yml`
- [x] Copy template from `build-mcp-public-farmer-tools.yml`
- [x] Update:
  - [x] Workflow name: "Build and Publish mcp-chef-services"
  - [x] Image name: `ghcr.io/tkubica12/advanced-ai-applications/mcp-chef-services`
  - [x] Build context path: `tools/mcp_chef_services`
  - [x] Trigger paths: `tools/mcp_chef_services/**`
- [x] Push and verify workflow builds image (ready to push)

### 2.3 Create Terraform Configuration ✅
- [x] Create `deploy/azure/mcp_tools/container_app.chef-services.tf`
- [x] Copy template from `container_app.farmer-tools.tf`
- [x] Update:
  - [x] Resource name: `azapi_resource.chef_services`
  - [x] Container App name: `ca-mcp-chef-services`
  - [x] Target port: 8013
  - [x] Secret name: `chef-services-api-key`
  - [x] Environment variables
  - [x] Image reference variable
- [x] Add variables to `variables.tf`:
  - [x] `chef_services_api_key` (sensitive)
  - [x] `chef_services_image` (default: latest from GHCR)
  - [x] `chef_services_min_replicas` (default: 0)
- [x] Add to `secrets.auto.tfvars`:
  - [x] `chef_services_api_key = "your-secure-key"`
- [x] Add to `configs.auto.tfvars`:
  - [x] Image URL
  - [x] Min replicas
- [x] Add output to `outputs.tf`:
  - [x] `chef_services_url` (FQDN)

### 2.4 Deploy to Azure ✅
- [x] Run Terraform:
  ```bash
  cd deploy/azure/mcp_tools
  terraform init
  terraform plan
  terraform apply
  ```
- [x] Verify deployment:
  - [x] Check Container App in Azure Portal
  - [x] Test health endpoint: `https://<fqdn>/health`
  - [x] Test MCP endpoint with Authorization header

### 2.5 Create Integration Tests for Remote MCP ✅
- [x] Create `tests/test_remote_chef_mcp.py`
- [x] Use environment variable `CHEF_SERVICES_MCP_URL`
- [x] Use environment variable `CHEF_SERVICES_MCP_API_KEY`
- [x] Test scenarios:
  - [x] Discovery (list tools)
  - [x] Each tool invocation with remote server (5 tools tested)
  - [x] Auth failure scenarios
- [x] Run: `pytest tests/test_remote_chef_mcp.py -v` (9/9 tests passing)
- [x] Use FastMCP Client pattern (not raw HTTP/JSON-RPC)

---

## Phase 3: Chef Agent Implementation

### 3.1 Create Agent Project Structure ✅
- [x] Create directory `agents/chef-agent/`
- [x] Create `pyproject.toml`:
  - [x] Name: "chef-agent"
  - [x] Dependencies: `fastapi`, `openai`, `python-dotenv`, `pydantic`, `uvicorn`
- [x] Create `.env.template`:
  - [x] Unified OpenAI config: `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` (optional for Azure), `OPENAI_API_VERSION` (optional for Azure)
  - [x] `CORS_ORIGINS` (default: `*`)
  - [x] `LOG_LEVEL` (default: `INFO`)
  - [x] `PORT` (default: `8002`)
  - [x] Chef MCP service config: `CHEF_SERVICES_MCP_URL`, `CHEF_SERVICES_MCP_API_KEY`
- [x] Create `.env` from template
- [x] Create `.python-version` (3.12)
- [x] Run `uv sync`

### 3.2 Implement Agent Core ✅
- [x] Create `src/main.py` (FastAPI app)
- [x] Create `src/models/`:
  - [x] `message.py`: `QueryRequest(message: str)`, `QueryResponse(response: str, response_id: str)`
  - [x] `health.py`: `HealthResponse(status: str)`
- [x] Create `src/services/`:
  - [x] `config_service.py`: Load environment config (similar to dreamfarm-agent pattern)
  - [x] `openai_service.py`: Unified OpenAI client using Responses API (copy pattern from dreamfarm-agent)

### 3.3 Implement Chef Agent Service prompt ✅
- [x] Create system prompt for Chef Agent (English language - per user request):
  ```
  Jsi specialista na gastronomické služby DreamFarm. Pomáháš uživatelům najít správného kucháře,
  objednat cateringové služby, kontrolovat dostupnost a spočítat ceny. Máš přístup k pěti nástrojům:
  
  1. search_chefs - najdi kucháře podle speciality, kuchyně nebo dietetických požadavků
  2. search_services - najdi cateringové a další služby podle typu a požadavků
  3. check_availability - zkontroluj dostupnost kucháře nebo služby k určitému datu
  4. calculate_pricing - vypočítej cenu služby (vždy před objednávkou!)
  5. place_order - potvrď a ulož objednávku (pouze po potvrzení ceny uživatelem)
  
  Proces objednávky:
  1. Zjisti potřeby uživatele (typ služby, počet hostů, datum, speciality)
  2. Použij vhodné nástroje pro vyhledání (search_chefs / search_services)
  3. Zkontroluj dostupnost (check_availability)
  4. Spočítej cenu (calculate_pricing) a prezentuj ji uživateli
  5. Po potvrzení vytvoř objednávku (place_order)
  
  Buď přátelský, profesionální a vždy ověřuj detaily před finalizací.
  ```

### 3.4 Implement MCP Tools Registration ✅
- [x] Create `get_tools()` method in `openai_service.py`:
  - [x] Register Chef Services MCP server using `type: "mcp"` pattern:
    ```python
    {
        "type": "mcp",
        "server_label": "chef_services",
        "server_url": config.chef_services_mcp_url,
        "require_approval": "never",
        "headers": {
            "Authorization": f"Bearer {config.chef_services_mcp_api_key}",
        },
    }
    ```
  - [x] Follow same pattern as Farmer Tools / Tavily in dreamfarm-agent
- [x] No custom HTTP client needed - Responses API handles MCP discovery and execution

### 3.5 Create API Endpoint ✅
- [x] POST `/query`:
  - [x] Request: `{"message": "string"}`
  - [x] Response: `{"response": "string", "response_id": "string"}`
  - [x] Error handling with proper HTTP status codes
- [x] GET `/health`:
  - [x] Return `{"status": "ok"}` with 200
- [x] CORS middleware:
  - [x] Configurable via `CORS_ORIGINS` environment variable
  - [x] Default: `*` (allow all for development)

### 3.6 Write Unit Tests ✅
- [x] Create `tests/test_config_service.py` (9 tests):
  - [x] Test config loading with all variables
  - [x] Test minimal config with defaults
  - [x] Test missing required variables
  - [x] Test validation (invalid log level, port, etc.)
- [x] Create `tests/test_openai_service.py` (6 tests):
  - [x] Mock OpenAI Responses API calls
  - [x] Test service initialization
  - [x] Test tool registration (MCP tools present in request)
  - [x] Test response generation with/without previous_response_id
  - [x] Test multiple content blocks and empty responses
- [x] Create `tests/test_api.py` (9 tests):
  - [x] Test `/query` endpoint with various inputs
  - [x] Test `/health` endpoint
  - [x] Test error handling (missing API key, invalid requests, service errors)
  - [x] Test CORS headers
  - [x] Test long messages and special characters
- [x] Use `pytest` with `httpx.AsyncClient` for API testing
- [x] **Total: 24 unit tests, all passing**

### 3.7 Write Integration Tests ✅
- [x] Create `tests/test_integration_remote_mcp.py` (8 tests):
  - [x] Test against deployed Chef Services MCP (use `CHEF_SERVICES_MCP_URL` from env)
  - [x] Test end-to-end flow: user query → agent → MCP tools → response
  - [x] Test MCP connection and tool discovery
  - [x] Scenarios:
    - [x] Chef search queries
    - [x] Service search queries
    - [x] Availability checking
    - [x] Pricing calculation
    - [x] Multi-turn conversation with state
    - [x] Complex booking workflow
    - [x] Error handling (invalid dates)
- [x] Run with: `uv run pytest tests/test_integration_remote_mcp.py -v`
- [x] **All 8 integration tests passing** (run with `RUN_INTEGRATION_TESTS=1`)

### 3.8 Local Testing ✅
- [x] Start agent: `cd agents/chef-agent && uv run python -m uvicorn src.main:app --port 8002`
- [x] Verify startup logs:
  - [x] Configuration loaded successfully
  - [x] OpenAI service initialized
  - [x] MCP URL registered
  - [x] Server running on port 8002
- [x] Test endpoints:
  - [x] Health check: `curl http://localhost:8002/health`
  - [x] Query: `curl -X POST http://localhost:8002/query -H "Content-Type: application/json" -d '{"message": "Find me an Italian chef"}'`
- [x] Verify:
  - [x] Agent connects to remote Chef Services MCP (Azure)
  - [x] Tools are discovered and registered
  - [x] Responses are coherent and use MCP tools

### 3.9 Create Agent README ✅
- [x] Create `agents/chef-agent/README.md`
- [x] Document:
  - [x] Purpose (specialized culinary services agent using remote Chef Services MCP)
  - [x] Architecture (stateless, Responses API, remote MCP tools)
  - [x] Environment configuration (OpenAI, MCP URL/key, CORS)
  - [x] How to run locally (dev and production modes)
  - [x] How to run tests (unit + integration)
  - [x] API endpoints (`/query`, `/health`) with examples
  - [x] Testing instructions and example queries
  - [x] Troubleshooting section
  - [x] Project structure and development guide

**Phase 3 Complete: Chef Agent fully implemented with 32 tests (24 unit + 8 integration), all passing!**

---

## Phase 4: Integration with DreamFarm Agent

### 4.1 Add Chef Agent Tool to DreamFarm
- [ ] Open `agents/dreamfarm-agent/src/services/chef_agent_client.py` (create)
- [ ] Implement HTTP client for Chef Agent:
  - [ ] `query_chef_agent(message: str) -> str`
  - [ ] POST to `CHEF_AGENT_URL/query`
  - [ ] Return response text
  - [ ] Error handling and timeouts
- [ ] Add to `agents/dreamfarm-agent/.env.template`:
  - [ ] `CHEF_AGENT_ENABLED` (default: false)
  - [ ] `CHEF_AGENT_URL` (default: http://localhost:8002)

### 4.2 Register Chef Agent as Tool
- [ ] Open `agents/dreamfarm-agent/src/main.py` (or tool registration module)
- [ ] Add function tool definition:
  ```python
  {
    "type": "function",
    "function": {
      "name": "query_chef_services",
      "description": """
        Query the specialized chef services agent for culinary assistance 
        including chef recommendations, catering services, availability, 
        and pricing. Use this tool when users ask about:
        - Finding chefs or cooks
        - Catering services for events
        - Private chef services
        - Meal preparation services
        - Availability for specific dates
        - Pricing for culinary services
        
        The agent will handle the complete workflow and return a text response.
      """,
      "parameters": {
        "type": "object",
        "properties": {
          "message": {
            "type": "string",
            "description": "User's query about chef services (pass through verbatim)"
          }
        },
        "required": ["message"]
      }
    }
  }
  ```
- [ ] Implement tool handler that calls `ChefAgentClient.query_chef_agent()`
- [ ] Add feature flag check (`CHEF_AGENT_ENABLED`)

### 4.3 Update DreamFarm System Prompt
- [ ] Open `agents/dreamfarm-agent/src/templates/system.jinja2` (or equivalent)
- [ ] Add section about Chef Agent tool:
  ```
  When users ask about culinary services (chefs, catering, cooking services):
  - Use the query_chef_services tool to delegate to the specialized agent
  - Pass the user's request as-is to the tool
  - The chef agent will handle availability, pricing, and booking workflows
  - Integrate the chef agent's response naturally into your answer
  - You can combine farm product recommendations with chef service suggestions
  ```

### 4.4 Write Integration Tests
- [ ] Create `agents/dreamfarm-agent/tests/test_chef_agent_integration.py`
- [ ] Mock Chef Agent HTTP responses
- [ ] Test scenarios:
  - [ ] User asks about chefs → agent calls tool → returns chef info
  - [ ] User asks about products AND chefs → agent calls both domains
  - [ ] Chef Agent unavailable → graceful fallback
  - [ ] Tool disabled (CHEF_AGENT_ENABLED=false) → skips tool
- [ ] Run: `uv run pytest tests/test_chef_agent_integration.py -v`

### 4.5 End-to-End Testing
- [ ] Start all services:
  1. MCP Chef Services: `cd tools/mcp_chef_services && uv run python main.py`
  2. Chef Agent: `cd agents/chef-agent && uv run uvicorn src.main:app --port 8002`
  3. DreamFarm Agent: `cd agents/dreamfarm-agent && uv run uvicorn src.main:app --reload --port 8001`
  4. Frontend: `cd frontend && npm run dev`
- [ ] Test via UI:
  - [ ] "I need an Italian chef for a wedding with 50 guests"
  - [ ] "Find me farm products and a chef for a dinner party"
  - [ ] "What's available on November 15th?"
  - [ ] "Get me a price quote for catering 30 people"
- [ ] Verify:
  - [ ] DreamFarm agent calls chef agent tool
  - [ ] Chef agent calls MCP tools
  - [ ] Responses are coherent and combined when appropriate
  - [ ] DF_META events show tool usage


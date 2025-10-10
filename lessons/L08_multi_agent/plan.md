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

### 3.5 Create API Endpoint
- [ ] POST `/query`:
  - [ ] Request: `{"message": "string"}`
  - [ ] Response: `{"response": "string", "response_id": "string"}`
  - [ ] Error handling with proper HTTP status codes
- [ ] GET `/health`:
  - [ ] Return `{"status": "ok"}` with 200
- [ ] CORS middleware:
  - [ ] Configurable via `CORS_ORIGINS` environment variable
  - [ ] Default: `*` (allow all for development)

### 3.6 Write Unit Tests
- [ ] Create `tests/test_chef_agent_service.py`:
  - [ ] Mock OpenAI Responses API calls
  - [ ] Test system prompt construction
  - [ ] Test tool registration (MCP tools present in request)
- [ ] Create `tests/test_api.py`:
  - [ ] Test `/query` endpoint with various inputs
  - [ ] Test `/health` endpoint
  - [ ] Test error handling (missing API key, invalid requests)
  - [ ] Test CORS headers
- [ ] Use `pytest` with `httpx.AsyncClient` for API testing
- [ ] Target: >80% coverage

### 3.7 Write Integration Tests
- [ ] Create `tests/test_integration_remote_mcp.py`:
  - [ ] Test against deployed Chef Services MCP (use `CHEF_SERVICES_MCP_URL` from env)
  - [ ] Test end-to-end flow: user query → agent → MCP tools → response
  - [ ] Scenarios:
    - [ ] "Najdi italského kucháře" (search_chefs)
    - [ ] "Kolik stojí catering pro 30 lidí?" (search_services + calculate_pricing)
    - [ ] "Je volný nějaký kuchař 15. ledna?" (check_availability)
  - [ ] Verify MCP tool calls in response metadata (if available)
- [ ] Run with: `uv run pytest tests/test_integration_remote_mcp.py -v`

### 3.8 Local Testing
- [ ] Start agent: `cd agents/chef-agent && uv run uvicorn src.main:app --reload --port 8002`
- [ ] Test with curl:
  ```bash
  curl -X POST http://localhost:8002/query \
    -H "Content-Type: application/json" \
    -d '{"message": "Najdi mi italského kucháře pro svatbu"}'
  ```
- [ ] Verify:
  - [ ] Agent connects to remote Chef Services MCP (Azure)
  - [ ] Tools are called correctly (check logs for MCP discovery and execution)
  - [ ] Response is in Czech and contextually appropriate

### 3.9 Create Agent README
- [ ] Create `agents/chef-agent/README.md`
- [ ] Document:
  - [ ] Purpose (specialized culinary services agent using remote Chef Services MCP)
  - [ ] Architecture (stateless, Responses API, remote MCP tools)
  - [ ] Environment configuration (OpenAI, MCP URL/key, CORS)
  - [ ] How to run locally
  - [ ] How to run tests (unit + integration)
  - [ ] API endpoints (`/query`, `/health`)
  - [ ] Testing instructions and example queries

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

### 4.6 Update Configuration
- [ ] Update `deploy/local/docker-compose.yml`:
  - [ ] Add `chef-mcp-services` service
  - [ ] Add `chef-agent` service
  - [ ] Configure networking
  - [ ] Add environment variables
- [ ] Test Docker Compose deployment:
  ```bash
  cd deploy/local
  docker-compose up --build
  ```

---

## Phase 5: Documentation & Demo

### 5.1 Create Lesson README (Czech)
- [ ] Create `lessons/L08_multi_agent/README.md`
- [ ] Structure:
  - [ ] **Úvod**: Co je multi-agent architektura
  - [ ] **Komponenty**:
    - [ ] MCP Chef Services (nástroje s mock daty)
    - [ ] Chef Agent (specializovaný agent)
    - [ ] Integrace do DreamFarm agenta
  - [ ] **Architektura**:
    - [ ] Diagram toku dat
    - [ ] Agent-as-tool pattern
    - [ ] Bezstavová komunikace
  - [ ] **Technologie**:
    - [ ] FastMCP pro nástroje
    - [ ] FastAPI pro agenty
    - [ ] OpenAI Responses API
  - [ ] **Spuštění**:
    - [ ] Prerekvizity
    - [ ] Lokální setup (3 služby)
    - [ ] Docker Compose
  - [ ] **Demo scénáře**:
    - [ ] Vyhledání kuchaře
    - [ ] Kontrola dostupnosti
    - [ ] Kalkulace ceny
    - [ ] Objednání služby
    - [ ] Kombinace produktů + kuchař
  - [ ] **Klíčové koncepty**:
    - [ ] Separace domén
    - [ ] Škálovatelnost
    - [ ] Testovatelnost
    - [ ] Rozšiřitelnost (další agenti)

### 5.2 Update Main Documentation
- [ ] Update `docs/ImplementationLog.md`:
  - [ ] Add entry for Lesson 08
  - [ ] Describe multi-agent implementation
  - [ ] Key decisions (stateless, agent-as-tool)
- [ ] Verify `docs/Design.md` Section 19 is accurate

### 5.3 Create Demo Script
- [ ] Create `lessons/L08_multi_agent/demo_script.md` (Czech)
- [ ] Include:
  - [ ] Příprava (spuštění služeb)
  - [ ] Demo 1: Základní vyhledání kuchaře
  - [ ] Demo 2: Komplexní plánování události
  - [ ] Demo 3: Kombinace produktů a služeb
  - [ ] Ukázka logů (DF_META, tool calls)
  - [ ] Diskuzní body (škálovatelnost, další agenti)

### 5.4 Add Architecture Diagrams
- [ ] Create `lessons/L08_multi_agent/diagrams/`
- [ ] Diagrams:
  - [ ] `architecture.png`: Celková architektura (User → DreamFarm → Chef Agent → MCP)
  - [ ] `sequence.png`: Sekvence volání (Mermaid exportovat)
  - [ ] `data_flow.png`: Tok dat mezi komponentami

---

## Checklist Summary

### Phase 1: Chef Services MCP ✓
- [ ] Project structure created
- [ ] Mock data implemented (10-15 chefs, 8-10 services)
- [ ] 5 MCP tools implemented (search_chefs, search_services, check_availability, calculate_pricing, place_order)
- [ ] Auth + CORS + health endpoint
- [ ] Unit tests written and passing
- [ ] Local testing verified
- [ ] README created

### Phase 2: Azure Deployment ✅
- [x] Dockerfile created
- [x] GitHub Actions workflow created
- [x] Terraform configuration created
- [x] Deployed to Azure Container Apps
- [x] Remote integration tests passing (9/9 tests with FastMCP Client)

### Phase 3: Chef Agent ✓
- [ ] Agent project created (pyproject.toml, .env.template, structure)
- [ ] Config service implemented (load OpenAI + MCP settings)
- [ ] OpenAI service implemented (Responses API client with MCP tool registration)
- [ ] Chef Agent service with Czech system prompt
- [ ] Stateless API endpoint (/query, /health) with CORS
- [ ] Unit tests written (service + API) - target >80% coverage
- [ ] Integration tests against remote MCP (end-to-end scenarios)
- [ ] Local testing verified (agent → Azure MCP)
- [ ] README created

### Phase 4: DreamFarm Integration ✓
- [ ] Chef Agent HTTP client created
- [ ] Tool registered in DreamFarm Agent
- [ ] System prompt updated
- [ ] Integration tests passing
- [ ] End-to-end testing verified
- [ ] Docker Compose updated

### Phase 5: Documentation ✓
- [ ] Lesson README (Czech) created
- [ ] Demo script (Czech) created
- [ ] Architecture diagrams added
- [ ] ImplementationLog updated
- [ ] Design.md verified

---

## Success Criteria

1. **Functionality**:
   - ✓ Chef Services MCP server running and responding to tool calls
   - ✓ Chef Agent calling MCP tools and returning coherent responses
   - ✓ DreamFarm Agent delegating chef queries to Chef Agent
   - ✓ All tools working with mock data consistency

2. **Testing**:
   - ✓ All unit tests passing
   - ✓ Integration tests passing
   - ✓ End-to-end scenarios working via UI

3. **Deployment**:
   - ✓ MCP server deployed to Azure Container Apps
   - ✓ Chef Agent running locally (Azure deployment optional)
   - ✓ Docker Compose orchestration working

4. **Documentation**:
   - ✓ Czech README with clear explanations
   - ✓ Demo script ready for presentation
   - ✓ Architecture diagrams created

---

## Notes

- Keep all code simple and well-documented (docstrings per AGENTS.md)
- Mock data should be deterministic (same names → same IDs)
- Stateless agent simplifies testing and deployment
- Chef Agent URL configurable for local vs deployed scenarios
- Feature flag allows disabling Chef Agent tool
- All tests should be isolated (no shared state)

---

## Future Enhancements (Out of Scope for L08)

- Persistent order tracking (database)
- Real payment integration
- Chef-side interface
- Multi-turn conversation with Chef Agent
- Agent-to-Agent protocol (instead of HTTP)
- Additional agents (Nutrition, Logistics, etc.)
- Event-driven communication between agents

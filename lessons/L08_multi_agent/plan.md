# Lesson 08: Multi-Agent Architecture - Implementation Plan

## Overview
Implement a multi-agent system where a specialized Chef Agent handles culinary service queries (chefs, catering, availability, pricing) via MCP tools, and integrates with the main DreamFarm Agent using agent-as-tool pattern.

## Implementation Strategy
- **Phase 1**: MCP Chef Services Server (tools + mocks)
- **Phase 2**: Chef Agent (simple stateless API)
- **Phase 3**: Integration (Chef Agent as tool in DreamFarm Agent)
- **Phase 4**: Deployment & Documentation

---

## Phase 1: Chef Services MCP Server

### 1.1 Create Project Structure
- [ ] Create directory `tools/mcp_chef_services/`
- [ ] Copy template files from `mcp_public_farmer_tools`:
  - [ ] `pyproject.toml` (update name to "mcp-chef-services")
  - [ ] `.env.template`
  - [ ] `.python-version` (3.12)
  - [ ] `Dockerfile`
- [ ] Create `main.py` with FastMCP boilerplate
- [ ] Create `.env` from template with `MCP_API_KEY=dev-chef-secret`

### 1.2 Implement Mock Data Layer
- [ ] Create in-memory mock data structures in `main.py`:
  - [ ] `MOCK_CHEFS` - List of 10-15 chefs with:
    - `chef_id` (deterministic: `chef_001`, `chef_002`, etc.)
    - `name` (realistic names)
    - `specialties` (list: Italian, BBQ, vegan, pastry, etc.)
    - `experience_years` (int)
    - `rate_per_hour` (int, USD)
    - `bio` (short description)
    - `certifications` (list: Michelin-trained, ServSafe, etc.)
  - [ ] `MOCK_SERVICES` - List of 8-10 services with:
    - `service_id` (deterministic: `svc_001`, etc.)
    - `type` (catering, delivery, meal_prep, private_chef)
    - `name` (descriptive name)
    - `base_price_per_person` (int, USD)
    - `min_guests` / `max_guests` (int)
    - `includes` (list of what's included)
    - `description` (text)
  - [ ] `MOCK_AVAILABILITY` - Dict mapping `chef_id` to list of blocked dates
  - [ ] `MOCK_ORDER_COUNTER` - Session-level order ID counter

### 1.3 Implement MCP Tools

#### Tool: search_chefs
- [ ] Define tool with parameters:
  - `specialty` (optional str)
  - `event_type` (optional str)
  - `max_results` (optional int, default 5)
- [ ] Implement filtering logic:
  - [ ] Filter by specialty (case-insensitive partial match)
  - [ ] Filter by event_type (generic matching logic)
  - [ ] Sort by match score (simple relevance)
  - [ ] Limit results
- [ ] Return structured JSON with chef details

#### Tool: search_services
- [ ] Define tool with parameters:
  - `service_type` (required: catering, delivery, meal_prep, private_chef)
  - `guest_count` (optional int)
  - `cuisine` (optional str)
- [ ] Implement filtering logic:
  - [ ] Filter by service_type
  - [ ] Filter by guest_count capacity (min/max)
  - [ ] Filter by cuisine if provided
- [ ] Return structured JSON with service details

#### Tool: check_availability
- [ ] Define tool with parameters:
  - `chef_id` (optional str)
  - `service_id` (optional str)
  - `date` (required str, YYYY-MM-DD format)
  - `duration_hours` (optional int)
- [ ] Implement availability logic:
  - [ ] Parse and validate date (must be future)
  - [ ] Check chef blocked dates
  - [ ] Return availability status + conflicts
  - [ ] Suggest next_available_date if blocked
- [ ] Return structured JSON

#### Tool: calculate_pricing
- [ ] Define tool with parameters:
  - `chef_id` (optional str)
  - `service_id` (optional str)
  - `guest_count` (required int)
  - `duration_hours` (optional int)
  - `menu_complexity` (optional: simple, moderate, complex)
  - `additional_services` (optional list[str])
- [ ] Implement pricing calculation:
  - [ ] Base: chef hourly rate × duration OR service per-person × guest_count
  - [ ] Complexity multiplier (1.0, 1.3, 1.6)
  - [ ] Additional services surcharges
  - [ ] Build detailed breakdown
- [ ] Return structured JSON with total + breakdown

#### Tool: place_order
- [ ] Define tool with parameters:
  - `chef_id` (optional str)
  - `service_id` (optional str)
  - `date` (required str)
  - `guest_count` (required int)
  - `duration_hours` (optional int)
  - `menu_notes` (optional str)
  - `contact_info` (required object with name, email, phone)
- [ ] Implement order logic:
  - [ ] Validate date availability
  - [ ] Generate sequential order ID: `ORD_YYYYMMDD_NNN`
  - [ ] Calculate total cost using pricing logic
  - [ ] Update mock availability (block the date)
  - [ ] Return confirmation with order details
- [ ] Return structured JSON

### 1.4 Add Server Infrastructure
- [ ] Implement auth using `EnvAPIKeyVerifier` (copy from farmer_tools)
- [ ] Add CORS middleware configuration
- [ ] Add `/health` endpoint
- [ ] Add `DeferDeleteMiddleware` (copy from farmer_tools)
- [ ] Create ASGI app export for uvicorn

### 1.5 Write Unit Tests
- [ ] Create `test_mcp_chef_services.py`
- [ ] Use FastMCP test client (check farmer_tools for pattern)
- [ ] Test scenarios:
  - [ ] `search_chefs` with various filters
  - [ ] `search_services` by type and guest count
  - [ ] `check_availability` for available and blocked dates
  - [ ] `calculate_pricing` with different configurations
  - [ ] `place_order` happy path
  - [ ] `place_order` validation errors (past date, unavailable)
  - [ ] Auth: valid token vs invalid token
- [ ] Run tests: `uv run pytest test_mcp_chef_services.py -v`

### 1.6 Local Testing
- [ ] Run server locally: `uv run python main.py`
- [ ] Test with curl or HTTP client:
  - [ ] Health check: `GET http://localhost:8013/health`
  - [ ] MCP discovery: `GET http://localhost:8013/mcp/`
  - [ ] Tool invocation with Bearer token
- [ ] Manual smoke test of each tool

### 1.7 Create README
- [ ] Create `tools/mcp_chef_services/README.md`
- [ ] Document:
  - [ ] Purpose and features
  - [ ] Mock data description
  - [ ] Tool catalog with examples
  - [ ] Local setup instructions
  - [ ] Docker usage
  - [ ] Testing instructions

---

## Phase 2: Azure Deployment for Chef Services MCP

### 2.1 Create Dockerfile
- [ ] Copy Dockerfile from `mcp_public_farmer_tools`
- [ ] Update base image if needed
- [ ] Update EXPOSE port to 8013
- [ ] Update CMD to run `main.py`
- [ ] Test local build: `docker build -t mcp-chef-services:local .`
- [ ] Test local run: `docker run -p 8013:8013 -e MCP_API_KEY=test mcp-chef-services:local`

### 2.2 Add GitHub Actions Workflow
- [ ] Create `.github/workflows/build-mcp-chef-services.yml`
- [ ] Copy template from `build-mcp-public-farmer-tools.yml`
- [ ] Update:
  - [ ] Workflow name
  - [ ] Image name: `ghcr.io/tkubica12/advanced-ai-applications/mcp-chef-services`
  - [ ] Build context path: `tools/mcp_chef_services`
  - [ ] Trigger paths: `tools/mcp_chef_services/**`
- [ ] Push and verify workflow builds image

### 2.3 Create Terraform Configuration
- [ ] Create `deploy/azure/mcp_tools/container_app.chef-services.tf`
- [ ] Copy template from `container_app.farmer-tools.tf`
- [ ] Update:
  - [ ] Resource name: `azapi_resource.chef_services`
  - [ ] Container App name: `ca-mcp-chef-services`
  - [ ] Target port: 8013
  - [ ] Secret name: `chef-services-api-key`
  - [ ] Environment variables
  - [ ] Image reference variable
- [ ] Add variables to `variables.tf`:
  - [ ] `chef_services_api_key` (sensitive)
  - [ ] `chef_services_image` (default: latest from GHCR)
  - [ ] `chef_services_min_replicas` (default: 0)
- [ ] Add to `secrets.auto.tfvars`:
  - [ ] `chef_services_api_key = "your-secure-key"`
- [ ] Add to `configs.auto.tfvars`:
  - [ ] Image URL
  - [ ] Min replicas
- [ ] Add output to `outputs.tf`:
  - [ ] `chef_services_url` (FQDN)

### 2.4 Deploy to Azure
- [ ] Run Terraform:
  ```bash
  cd deploy/azure/mcp_tools
  terraform init
  terraform plan
  terraform apply
  ```
- [ ] Verify deployment:
  - [ ] Check Container App in Azure Portal
  - [ ] Test health endpoint: `https://<fqdn>/health`
  - [ ] Test MCP endpoint with Authorization header

### 2.5 Create Integration Tests for Remote MCP
- [ ] Create `tests/test_remote_chef_mcp.py`
- [ ] Use environment variable `CHEF_SERVICES_MCP_URL`
- [ ] Use environment variable `CHEF_SERVICES_MCP_API_KEY`
- [ ] Test scenarios:
  - [ ] Discovery (list tools)
  - [ ] Each tool invocation with remote server
  - [ ] Auth failure scenarios
- [ ] Run: `pytest tests/test_remote_chef_mcp.py -v`

---

## Phase 3: Chef Agent Implementation

### 3.1 Create Agent Project Structure
- [ ] Create directory `agents/chef-agent/`
- [ ] Create `pyproject.toml`:
  - [ ] Name: "chef-agent"
  - [ ] Dependencies: `fastapi`, `openai`, `python-dotenv`, `httpx`, `pydantic`
- [ ] Create `.env.template`:
  - [ ] `OPENAI_API_KEY`
  - [ ] `OPENAI_MODEL` (default: gpt-4o)
  - [ ] `OPENAI_BASE_URL` (optional, for Azure)
  - [ ] `OPENAI_API_VERSION` (optional, for Azure)
  - [ ] `CHEF_MCP_SERVER_URL` (http://localhost:8013/mcp)
  - [ ] `CHEF_MCP_API_KEY`
  - [ ] `HOST` (default: 0.0.0.0)
  - [ ] `PORT` (default: 8002)
- [ ] Create `.env` from template
- [ ] Create `.python-version` (3.12)
- [ ] Run `uv sync`

### 3.2 Implement Agent Core
- [ ] Create `src/main.py` (FastAPI app)
- [ ] Create `src/models/`:
  - [ ] `message.py`: `QueryRequest(message: str)`, `QueryResponse(response: str)`
- [ ] Create `src/services/`:
  - [ ] `openai_service.py`: Unified OpenAI client (copy from dreamfarm-agent)
  - [ ] `mcp_client.py`: MCP tool client for Chef Services
  - [ ] `chef_agent_service.py`: Core agent logic

### 3.3 Implement Chef Agent Service
- [ ] Create system prompt for Chef Agent:
  ```
  You are a culinary services assistant specializing in connecting customers 
  with professional chefs and catering services. You help plan events, 
  recommend chefs based on cuisine preferences and dietary needs, check 
  availability, and provide accurate pricing quotes.
  
  When discussing services:
  - Always verify availability before quoting final prices
  - Clarify guest count and dietary restrictions early
  - Explain what's included in each service tier
  - Provide chef profiles with specialties and experience
  - Confirm all details before placing orders
  
  You have access to the following tools:
  - search_chefs: Find chefs by specialty or event type
  - search_services: Find catering/delivery/meal prep services
  - check_availability: Check if a chef/service is available on a date
  - calculate_pricing: Get cost estimates with detailed breakdown
  - place_order: Book a chef or service (confirm with user first!)
  ```
- [ ] Implement stateless query method:
  - [ ] Accept message string
  - [ ] Register Chef Services MCP tools
  - [ ] Call OpenAI Responses API with tools
  - [ ] Handle tool calls (invoke MCP server)
  - [ ] Return final text response
- [ ] No conversation history (stateless)

### 3.4 Implement MCP Client
- [ ] Create MCP HTTP client:
  - [ ] Discovery: GET `/mcp/` to list tools
  - [ ] Invocation: POST `/mcp/` with tool name + args
  - [ ] Auth: Add `Authorization: Bearer <token>` header
- [ ] Parse MCP responses
- [ ] Error handling and retries

### 3.5 Create API Endpoint
- [ ] POST `/query`:
  - [ ] Request: `{"message": "string"}`
  - [ ] Response: `{"response": "string"}`
  - [ ] No auth (simplified for Phase 1)
  - [ ] CORS enabled (for testing)
- [ ] GET `/health`:
  - [ ] Return 200 OK

### 3.6 Write Agent Tests
- [ ] Create `tests/test_chef_agent.py`
- [ ] Mock MCP server responses
- [ ] Test scenarios:
  - [ ] Simple chef search query
  - [ ] Availability check workflow
  - [ ] Pricing calculation
  - [ ] Multi-turn workflow (search → check → price → order)
  - [ ] Error handling (tool failures)
- [ ] Run: `uv run pytest tests/ -v`

### 3.7 Local Testing
- [ ] Run MCP server: `cd tools/mcp_chef_services && uv run python main.py`
- [ ] Run agent: `cd agents/chef-agent && uv run uvicorn src.main:app --reload --port 8002`
- [ ] Test with curl:
  ```bash
  curl -X POST http://localhost:8002/query \
    -H "Content-Type: application/json" \
    -d '{"message": "Find me an Italian chef for 20 people"}'
  ```
- [ ] Verify agent calls MCP tools correctly

### 3.8 Create Agent README
- [ ] Create `agents/chef-agent/README.md`
- [ ] Document:
  - [ ] Purpose (specialized culinary services agent)
  - [ ] Architecture (stateless API + MCP tools)
  - [ ] Setup instructions
  - [ ] Environment variables
  - [ ] API specification
  - [ ] Example queries
  - [ ] Testing instructions

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

### Phase 2: Azure Deployment ✓
- [ ] Dockerfile created
- [ ] GitHub Actions workflow created
- [ ] Terraform configuration created
- [ ] Deployed to Azure Container Apps
- [ ] Remote integration tests passing

### Phase 3: Chef Agent ✓
- [ ] Agent project created
- [ ] MCP client implemented
- [ ] Chef Agent service with system prompt
- [ ] Stateless API endpoint (/query)
- [ ] Unit tests written
- [ ] Local testing with MCP server verified
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

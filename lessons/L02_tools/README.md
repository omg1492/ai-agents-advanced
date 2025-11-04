# Lekce 02 - Používání nástrojů (Web search, API, MCP)
V této lekci rozšíříme základní chatbot o schopnost volat nástroje. Model si může dynamicky vyžádat externí data a pak pokračovat v odpovědi. Oproti lekci 01 přibývají tři zdroje:

- Cloud MCP Farmer Tools (sezónní tipy, počasí, čas)
- Tavily (web / news search)
- Lokální Stock API (aktuální sklad - funkce `get_stock`)

**MCP Farmer Tools běží v cloudu** na adrese `https://farmer-tools.tomasdemo.org/mcp/`. API klíč vám předá lektor/průvodce. Lokálně už nic nespouštíte.

**Docker Compose nyní startuje i Stock API**, takže není třeba pouštět `tools/api_stock` ručně:
```bash
cd tools/api_stock/
uv run main.py 
```

**Koncepty:**
- Tool-use (function call + MCP)
- Kombinace RAG (katalog) + dynamická data (stock, web, sezónnost)
- Transparentnost volání nástrojů ve streamu

**Technologie:**
- OpenAI Responses API (GPT‑5)
- MCP (Farmer Tools, Tavily)
- FastAPI (agent, stock)
- PostgreSQL + pgvector (z předchozí lekce - volitelné)

# Ukázka (teacher branch)

## Rychlé spuštění
1. Spusťte infrastrukturu (PostgreSQL + stock API) pokud neběží:
	```bash
	cd deploy/local
	export DOCKER_DEFAULT_PLATFORM=linux/amd64 && docker compose up -d postgres api-stock
	```

2. Naimportujte stock data (pokud ještě nebyla naimportována):
	```bash
	cd data/scripts
	uv run configure_postgresql.py
	uv run import_simple_products.py
	uv run import_stock.py
	```

3. Frontend (pokud neběží):
	```bash
	cd frontend
	npm install
	npm run dev
	```
4. DreamFarm Agent:
	```bash
	cd agents/dreamfarm-agent
	uv sync
	uv run dreamfarm-agent
	```
5. Otevřete UI na `http://localhost:3000`.

---
## .env pro agent (minimální výřez)
```env
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5

# (Volitelné) RAG
ENABLE_RAG=true
PGHOST=localhost
PGPORT=5432
PGDATABASE=aidb
PGUSER=admin
PGPASSWORD=Admin12345678
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Stock tool (docker compose → http://localhost:8011)
STOCK_TOOL_ENABLED=true
STOCK_API_URL=http://localhost:8011

# Cloud Farmer Tools (MCP)
FARMER_TOOLS_ENABLED=true
FARMER_TOOLS_MCP_URL=https://farmer-tools.tomasdemo.org/mcp/
FARMER_TOOLS_MCP_API_KEY=<klíč od lektora>

# Tavily web search
TAVILY_ENABLED=true
TAVILY_API_KEY=<váš_tavily_key>
```

**Tavily klíč:** Získejte registrací na https://app.tavily.com/ (free tier stačí), v uživatelském dashboardu zkopírujte API key. Pokud klíč nemáte, nastavte `TAVILY_ENABLED=false`.


## Jak to funguje
- `OpenAIService.get_tools()` zaregistruje: MCP tool „farmer-tools“, MCP tool „tavily“ (pokud klíč) a lokální function tool `get_stock`.
- Model při potřebě dat vrátí `function_call` → agent zavolá REST (`POST /stock`) a výsledek pošle zpět přes `submit_tool_outputs`.
- UI zobrazuje průběh (DF_META) - uvidíte, kdy byl nástroj volán.

---
## Zkuste se zeptat
1. „What seasonal farm products do you recommend this month?“ (Farmer Tools)
2. „Do we have stock for product <UUID>?“ (Stock - použijte reálné UUID z DB) - pokud používáte přepřipravená data, zkuste `083166ea-c088-40cc-bc06-4e5e506210f8` a očekávejte výsledek 176
3. „Find two recent recipe ideas using goat cheese and cite sources. Use Internet search and give me links.“ (Tavily)
4. „Recommend two goat aged cheeses from the catalog and check their stock.“ (RAG + Stock)

Pokud nevidíte žádné tool volání, zkontrolujte logy a env proměnné.

# Úkol (student branch)
Nástroje jsou pro vás připravené - MCP v cloudu, API pustíte lokálně, DB import do stocks je pro vás připraven. Přidejte do aplikace nástroje tak, jak jsme ukazovali - Tavily search, Stock nástroj přes API a farmer tools přes MCP.

## GitHub Copilot - příklady promptů pro implementaci

Zde jsou navržené prompty, které můžete použít s GitHub Copilotem k implementaci jednotlivých nástrojů:

### 1. Přidání Stock API nástroje (Function Calling)

```
I need to add a Stock API tool to the DreamFarm agent. The tool should:
1. Create a new StockService in agents/dreamfarm-agent/src/services/stock_service.py that:
   - Connects to Stock API at STOCK_API_URL from environment
   - Has a get_stock(product_ids) async method that calls POST /stock with {"productIds": [...]}
   - Returns list of StockItem with product_id and on_stock fields
   - Can be enabled/disabled via STOCK_TOOL_ENABLED env var
2. Add StockToolConfig to config_service.py with enabled and api_url fields
3. In openai_service.py:
   - Add stock_service parameter to __init__
   - Create get_tools() method that returns a function tool definition for "get_stock"
   - In generate_response(), implement a loop that extracts function_call items and executes get_stock
4. In main.py:
   - Initialize StockService in lifespan
   - In streaming endpoint, handle function_call items, execute get_stock, and submit outputs

Use httpx for HTTP calls, follow existing patterns in the codebase.
```

### 2. Přidání Farmer Tools (Remote MCP)

```
I need to add Farmer Tools as a remote MCP server tool to the DreamFarm agent. The tool should:
1. Add FarmerToolsConfig dataclass to config_service.py with:
   - enabled: bool
   - mcp_url: str (default "https://farmer-tools.tomasdemo.org/mcp/")
   - mcp_api_key: str
   - Load from FARMER_TOOLS_ENABLED, FARMER_TOOLS_MCP_URL, FARMER_TOOLS_MCP_API_KEY env vars
2. In openai_service.py get_tools() method, add MCP tool definition:
   - type: "mcp"
   - server_label: "farmer-tools"
   - server_url: from config
   - headers: {"Authorization": f"Bearer {api_key}"}
   - require_approval: "never"
3. The OpenAI Responses API will handle MCP tool calls automatically, no manual execution needed
4. Update system_prompt.j2 to mention Farmer Tools availability

Follow the existing code style and patterns.
```

### 3. Přidání Tavily Search (Remote MCP)

```
I need to add Tavily Search as a remote MCP server tool to the DreamFarm agent. The tool should:
1. Add TavilyConfig dataclass to config_service.py with:
   - enabled: bool
   - api_key: str
   - mcp_url: str (default "https://mcp.tavily.com/mcp/")
   - Load from TAVILY_ENABLED and TAVILY_API_KEY env vars
2. In openai_service.py get_tools() method, add MCP tool definition:
   - type: "mcp"
   - server_label: "tavily"
   - server_url: f"{mcp_url}?tavilyApiKey={api_key}" (API key goes in URL query param)
   - require_approval: "never"
3. The OpenAI Responses API will handle MCP tool calls automatically
4. Update system_prompt.j2 to mention web search capability via Tavily

Follow the existing code patterns and conventions.
```

### 4. Komplexní implementace všech tří nástrojů najednou

```
I need to add three tools to the DreamFarm agent following the teacher implementation:

1. Stock API (Function Calling):
   - Create StockService that calls POST /stock API endpoint
   - Add StockToolConfig to config_service.py
   - Register as function tool in openai_service.get_tools()
   - Implement tool execution loop in openai_service.generate_response() and main.py streaming

2. Farmer Tools (Remote MCP):
   - Add FarmerToolsConfig with mcp_url and mcp_api_key
   - Register as MCP tool with Bearer auth header

3. Tavily Search (Remote MCP):
   - Add TavilyConfig with api_key
   - Register as MCP tool with API key in URL query param

All tools should:
- Be configurable via environment variables with *_ENABLED flags
- Follow existing service patterns and code conventions
- Include proper logging and error handling
- Update system_prompt.j2 to document available tools

Reference the teacher branch implementation in agents/dreamfarm-agent for exact patterns.
```

## Tipy pro úspěšnou implementaci

1. **Postupujte krok po kroku**: Implementujte nejprve jeden nástroj, otestujte, pak přidejte další.
2. **Zkontrolujte .env**: Ujistěte se, že máte správně nastavené environment variables.
3. **Sledujte logy**: Agent loguje všechny tool volání - pomůže vám to s debugováním.
4. **Testujte jednotlivě**: Pro každý nástroj zkuste konkrétní otázku z příkladů výše.
5. **Použijte teacher branch jako referenci**: Pokud si nejste jistí implementací, podívejte se do učitelské větve.

## Myšlenky navíc, pokud zbývá čas
Můžete předělat stock API na MCP jednou z těchto cest:
- Použijte konverzi, například Azure API Management dokáže z vystaveného API udělat MCP
- Přidejte k API ještě přímo MCP podporu s využitím FastMCP knihovny

Předělejte nástroj tak, aby i stock API bylo přes MCP volání z Responses API (public endpoint - nasaďte do Container Apps apod.). Možná by stálo za to přidat zabezpečení, alespoň řpes api klíč, nebo ještě lépe JWT. S tím může pomoci opět API Management nebo vyřešte v kódu.
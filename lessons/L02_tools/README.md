## Lekce 02 – Používání nástrojů (Web search, API, MCP)
V této lekci rozšíříme základní chatbot o schopnost volat nástroje. Model si může dynamicky vyžádat externí data a pak pokračovat v odpovědi. Oproti lekci 01 přibývají tři zdroje:

- Cloud MCP Farmer Tools (sezónní tipy, počasí, čas)
- Tavily (web / news search)
- Lokální Stock API (aktuální sklad – funkce `get_stock`)

**MCP Farmer Tools běží v cloudu** na adrese `https://farmer-tools.tomasdemo.org/mcp/`. API klíč vám předá lektor/průvodce. Lokálně už nic nespouštíte.

**Docker Compose nyní startuje i Stock API**, takže není třeba pouštět `tools/api_stock` ručně.

**Koncepty:**
- Tool-use (function call + MCP)
- Kombinace RAG (katalog) + dynamická data (stock, web, sezónnost)
- Transparentnost volání nástrojů ve streamu

**Technologie:**
- OpenAI Responses API (GPT‑5)
- MCP (Farmer Tools, Tavily)
- FastAPI (agent, stock)
- PostgreSQL + pgvector (z předchozí lekce – volitelné)

---
### Rychlé spuštění
1. Spusťte infrastrukturu (PostgreSQL + stock API) pokud neběží:
	```pwsh
	cd deploy/local
	docker compose up -d postgres api-stock
	```
2. Frontend (pokud neběží):
	```pwsh
	cd frontend
	npm install
	npm run dev
	```
3. DreamFarm Agent:
	```pwsh
	cd agents/dreamfarm-agent
	uv sync
	uv run dreamfarm-agent
	```
4. Otevřete UI na `http://localhost:3000`.

---
### .env pro agent (minimální výřez)
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

---
### Jak to funguje
- `OpenAIService.get_tools()` zaregistruje: MCP tool „farmer-tools“, MCP tool „tavily“ (pokud klíč) a lokální function tool `get_stock`.
- Model při potřebě dat vrátí `function_call` → agent zavolá REST (`POST /stock`) a výsledek pošle zpět přes `submit_tool_outputs`.
- UI zobrazuje průběh (DF_META) – uvidíte, kdy byl nástroj volán.

---
### Zkuste se zeptat
1. „What seasonal farm products do you recommend this month?“ (Farmer Tools)
2. „Do we have stock for product <UUID>?“ (Stock – použijte reálné UUID z DB)
3. „Find two recent recipe ideas using goat cheese and cite sources. Use Internet search and give me links.“ (Tavily)
4. „Recommend two goat aged cheeses from the catalog and check their stock.“ (RAG + Stock)

Pokud nevidíte žádné tool volání, zkontrolujte logy a env proměnné.


# Lekce 06 – Ad hoc kódování & Vizualizační artefakty

V této lekci navazujeme na paměť a hlas (Lekce 05) a přidáváme schopnost ad‑hoc datové analýzy a okamžité generování vizuálních HTML artefaktů. Cílem je dát uživateli možnost přinést vlastní data (např. sledování váhy, nutriční záznamy, jednoduché tabulky) a ihned z nich získat přehledové statistiky, grafy a estetické vizualizace podporující engagement i konverze na marketplace.

## Implementace ad‑hoc výpočtů (Code Interpreter)
- Upload souboru přes frontend vede na Azure OpenAI Files API a vrací `file_id`.
- Při dotazu aktivujeme nástroj `code_interpreter` a předáme seznam příslušných `file_ids`.
- Sandbox Python skript se spouští izolovaně; výstupy (text / obrázky) se vrací v metadatech `annotations` (obsah: `file_id`, `filename`, volitelně `container_id`).
- Backend spravuje mapu souborů + generuje krátkodobé download tokeny (časově omezené, žádný trvalý storage).
- Přístup k souboru: preferovaně přes kontejner (`/containers/{container_id}/files/...`), fallback na `/files/{file_id}/content` pro robustnost.
- Frontend překládá sandbox cesty `sandbox:/mnt/data/...` na veřejné proxy URL s tokenem (`/files/{file_id}/content?token=...`).
- Obrázky (PNG/JPG/WEBP) se automaticky renderují jako Markdown image bez potřeby Bearer tokenu; textové výstupy se vkládají přímo.
- Data se po expiraci tokenu stávají nedostupnými – neprovádí se žádný archiv.

## Implementace vizualizačního MCP serveru
- Dostupný nástroj `generate_infographic` (MCP server na Azure Container Apps) vytváří kompletní HTML artefakty.
- Po obdržení tool response backend extrahuje HTML, generuje UUID a ukládá ho do in-memory registru s TTL (1 h).
- Událost `DF_META` informuje frontend o vytvoření artefaktu (`visualization.artifact_created`, `artifact_id`).
- Do zprávy pro uživatele se vloží odkaz `[View Visualization](/artifacts/{uuid})` – renderer ho detekuje a nahrazuje komponentou s iframe.
- Iframe je sandboxovaný (`allow-same-origin`), bez povolení skriptů třetích stran; bezpečnostní vrstva brání XSS.
- HTML je účelově bez externích CDN závislostí (rychlejší render, menší riziko výpadků).
- Expirace artefaktu zajišťuje automatické čištění paměti – žádná dlouhodobá persistence.

## Jak vyzkoušet (rychlý start)
1. Spusťte lokální infrastrukturu (PostgreSQL, Keycloak, stock API – pokud již neběží):
```pwsh
cd deploy/local
docker compose up -d postgres keycloak api-stock
```

2. Inicializujte data (volitelné – jen pokud jste ještě neprošli předchozí lekce):
```pwsh
cd data/scripts
uv run configure_postgresql.py
uv run import_all.py
```

3. Spusťte agenta (feature flagy pro ad‑hoc výpočty / vizualizace dle konfigurace):
```pwsh
cd agents/dreamfarm-agent
uv run dreamfarm-agent
```

4. Spusťte frontend:
```pwsh
cd frontend
npm install
npm run dev
```

## Rychlý demonstrační flow
1. Nahrajte soubor `data/user_upload/user_data.csv` zeptejte se `Který týden jsem měl nejvyšší hmotnost a jak jsem se u toho cítil` - použije Code Interpreter pro napsání Python kódu pro parsing CSV a výpočty
2. `Vykresli čárový graf mé hmotnosti` - použije Code Interpreter a s Matplotlib vytvoří graf
3. `Potřebuji hezkou infografiku s hodně růžové barvy, kde bude vidět můj hmotnostní cíl 79kg do konce ledna a krátké motivační fráze na ráno, poledne a večer.` - použije náš vlastní vizualizační generátor (mám spuštěn jako MCP) pro vytvoření HTML/Javascript grafického prvku

# Úkol (student branch)
Ve studentském branch nejsou některé věci implementovány:
- Možnost uploadovat soubory v UI máte připravenou i včetně backendového API, ale nástroj Code Interpreter není registrován.
- Nástroj pro generování vizualizací v HTML/Javascript máte za úkol vytvořit a je na vás, zda to bude někde hostovaný MCP server (podobně jako naše farm tools), lokální API (podobně jako naše stock API) nebo přímo v kódu použitý Function Calling (podobně jako třeba náš agentic search).

## GitHub Copilot – příklady promptů pro začátek

Níže jsou příklady promptů pro GitHub Copilot. Copilot funguje nejlépe s kontextem – vysvětlete mu co chcete dosáhnout, jaké technologie používáte a jaké jsou kroky k řešení.

### Úkol 1: Registrace Code Interpreter nástroje
```markdown
Help me register the code_interpreter tool in our OpenAI Responses API integration so the agent can execute Python code for data analysis.
Steps:
1. In openai_service.py, extend the get_tools() method to append a code_interpreter tool definition when ENABLE_CODE_INTERPRETER=true.
2. The tool definition should be: {"type": "code_interpreter", "container": {"type": "auto", "file_ids": [...]}} where file_ids contains uploaded file IDs passed as a parameter.
3. In main.py streaming loop, after the final response, parse response.output items with type='message' to find annotations containing file_id, container_id, and filename for generated files.
4. Create an in-memory registry (_generated_files dict) mapping file_id to download tokens with 1-hour TTL.
5. Emit a DF_META event with structure: {"kind": "tool_event", "event_type": "code_interpreter.files_generated", "files": [{"file_id": "...", "download_token": "...", "filename": "...", "container_id": "..."}]}.
6. Keep reasoning minimal and only register the tool when the feature flag is enabled.
Return the necessary code changes and any new environment variables I need to set.
```

### Úkol 2: Implementace vizualizačního generátoru (MCP server varianta)
```markdown
Help me create a visualization generator tool that produces custom HTML artifacts for health dashboards and motivational infographics.
Option A: Implement as a remote MCP server (recommended for flexibility).
Steps:
1. Create a new FastAPI-based MCP server in tools/mcp_visualization_generator/ with one tool: generate_infographic.
2. The tool accepts parameters: title (string), colorScheme (string), goals (array of strings), optional csvFileId (string).
3. Use a reasoning model (gpt-4o or o1) to generate self-contained HTML with inline CSS (no external CDN dependencies).
4. Sanitize the output HTML using bleach or lxml to allow only safe tags: div, span, h1-h6, p, ul, li, table, canvas, style. Strip all script tags and inline event handlers.
5. Return JSON structure: {"type": "custom_ui", "html": "<div>...</div>"}.
6. In openai_service.py, register the tool as: {"type": "mcp", "server_label": "visualization", "server_url": "...", "headers": {"Authorization": "Bearer ..."}}.
7. In main.py, parse MCP tool call outputs for type='mcp_call' and name='generate_infographic', extract the HTML, generate a UUID, and store in an artifact registry with 1-hour TTL.
8. Emit DF_META event: {"kind": "tool_event", "event_type": "visualization.artifact_created", "artifact_id": "...", "timestamp": "..."}.
9. Insert a link in the response text: "[View Visualization](/artifacts/{uuid})" for frontend rendering.
Provide code patches, Dockerfile, .env.template, and setup instructions.
```

### Úkol 2 (alternativa): Implementace vizualizačního generátoru (lokální function tool)
```markdown
Help me add a generate_infographic tool as a local function (not MCP) that the agent can call directly.
Steps:
1. In openai_service.py, add to get_tools(): {"type": "function", "name": "generate_infographic", "parameters": {...}} with fields: title, colorScheme, goals (array), optional csvFileId.
2. In the generate_response() tool call loop, detect when name == "generate_infographic" and handle it locally.
3. Parse the arguments and use gpt-4o to generate self-contained HTML (system prompt: "Generate a health goal infographic card with inline CSS, no external scripts").
4. Sanitize the HTML output (bleach whitelist: div, span, h1-h6, p, ul, li, canvas, style).
5. Generate a UUID, store the artifact in a global dict with 1-hour TTL: _html_artifacts[uuid] = {"html": "...", "created_at": timestamp}.
6. Return tool output: {"artifact_id": uuid, "html_length": len(html)}.
7. In main.py streaming, emit DF_META event when function_call completes: {"kind": "tool_event", "event_type": "visualization.artifact_created", "artifact_id": "..."}.
8. Insert link in response text: "[View Visualization](/artifacts/{uuid})".
Provide code patches for openai_service.py and main.py.
```

### Úkol 2 (bezpečnost): Bezpečnostní sanitizace HTML artefaktů
```markdown
Before storing HTML artifacts, implement robust sanitization to prevent XSS attacks.
Requirements:
1. Create a sanitize_html(html: str) -> str helper function using bleach or lxml.
2. Allowed tags: div, span, h1, h2, h3, h4, h5, h6, p, ul, ol, li, table, thead, tbody, tr, td, th, canvas, svg, style.
3. Strip all script tags and inline event handlers (onclick, onerror, onload, etc.).
4. Remove any javascript: URLs in href or src attributes.
5. Add unit tests: test_sanitize_removes_script(), test_sanitize_removes_event_handlers(), test_sanitize_allows_safe_tags(), test_sanitize_preserves_inline_css().
Provide the helper function, test cases, and integration points in the visualization generator.
```

## Další možné rozšíření (dobrovolně)
- Vymyslet více interaktivní vizualizace, ale dopředu připravené (například React komponenta)
- Posunout generované UI do ad-hoc generování jednotlivých kroků (kliků) bez přípravy dopředu (každý klik = nový LLM generovaný kód), třeba s HTMX

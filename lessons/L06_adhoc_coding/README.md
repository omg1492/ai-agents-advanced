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
- Možnost uploadovat soubory v UI máte připravenou i včetně backendového API, ale nástroj Code Interpreter není registrován.
- Nástroj pro generování vizualizací v HTML/Javascript máte za úkol vytvořit a je na vás, zda to bude někde hostovaný MCP server (podobně jako naše farm tools), lokální API (podobně jako naše stock API) nebo přímo v kódu pooužitý FUnction Caling (podobně jako třeba náš agentic search)
  
## Další možné rozšíření (dobrovolně)
- Vymyslet více interaktivní vizualizace, ale dopředu připravené (například React komponenta)
- Posunout generované UI do ad-hoc generování jednotlivých kroků (kliků) bez přípravy dopředu (každý klik = nový LLM generovaný kód), třeba s HTMX

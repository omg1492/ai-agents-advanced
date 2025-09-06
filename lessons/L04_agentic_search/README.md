

## Lekce 04 – Agentic Search, Knowledge Graph & RAG Fencing

V této lekci jsme nad předchozí hybridní RAG architekturou (Lekce 03) přidali řízené (agentic) vyhledávání pomocí nástrojů, základ znalostního grafu v PostgreSQL/AGE a řízení přístupu k produktům (fencing) podle VIP příznaku uživatele. Součástí je autentizace přes Keycloak a filtrování výsledků uživateli ještě předtím, než se dostanou do promptu LLM.

### Byznys motivace
Ne všichni zákazníci mají mít přístup k prémiovým (VIP) produktům. Potřebujeme schopnost řídit přístup a zároveň umožnit hlubší iterativní (multi‑step) vyhledávání – LLM si samo zvolí, kdy použije sémantické nebo klíčové (keyword) hledání, případně je zkombinuje přes několik kroků.

### Novinky oproti lekci 03
1. Autentizace a autorizace přes Keycloak + extrakce identity (userId, isVip) na backendu i frontendu.
2. Sloupec `is_vip` u produktů + datová pipeline, která náhodně označí ~10 % produktů jako VIP.
3. Agentic (tool‑based) search: dvě nástrojové funkce – semantic search (s HyDE generovaným textem) a keyword search (full‑text). LLM rozhoduje o jejich volání.
4. RAG fencing: automatické filtrování `is_vip` v obou nástrojích (nevzniká riziko, že model uvidí nepovolená data).
5. Základ Knowledge Graphu v Apache AGE: uzly (producenti, produkty, alergeny, certifikace) a hrany mezi nimi podle importovaných JSON souborů.
6. Skripty pro import grafu (`import_graph_age.py`) a standardní produkty + stock + embeddings.
7. Připraveno pro rozšíření o kategorii a kuchyně (pipeline zatím TODO – viz plán).

### Koncepty v praxi
- Agentic / iterativní vyhledávání řízené LLM (function calling)
- RAG fencing (row‑level bezpečnost na aplikační vrstvě před promptem)
- Knowledge graph (AGE) jako budoucí dodatečný zdroj kontextu
- HyDE (hypotetický dokument) pro zlepšení sémantického dotazu v semantic toolu

### Technologie
- Keycloak (OAuth2 / OIDC) – demo uživatelé `user1` (běžný), `vipuser` (VIP)
- PostgreSQL + pgvector + Apache AGE
- FastAPI backend (DreamFarm Agent) s OpenAI Responses API (tool calling)
- React frontend (assistant-ui) s přihlášením a předáním JWT

### Implementované prvky
- `is_vip` sloupec a filtrování ve vyhledávacích nástrojích
- Feature flagy: `ENABLE_RAG`, `ENABLE_AGENTIC_SEARCH`, `REQUIRE_AUTH`
- Keycloak container v `docker-compose` + skripty pro vytvoření demo uživatelů
- AGE inicializace + import grafu (producent ↔ produkt, produkt ↔ alergen, produkt ↔ certifikace)
- System prompt doplněn o striktní groundování produktových tvrzení

### Jak vyzkoušet (rychlý start)
1. Spusťte lokální infrastrukturu (PostgreSQL, Keycloak, stock API, agent – pokud ještě neběží):
```pwsh
cd deploy/local
docker compose up -d postgres keycloak api-stock
```
2. Inicializujte data (pokud jste ještě neprováděli v předchozích lekcích):
```pwsh
cd data/scripts
uv sync
uv run gen_basic_data.py            # základní produkty
uv run embeddings_products.py       # embeddings (přidělí také is_vip)
uv run import_products.py
uv run import_stock.py
uv run import_graph_age.py --reset  # AGE graf (producenti, alergeny, certifikace)
```
3. (Volitelně) vytvoření Keycloak uživatelů – pokud máte připravený skript (např. `provision_keycloak.py` v `identity/`):
```pwsh
cd identity
uv sync
uv run provision_keycloak.py
```
4. Spusťte agenta s autentizací a agentic search (příklad .env hodnot):
```env
REQUIRE_AUTH=true
ENABLE_RAG=false
ENABLE_AGENTIC_SEARCH=true
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```
```pwsh
cd agents/dreamfarm-agent
uv sync
uv run dreamfarm-agent
```
5. Frontend:
```pwsh
cd frontend
npm install
npm run dev
```
6. Otevřete `http://localhost:3000`, přihlaste se:
	- Běžný uživatel: `user1 / user1123`
	- VIP uživatel: `vipuser / vipuser123`
7. Položte dotaz typu: „Ukaž mi nějaké prémiové nebo exkluzivní produkty“.
	- Jako VIP uvidíte i položky se `is_vip = true`.
	- Jako běžný uživatel se VIP produkty ve výsledcích vůbec neobjeví.
8. Zapněte/porovnejte i klasický jednoduchý RAG (`ENABLE_RAG=true`, `ENABLE_AGENTIC_SEARCH=false`) pro rozdíl: klasický RAG (bez fencing) vs. agentic search (s fencing).

### Ověření VIP Fencingu v databázi
V databázi si náhodně vyberte produkt s `is_vip = true` a zkuste jej najít jako oba uživatelé – jen VIP by měl produkt „vidět“ ve výsledcích (výpis z agentic tool call meta eventů nebo v odpovědi).

### Další kroky (TODO / plán)
- LLM‑řízené rozšíření grafu o kategorie (~50) a kuchyně (~20) + automatická klasifikace produktů → uložit (JSON/Parquet) + import skriptem.
- Propojení agentic search s grafovými traversal dotazy (další nástroj).

### Shrnutí
Máme funkční agentic tool‑based search se striktním filtrováním citlivých (VIP) produktů a základ znalostního grafu. To vytváří základ pro hlubší semantické i strukturální dotazování v dalších lekcích.

---
Rychlý test: Přihlaste se jako `vipuser` a položte dotaz na „prémiové“ nebo „exkluzivní“ produkty – měli byste získat i VIP položky; jako `user1` nikoli.


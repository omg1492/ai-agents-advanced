## Lekce 04 - Agentic Search, Knowledge Graph & RAG Fencing

V této lekci jsme nad předchozí hybridní RAG architekturou (Lekce 03) přidali řízené (agentic) vyhledávání pomocí nástrojů, základ znalostního grafu v PostgreSQL/AGE a řízení přístupu k produktům (fencing) podle VIP příznaku uživatele. 
Součástí je autentizace přes Keycloak a filtrování výsledků uživateli ještě předtím, než se dostanou do promptu LLM.

## Byznys motivace
Ne všichni zákazníci mají mít přístup k prémiovým (VIP) produktům. Potřebujeme schopnost řídit přístup a zároveň umožnit hlubší iterativní (multi‑step) vyhledávání - LLM si samo zvolí, kdy použije sémantické nebo klíčové (keyword) hledání, použití grafu, nadřazených konceptů a tak podobně.

## Novinky oproti lekci 03
1. Autentizace a autorizace přes Keycloak + extrakce identity (userId, isVip) na backendu i frontendu.
2. Sloupec `is_vip` u produktů + datová pipeline, která náhodně označí ~10 % produktů jako VIP.
3. Agentic (tool‑based) search: dvě nástrojové funkce - semantic search (s HyDE generovaným textem) a keyword search (full‑text). LLM rozhoduje o jejich volání.
4. RAG fencing: automatické filtrování `is_vip` v obou nástrojích (nevzniká riziko, že model uvidí nepovolená data).
5. Základ Knowledge Graphu v Apache AGE: uzly (producenti, produkty, alergeny, certifikace) a hrany mezi nimi podle importovaných JSON souborů.
6. Skripty pro import grafu (`import_graph_age.py`) a standardní produkty + stock + embeddings.
7. Přidány dva grafové nástroje (feature flag `GRAPH_SEARCH_ENABLED`):
	- `graph_dfs_similarity_search` - „DFS" (podobnostní rozšíření od konkrétního produktu podle sdílených kategorií/kuchyní/certifikací/alergenů + producent bonus).
	- `graph_bfs_taxonomy_search` - „BFS / taxonomy expansion" (široký dotaz → embedding → výběr relevantních pojmů taxonomy → produkty napojené na jakýkoli z nich, skórování váženým součtem).
8. VIP fencing aplikován i v grafových nástrojích (model nikdy nedostane VIP produkt, pokud uživatel není VIP).
9. System prompt nyní explicitně popisuje dostupné grafové nástroje a kdy je použít.

## Koncepty v praxi
- Agentic / iterativní vyhledávání řízené LLM (function calling)
- RAG fencing (row‑level bezpečnost na aplikační vrstvě před promptem)
- Knowledge graph (AGE) jako dodatečný zdroj kontextu
- HyDE (hypotetický dokument) pro zlepšení sémantického dotazu v semantic toolu

## Technologie
- Keycloak (OAuth2 / OIDC) - demo uživatelé `user1` (běžný), `vipuser` (VIP)
- PostgreSQL + pgvector + Apache AGE
- FastAPI backend (DreamFarm Agent) s OpenAI Responses API (tool calling)
- React frontend (assistant-ui) s přihlášením a předáním JWT

## Implementované prvky
- `is_vip` sloupec a filtrování ve vyhledávacích nástrojích
- Feature flagy: `ENABLE_RAG`, `AGENTIC_SEARCH_ENABLED`, `AUTH_ENABLED`
- Keycloak container v `docker-compose` + skripty pro vytvoření demo uživatelů
- AGE inicializace + import grafu (producent ↔ produkt, produkt ↔ alergen, produkt ↔ certifikace)
- System prompt doplněn o striktní groundování produktových tvrzení
  
# Ukázka (teacher branch)

## Jak vyzkoušet (rychlý start)
1. Spusťte lokální infrastrukturu (PostgreSQL, Keycloak, stock API, agent - pokud ještě neběží):
```bash
cd deploy/local
export DOCKER_DEFAULT_PLATFORM=linux/amd64 && docker compose up -d postgres keycloak api-stock
```
2. Inicializujte data (pokud jste ještě neprováděli v předchozích lekcích). Základní pořadí + volitelné kroky:
```bash
cd data/scripts
uv run configure_postgresql.py      # (jednorázově) rozšíření/ tabulky pokud ještě nejsou

# Scripts to prepare all data - you can skip if you plan to reuse my previous run
uv run gen_basic_data.py            # základní produkty (JSON / Parquet)
uv run gen_qna.py                   # (volitelné) generace QnA páru dotaz/odpověď
uv run gen_graph_taxonomy.py        # (volitelné) generace taxonomy konceptů (kategorie/kuchyně)

# Script to "index" data with embeddings - you can skip if you plan to reuse my previous run
uv run embeddings_products.py       	# embeddings pro detailní produkty (a is_vip označení)
uv run embeddings_simple_products.py  	# (volitelné) embeddings pro zjednodušené produkty
uv run embeddings_qna.py            	# (volitelné) embeddings pro QnA

# Import to Postgres / pgvector:
uv run import_products.py
uv run import_simple_products.py  
uv run import_stock.py
uv run import_qna.py   
uv run import_concept_embeddings.py   

# Knowledge Graph (AGE):
uv run import_graph_age.py --reset  # producenti, alergeny, certifikace (a produkty)
uv run import_taxonomy_age.py       # taxonomy koncepty (pokud jste dříve spustili gen_graph_taxonomy)
```

3. Vytvoření Keycloak uživatelů:
```bash
cd identity
uv run provision_keycloak.py
```

4. Spusťte agenta s autentizací, agentic search a grafovými nástroji (příklad .env hodnot):
```env
AUTH_ENABLED=true
ENABLE_RAG=false
AGENTIC_SEARCH_ENABLED=true
GRAPH_SEARCH_ENABLED=true
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
AGE_GRAPH_NAME=dreamfarm
```

```bash
cd agents/dreamfarm-agent
uv sync
uv run dreamfarm-agent
```

5. Frontend:
```bash
cd frontend
npm install
npm run dev
```

6. Otevřete `http://localhost:3000`, přihlaste se:
	- Běžný uživatel: `user1 / user1123`
	- VIP uživatel: `vipuser / vipuser123`

7. Položte dotaz typu: „Ukaž mi nějaké prémiové nebo exkluzivní produkty".
	- Jako VIP uvidíte i položky se `is_vip = true`.
	- Jako běžný uživatel se VIP produkty ve výsledcích vůbec neobjeví.
  
8. Zapněte/porovnejte i klasický jednoduchý RAG (`ENABLE_RAG=true`, `AGENTIC_SEARCH_ENABLED=false`) pro rozdíl: klasický RAG (bez fencing) vs. agentic search (s fencing).
   
9.  (Volitelně) Otestujte grafové nástroje dotazy uvedené níže.

## Ukázkové prompt scénáře

Níže jsou konkrétní formulace (CZ/EN mix), které typicky aktivují správné nástroje. LLM se může rozhodnout pro vícekrokový sled volání.

| Cíl | Příklad promptu | Očekávané nástroje | Poznámky |
|-----|-----------------|--------------------|----------|
| Semantic search | "Hledám něco na snídani co je zdravé a energetické" nebo "Potřebuji ingredience pro středomořskou večeři" | semantic tool | Model vytvoří HyDE dokument a vyhledá podobné produkty podle významu |
| Keyword | "Najdi produkty obsahující výraz 'organic raw honey'" | keyword tool | Pokud se model rozhodne, použije keyword před semantic |
| Široký záběr - BFS taxonomy | "Hledám nějaké čerstvé italské mléčné výrobky bez arašídů" | `graph_bfs_taxonomy_search` | BFS vybere koncepty (např. italská kuchyně, mléčné, alergen peanut) a vrátí mix produktů |
| Porovnání strategií | "Nejdřív mi dej široký přehled italských sýrů a pak detailněji podobné k tomu prvnímu" | BFS → DFS | Dva kroky; model by měl zavolat BFS a následně DFS s `product_id` prvního výsledku |
| Konkrétní produkt → podobné | "Najdi podobné produkty k produktu <UUID>" nebo "Co je podobné výrobku s ID <UUID>?" | `graph_dfs_similarity_search` | Nejprve zjistěte UUID (např. semantic search), pak DFS |
| VIP ověření | (Přihlášen VIP) "Ukaž mi exkluzivní nebo prémiové produkty" | semantic / BFS + VIP výsledky | Běžný uživatel VIP produkty neuvidí |
| Kombinace | "Porovnej dostupné bio medy a podobné produkty jako první med" | semantic / keyword → DFS | Kombinace vyhledání + grafová podobnost |

## Jak „nakopnout" BFS když model váhá
Modelu můžete explicitně naznačit šíři dotazu:
- "Dej mi hrubý přehled ..."
- "Nejdřív prozkoumej taxonomy a pak ..."
- "Zkus najít produkty napříč kategoriemi a kuchyněmi ..."

## Jak interpretovat výsledky
* `similarity_score` u DFS: normalizace kombinovaného trait skóre (0..1).
* `similarity_score` u BFS: normalizace váženého součtu vybraných taxonomy konceptů (0..1).
* VIP fencing: jestliže jste přihlášeni jako ne‑VIP, výsledky prostě chybí (žádné maskování hodnot uvnitř záznamu).

## Doporučený demonstrační flow (5-7 minut)
1. Přihlásit se jako běžný uživatel a položit BFS prompt (široký dotaz) - ukázat ne‑VIP výsledky.
2. Přihlásit se jako VIP a zopakovat - ukázat, že nyní přibyly prémiové položky.
3. Vzít první produkt z BFS výsledků → požádat: "Najdi podobné k tomuto produktu" (DFS).
4. Ukázat multi‑step: "Nejdřív zjisti širokou nabídku italských sýrů a potom podobné k prvnímu".
5. Porovnat s jednoduchým RAG (vypnout agentic & graph, zapnout RAG) - menší flexibilita.

## Bezpečnost a omezení
Aktuálně je fencing aplikační (na úrovni nástrojových odpovědí). Budoucí krok by mohl být posun logiky filtrace níže (row‑level policy na DB) nebo doplnění kategorie/kuchyní automatické klasifikace.

## Ověření VIP Fencingu v databázi
V databázi si náhodně vyberte produkt s `is_vip = true` a zkuste jej najít jako oba uživatelé - jen VIP by měl produkt „vidět" ve výsledcích (výpis z agentic tool call meta eventů nebo v odpovědi).

## Shrnutí
Máme funkční agentic tool‑based search se striktním filtrováním citlivých (VIP) produktů a základ znalostního grafu. To vytváří základ pro hlubší semantické i strukturální dotazování v dalších lekcích.


# Úkol (student branch)
- Ve student branch není implmentován semantic search ve formě nástroje a použitím HyDE (Hypothetical Document Embedding). Přidejte tento nástroj a otestujte, zjistěte jak funguje.
- Knowledge Graph nástroje ve studentském branch implementovány, ale v systém promptu chybí jejich popis a pár pokynů jak je může agent efektivně využívat, takže výsledky nejsou ideální. Vylepšete prompt.
- VIP fencing je ve studentském branch implementován na graph a semantic nástrojích, ale ne u keyword search. Ověřte, že aktuálně vám agent vrátí VIP produkt i pod normálním uživatelem, pokud se zeptáte tak, že se aktivuje keyword search. Opravte to.
  
## GitHub Copilot - příklady promptů pro začátek

Níže jsou příklady kvalitních promptů pro GitHub Copilot. Copilot funguje nejlépe s kontextem - vysvětlete mu co chcete dosáhnout, jaké technologie používáte a jaké jsou kroky k řešení.

### Úkol 1: Implementace semantic search s HyDE

```
I need to implement semantic_product_search tool in the DreamFarm agent application. This is a RAG (Retrieval Augmented Generation) system using:
- FastAPI backend with OpenAI Responses API (function calling)
- PostgreSQL with pgvector extension for vector similarity search
- OpenAI embeddings (text-embedding-3-large, 2000 dimensions)

Current state:
- File: agents/dreamfarm-agent/src/services/agentic_search.py
- The semantic_search() method is stubbed out and returns empty list
- The _embed() helper method already exists and works
- The keyword_search() method shows the pattern (uses SQL with pgvector)

Requirements:
1. Implement HyDE (Hypothetical Document Embedding) technique:
   - Take the user's text query and generate embedding using self._embed(text_value)
   - Use pgvector cosine similarity operator <=> for distance calculation
   - Convert distance to similarity score: 1 - (embedding <=> query_vector)

2. Query structure:
   - Table: products (columns: product_id, producer_name, product_name, product_description, embedding, is_vip)
   - Return top k results ordered by similarity
   - Include VIP fencing: WHERE (is_vip = false OR :user_is_vip = true)

3. Also need to register the tool in openai_service.py:
   - Add tool schema in get_tools() method (around line 193)
   - Tool name: "semantic_product_search"
   - Parameters: text (string, required), k (integer, 3-10, optional)
   - Update execution logic in both openai_service.py and main.py

Please show me the complete implementation with proper error handling and logging.
```

### Úkol 2: Vylepšení system promptu pro graph tools

```
I need to improve the system prompt guidance for knowledge graph search tools in a DreamFarm AI assistant. The application uses:
- Apache AGE (graph database extension for PostgreSQL)
- OpenAI function calling
- Two graph tools: graph_dfs_similarity_search and graph_bfs_taxonomy_search

Current state:
- File: agents/dreamfarm-agent/src/templates/system_prompt.j2
- Minimal guidance exists (line ~40-50): just mentions tools are available
- The LLM doesn't know when to use DFS vs BFS effectively

Tool capabilities:
1. graph_dfs_similarity_search:
   - Takes product_id (UUID) and k (number of results)
   - Finds similar products by traversing graph relationships
   - Best for: "find similar to this product", "alternatives to product X", "more like this"
   - Requires: a specific product must already be identified

2. graph_bfs_taxonomy_search:
   - Takes query (natural language) and k (number of results)
   - Embeds query, selects relevant taxonomy concepts (categories, cuisines, certifications, allergens)
   - Expands to products connected to those concepts
   - Best for: broad exploratory queries, "Italian dairy products", "organic breakfast items"

Requirements:
Add clear tactical guidance to the system prompt that explains:
- When to use DFS (after identifying specific product, for similarity/alternatives)
- When to use BFS (for broad/ambiguous queries, category exploration)
- That DFS needs concrete product_id from previous search results (not guessed)
- How to choose appropriate k value (3-10 range)
- How these tools complement semantic/keyword search

Keep the guidance concise but actionable. The LLM should clearly understand the decision tree.
```

### Úkol 3: Oprava VIP fencing v keyword search

```
I need to fix a security issue (VIP fencing) in the keyword search functionality of a DreamFarm marketplace application.

Context:
- Application has VIP and non-VIP users (stored in JWT, extracted as user_is_vip boolean)
- Some products have is_vip=true flag (premium products)
- Non-VIP users should NEVER see VIP products in search results
- VIP users should see all products

Current problem:
- File: agents/dreamfarm-agent/src/services/agentic_search.py, keyword_search() method
- The SQL query does NOT filter VIP products - security gap!
- Semantic search and graph tools already have proper fencing implemented

The keyword_search method:
- Uses PostgreSQL full-text search with ts_rank()
- Takes keywords array, k (limit), and user_is_vip flag
- Currently queries: WHERE fts_document @@ to_tsquery('english', :q)
- Missing: VIP filtering in WHERE clause

Required fix:
Add the VIP fencing condition to the SQL WHERE clause:
- Should include: AND (is_vip = false OR :user_is_vip = true)
- Must pass user_is_vip as a bind parameter
- This ensures non-VIP users only see non-VIP products

Reference implementations (already correct):
- semantic_search() method in same file has: WHERE (is_vip = false OR :user_is_vip = true)
- graph_search_service.py methods also implement this pattern

Please show me the corrected keyword_search SQL query with proper VIP fencing.
```

## Další možné rozšíření (dobrovolně)
- Rozšiřte LLM-based přípravu grafu o nové agregace, například sumář producenta (agregáty typu počty registrovaných produktů, procento co má skladem, pro které kuchyně má typicky suroviny, hlavní zaměření producenta podle jeho produktů), připravená data zaneste do grafové databáze a nabídněte jako nástroj

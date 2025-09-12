

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
7. Přidány dva grafové nástroje (feature flag `GRAPH_SEARCH_ENABLED`):
	- `graph_dfs_similarity_search` – „DFS“ (podobnostní rozšíření od konkrétního produktu podle sdílených kategorií/kuchyní/certifikací/alergenů + producent bonus).
	- `graph_bfs_taxonomy_search` – „BFS / taxonomy expansion“ (široký dotaz → embedding → výběr relevantních pojmů taxonomy → produkty napojené na jakýkoli z nich, skórování váženým součtem).
8. VIP fencing aplikován i v grafových nástrojích (model nikdy nedostane VIP produkt, pokud uživatel není VIP).
9. System prompt nyní explicitně popisuje dostupné grafové nástroje a kdy je použít.

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
2. Inicializujte data (pokud jste ještě neprováděli v předchozích lekcích). Základní pořadí + volitelné kroky:
```pwsh
cd data/scripts
uv sync
uv run configure_postgresql.py      # (jednorázově) rozšíření/ tabulky pokud ještě nejsou
uv run gen_basic_data.py            # základní produkty (JSON / Parquet)
uv run gen_qna.py                   # (volitelné) generace QnA páru dotaz/odpověď
uv run gen_graph_taxonomy.py        # (volitelné) generace taxonomy konceptů (kategorie/kuchyně)

# Embeddings (vyžadují OPENAI_API_KEY):
uv run embeddings_products.py       	# embeddings pro detailní produkty (a is_vip označení)
uv run embeddings_simple_products.py  	# (volitelné) embeddings pro zjednodušené produkty
uv run embeddings_qna.py            	# (volitelné) embeddings pro QnA

# Importy do Postgres / pgvector:
uv run import_products.py
uv run import_simple_products.py  
uv run import_stock.py
uv run import_qna.py      

# Knowledge Graph (AGE):
uv run import_graph_age.py --reset  # producenti, alergeny, certifikace (a produkty)
uv run import_taxonomy_age.py       # taxonomy koncepty (pokud jste dříve spustili gen_graph_taxonomy)
```
3. (Volitelně) vytvoření Keycloak uživatelů – pokud máte připravený skript (např. `provision_keycloak.py` v `identity/`):
```pwsh
cd identity
uv sync
uv run provision_keycloak.py
```
4. Spusťte agenta s autentizací, agentic search a grafovými nástroji (příklad .env hodnot):
```env
REQUIRE_AUTH=true
ENABLE_RAG=false
ENABLE_AGENTIC_SEARCH=true
GRAPH_SEARCH_ENABLED=true
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
AGE_GRAPH_NAME=dreamfarm
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
9. (Volitelně) Otestujte grafové nástroje dotazy uvedené níže.

### Ukázkové prompt scénáře

Níže jsou konkrétní formulace (CZ/EN mix), které typicky aktivují správné nástroje. LLM se může rozhodnout pro vícekrokový sled volání.

| Cíl | Příklad promptu | Očekávané nástroje | Poznámky |
|-----|-----------------|--------------------|----------|
| Široký záměr – BFS taxonomy | "Hledám nějaké čerstvé italské mléčné výrobky bez arašídů" | `graph_bfs_taxonomy_search` | BFS vybere koncepty (např. italská kuchyně, mléčné, alergen peanut) a vrátí mix produktů |
| Konkrétní produkt → podobné | "Najdi podobné produkty k produktu <UUID>" nebo "Co je podobné výrobku s ID <UUID>?" | `graph_dfs_similarity_search` | Nejprve zjistěte UUID (např. semantic search), pak DFS |
| Porovnání strategií | "Nejdřív mi dej široký přehled italských sýrů a pak detailněji podobné k tomu prvnímu" | BFS → DFS | Dva kroky; model by měl zavolat BFS a následně DFS s `product_id` prvního výsledku |
| VIP ověření | (Přihlášen VIP) "Ukaž mi exkluzivní nebo prémiové produkty" | semantic / BFS + VIP výsledky | Běžný uživatel VIP produkty neuvidí |
| Fallback na keyword | "Najdi produkty obsahující výraz 'organic raw honey'" | keyword tool | Pokud se model rozhodne, použije keyword před semantic |
| Kombinace | "Porovnej dostupné bio medy a podobné produkty jako první med" | semantic / keyword → DFS | Kombinace vyhledání + grafová podobnost |

### Jak „nakopnout“ BFS když model váhá
Modelu můžete explicitně naznačit šíři dotazu:
- "Dej mi hrubý přehled ..."
- "Nejdřív prozkoumej taxonomy a pak ..."
- "Zkus najít produkty napříč kategoriemi a kuchyněmi ..."

### Jak interpretovat výsledky
* `similarity_score` u DFS: normalizace kombinovaného trait skóre (0..1).
* `similarity_score` u BFS: normalizace váženého součtu vybraných taxonomy konceptů (0..1).
* VIP fencing: jestliže jste přihlášeni jako ne‑VIP, výsledky prostě chybí (žádné maskování hodnot uvnitř záznamu).

### Doporučený demonstrační flow (5–7 minut)
1. Přihlásit se jako běžný uživatel a položit BFS prompt (široký dotaz) – ukázat ne‑VIP výsledky.
2. Přihlásit se jako VIP a zopakovat – ukázat, že nyní přibyly prémiové položky.
3. Vzít první produkt z BFS výsledků → požádat: "Najdi podobné k tomuto produktu" (DFS).
4. Ukázat multi‑step: "Nejdřív zjisti širokou nabídku italských sýrů a potom podobné k prvnímu".
5. Porovnat s jednoduchým RAG (vypnout agentic & graph, zapnout RAG) – menší flexibilita.
6. Krátce zobrazit `CommonErrors.md` sekci o Cypher jako ukázku lessons‑learned dokumentace.

### Bezpečnost a omezení
Aktuálně je fencing aplikační (na úrovni nástrojových odpovědí). Budoucí krok by mohl být posun logiky filtrace níže (row‑level policy na DB) nebo doplnění kategorie/kuchyní automatické klasifikace.

### Ověření VIP Fencingu v databázi
V databázi si náhodně vyberte produkt s `is_vip = true` a zkuste jej najít jako oba uživatelé – jen VIP by měl produkt „vidět“ ve výsledcích (výpis z agentic tool call meta eventů nebo v odpovědi).

### Shrnutí
Máme funkční agentic tool‑based search se striktním filtrováním citlivých (VIP) produktů a základ znalostního grafu. To vytváří základ pro hlubší semantické i strukturální dotazování v dalších lekcích.

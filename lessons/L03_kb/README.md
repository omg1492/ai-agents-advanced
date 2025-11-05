## Lekce 03 - Znalostní báze z dokumentů, obrázků a videí, hybridní vyhledávání & semantický cache

V této lekci stavíme na předchozích základech (RAG + nástroje) a rozšiřujeme systém o ingest heterogenních zdrojů (PDF, obrázky, video/audio) do jednotné znalostní báze, hybridní (semantic + full‑text) vyhledávání s Reciprocal Rank Fusion a semantický cache pro bleskové odpovědi na nejběžnější úvodní otázky.

**Byznys motivace:** Farmáři často dodají pouze PDF katalog, produktové fotky nebo promo / recenzní video. Tyto zdroje je potřeba převést do textové podoby, obohatit o stručná metadata (název, krátký popis) a umožnit jak sémantické, tak klíčové (exact / keyword) vyhledávání. U opakujících se obecných dotazů chceme snížit latenci i náklady.

**Koncepty:**
- Multimodální ingest (PDF → Markdown, Image → vision extrakce, Video → sampling + Whisper transcript)
- Hybridní vyhledávání (semantic vector search + full‑text search + RRF fusion)
- LLM řízená extrakce klíčových slov (structured output)
- Semantický cache (first‑turn, high‑similarity match)

**Technologie:**
- MarkItDown (PDF → Markdown)
- OpenAI / Azure OpenAI (vision + extrakce strukturovaných výstupů)
- faster-whisper (lokální transkripce audia z videa)
- PostgreSQL + pgvector + full‑text (GIN, to_tsquery, unaccent)
- Reciprocal Rank Fusion (kombinace různých rankingů)

---
### Novinky oproti lekci 02
1. Skripty pro zpracování multimédií v `data/scripts/`:
	- `process_pdfs.py` - PDF → Markdown (MarkItDown) → LLM structured parse (`ProductSummary`)
	- `process_images.py` - obrázek (base64) → vision prompt → structured `ImageProductSummary`
	- `process_videos.py` - sampling 3 rámců + (volitelně) extrakce audia přes ffmpeg + lokální Whisper → vision + text prompt → `VideoProductSummary`
2. Schéma / tabulky rozšířené o full‑text (`fts_combined`) a HNSW index pro vektorové dotazy.
3. Hybridní RAG pipeline: 
	- Semantic pass (embedding dotazu)
	- LLM extrakce klíčových slov → FTS (to_tsquery)
	- Reciprocal Rank Fusion (RRF) pro sjednocení pořadí
4. Semantický cache pro první zprávu (tabulka `semantic_cache`) - top 1 nejpodobnější otázka nad uloženými embeddingy, pokud překročí práh podobnosti → okamžitá odpověď bez volání modelu.

---
### Architektura (rozšíření)
```
User → Frontend → Agent (FastAPI)
								 │
								 ├─ Semantic Cache (first turn)
								 ├─ Hybrid RAG Service
								 │    ├─ Vector (pgvector)
								 │    ├─ FTS (GIN over fts_combined)
								 │    └─ RRF Fusion
								 └─ OpenAI (embeddings, keyword extraction, vision)

Data Pipeline Scripts → (PDF / Image / Video -> summaries + text) → Ingest → PostgreSQL
```

---
### Hybridní vyhledávání - detail
1. Vypočti embedding dotazu → top N kandidátů (cosine) z `simple_products.embedding`.
2. LLM (Responses / Chat beta parse) extrahuje normalizovaná klíčová slova (structured schema).
3. Full‑text dotaz: `fts_combined @@ to_tsquery('simple', <OR-joined keywords>)` + `ts_rank`.
4. RRF (k=60): pro každý výsledek se sečtou příspěvky `1/(k + rank_list_i)` a výsledky se znovu seřadí.
5. Fused top K se vloží do system promptu jako blok relevantních produktů.

Failovery:
- Pokud extrakce klíčových slov selže nebo vrátí prázdný seznam → použije se pouze semantic.
- Pokud FTS vrátí 0 výsledků → použije se jen semantic výsledek.

Logging (INFO) ukazuje počty a zdroje (semantic_count, fts_count, fused_count) pro ladění relevance.

---
### Semantický cache (rychlá první odpověď)
Používá se pouze pro úplně první uživatelskou zprávu v konverzaci, aby nemátl kontext.

Mechanismus:
1. Embed první zprávu.
2. Dotaz na `semantic_cache` (pgvector) - kosinová podobnost (HNSW index).
3. Pokud max podobnost ≥ `SEMANTIC_CACHE_SIMILARITY_THRESHOLD` (výchozí 0.93) → vrátí se uložená odpověď, žádné volání LLM.
4. Miss → pokračuje standardní pipeline (cache se neaplikuje na další zprávy).

Cache obsahuje pouze bezpečné, obecné Q&A bez specifických produktů (rychlost + nákladové úspory, žádné riziko zastarání).

# Ukázka (teacher branch)

## Rychlé spuštění (navazuje na předchozí lekce)
1. Spusťte infrastrukturu (PostgreSQL) + API (pokud ještě neběží):
```pwsh
cd deploy/local
docker compose up -d postgres api-stock
```
2. Nakonfigurujte PostgreSQL (pgvector extension + schéma):
```pwsh
cd data/scripts
uv sync
uv run configure_postgresql.py
```
3. Naimportujte základní data do databáze:
```pwsh
# Import produktů s embeddingy
uv run import_simple_products.py

# Import stock dat
uv run import_stock.py

# Import Q&A semantic cache
uv run import_qna.py
```
4. (Volitelně) zpracujte multimediální soubory (použijte reálné produkty z `data/`):
```pwsh
uv run process_pdfs.py
uv run process_images.py
uv run process_videos.py
```
5. Spusťte agenta (s aktivovaným RAG a cache):
```pwsh
cd agents/dreamfarm-agent
uv sync
uv run dreamfarm-agent
```
6. Frontend:
```pwsh
cd frontend
npm install
npm run dev
```
7. Otevřete `http://localhost:3000` a zkuste dotazy.

---
## .env (nové / relevantní proměnné)
```env
# RAG
ENABLE_RAG=true
RAG_MAX_RESULTS=5
RAG_SIMILARITY_THRESHOLD=0.7

# Semantický cache
SEMANTIC_CACHE_ENABLED=true
SEMANTIC_CACHE_SIMILARITY_THRESHOLD=0.93
SEMANTIC_CACHE_EMBEDDING_MODEL=text-embedding-3-large  # (pokud chcete jiný než hlavní)

# OpenAI / Azure OpenAI (viz předchozí lekce)
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```

## Jak skripty fungují
| Skript | Vstup | Kroky | Model výstup (Pydantic) |
|--------|-------|-------|-------------------------|
| `process_pdfs.py` | `data/PDFs/*.pdf` | PDF → Markdown (MarkItDown) → LLM structured parse | `ProductSummary` |
| `process_images.py` | `data/images/*.(jpg/png/webp/gif)` | Base64 → vision + structured parse | `ImageProductSummary` |
| `process_videos.py` | `data/videos/*.(mp4/mov/mkv/webm)` | Frame sampling (OpenCV) + (Whisper transcript) → vision + structured parse | `VideoProductSummary` |

Výstup skriptů se tiskne do konzole; můžete jej zachytit, parsovat a ukládat.

# Úkol (student branch)
- Ve vašem branch je vyřešené procesování videa a obrázky, ale chybí **řešení pro PDF** - vytvořte.
- Ve vašem branch je implementovaný full-text search, ale ne semantický - **dodělejte semantic search** a následně vytvořte metodu spojední obou výsledků do jediného s **Reciprocal Rank Fusion**.
- Ve vašem branch chybí **semantická cache**, impementujte ji.

## GitHub Copilot - Nápovědy pro implementaci

Níže naleznete strategické prompty pro GitHub Copilot, které vám pomohou implementovat jednotlivé úkoly. Prompty jsou záměrně koncepční - GitHub Copilot potřebuje kontext a cíl, ne přesné instrukce. Copilot prompty jsou v angličtině pro lepší výsledky.

### Úkol 1: PDF Processing Script

**Cíl:** Vytvořit skript pro zpracování PDF souborů podobně jako už fungující skripty pro obrázky a videa.

**GitHub Copilot Prompt:**
```
I need to complete the process_pdfs.py script to extract product information from PDF files. 
The script should follow the same pattern as process_images.py and process_videos.py:

1. Load configuration and initialize OpenAI client (unified for both OpenAI and Azure OpenAI)
2. Use the markitdown library to convert PDFs to Markdown format
3. Send the markdown to OpenAI API using structured output (Pydantic model ProductSummary) 
   to extract product name and description
4. Print results in formatted blocks for each file
5. Generate a consolidated summary at the end

The script needs to handle:
- Environment variables for API configuration (OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, etc.)
- PDF directory path from environment or default location
- Error handling per file (continue processing if one fails)
- Full markdown text should be sent to the model (no truncation)

Look at the existing process_images.py implementation for the exact patterns to follow.
Generate the complete implementation for all TODO functions.
```

---

### Úkol 2: Semantic Search Implementation

**Cíl:** Přidat vektorové vyhledávání pomocí embeddings a pgvector do RAG service.

**GitHub Copilot Prompt:**
```
I need to implement semantic/vector search in the RAG service to complement the existing 
full-text search. The implementation requires:

1. Embedding generation - convert user queries to vector embeddings using OpenAI embeddings API
   - Use the configured embedding model with 2000 dimensions
   - Return the embedding vector for similarity search

2. Vector similarity search - query PostgreSQL with pgvector extension
   - Use cosine distance operator (<=> in PostgreSQL) to find similar products
   - Filter by similarity threshold and return top results
   - The simple_products table has an 'embedding' column (vector type)

3. Orchestration - connect the embedding generation with vector search
   - Generate embedding for user query
   - Execute vector search with the embedding
   - Return ranked results based on similarity

The existing code has the database connection and OpenAI client already set up.
Look for TODO comments in the RAGService class to find where to implement these features.
Focus on the three key methods that enable semantic search functionality.
```

---

### Úkol 3: Reciprocal Rank Fusion

**Cíl:** Sloučit výsledky ze sémantického a full-text vyhledávání do jednoho rankingu.

**GitHub Copilot Prompt:**
```
I need to implement Reciprocal Rank Fusion (RRF) to combine results from semantic search 
and full-text search into a single ranked list.

RRF algorithm concept:
- Take multiple ranked lists (semantic results and FTS results)
- For each item, calculate a fused score by summing 1/(k + rank) across all lists where it appears
- Rank is 1-based position in each list, k is a constant (typically 60)
- Items appearing in multiple lists get higher scores
- Sort by fused score and return top N results

Implementation requirements:
- Accept multiple result lists as input
- Use product_id as the unique key to identify same items across lists
- Preserve the SearchResult object structure but update similarity_score with fused score
- Handle cases where items appear in one list but not others

After implementing RRF, update the hybrid search method to:
- Run both semantic search and FTS in parallel
- Apply RRF fusion if both return results
- Fall back to single-source results if only one succeeds
- Log counts for debugging (semantic count, FTS count, fused count)

The existing full-text search and keyword extraction already work - just connect the pieces.
```

---

### Úkol 4: Semantic Cache Service

**Cíl:** Implementovat cache pro okamžité odpovědi na často kladené úvodní otázky.

**GitHub Copilot Prompt:**
```
I need to implement a semantic cache service for instant responses on first-turn user messages.

Architecture concept:
- PostgreSQL table 'semantic_cache' stores: question text, answer text, and embedding vector
- Only first message in a conversation is eligible for cache lookup
- High similarity threshold (≥0.93) ensures precise matches
- If cache hit: return cached answer immediately, skip LLM call
- If cache miss: proceed with normal RAG + LLM flow

Implementation components needed:
1. Service initialization
   - Load configuration for cache enable/disable and similarity threshold
   - Set up database connection (PostgreSQL with pgvector)
   - Set up OpenAI client for generating query embeddings

2. Embedding generation
   - Same pattern as RAG service
   - Convert user question to vector for similarity search

3. Cache lookup
   - Generate embedding for incoming question
   - Query semantic_cache table using pgvector similarity
   - Return cached answer if similarity above threshold
   - Return None for cache miss

4. Integration into main API endpoints
   - Check cache before LLM call (only on first turn)
   - Return cached response if hit
   - The TODO comments in main.py show where to integrate

The cache table schema is already created by migration scripts.
Follow the same patterns as RAGService for database and OpenAI client setup.
The SemanticCacheHit class is already defined for returning results.
```

---

## Postup řešení

**Doporučené pořadí implementace:**

1. **PDF Processing** (nejjednodušší) - máte kompletní vzor v process_images.py
2. **Semantic Search** (střední obtížnost) - rozšíření existující RAG service
3. **RRF Fusion** (algoritmus) - čistá logika pro sloučení výsledků
4. **Semantic Cache** (komplexní) - samostatná service + integrace do API

**Tipy pro práci s GitHub Copilot:**
- Otevřete referenční soubory (process_images.py, process_videos.py) jako kontext
- Používejte Copilot Chat pro vysvětlení konceptů (pgvector, RRF algoritmus)
- Nechte Copilot vygenerovat kostru, pak ji upravte podle potřeby
- Testujte průběžně po každém kroku

**Testování:**
- PDF: `uv run process_pdfs.py` (po implementaci)
- Semantic Search: Nastavte `ENABLE_RAG=true` a testujte dotazy v agentovi
- RRF: Porovnejte relevanci výsledků s pouze FTS
- Cache: Nastavte `SEMANTIC_CACHE_ENABLED=true` a testujte první zprávy

## Další možné rozšíření (dobrovolně)
- Dotáhnout datovou pipeline do automatického importu do databáze
- Místo RRF použít semantic reranking



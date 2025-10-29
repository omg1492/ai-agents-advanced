## Lekce 03 – Znalostní báze z dokumentů, obrázků a videí, hybridní vyhledávání & semantický cache

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
	- `process_pdfs.py` – PDF → Markdown (MarkItDown) → LLM structured parse (`ProductSummary`)
	- `process_images.py` – obrázek (base64) → vision prompt → structured `ImageProductSummary`
	- `process_videos.py` – sampling 3 rámců + (volitelně) extrakce audia přes ffmpeg + lokální Whisper → vision + text prompt → `VideoProductSummary`
2. Schéma / tabulky rozšířené o full‑text (`fts_combined`) a HNSW index pro vektorové dotazy.
3. Hybridní RAG pipeline: 
	- Semantic pass (embedding dotazu)
	- LLM extrakce klíčových slov → FTS (to_tsquery)
	- Reciprocal Rank Fusion (RRF) pro sjednocení pořadí
4. Semantický cache pro první zprávu (tabulka `semantic_cache`) – top 1 nejpodobnější otázka nad uloženými embeddingy, pokud překročí práh podobnosti → okamžitá odpověď bez volání modelu.

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
### Hybridní vyhledávání – detail
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
2. Dotaz na `semantic_cache` (pgvector) – kosinová podobnost (HNSW index).
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
2. (Volitelně) zpracujte multimediální soubory (použijte reálné produkty z `data/`):
```pwsh
cd data/scripts
uv sync
uv run process_pdfs.py
uv run process_images.py
uv run process_videos.py
```
3. Naimportujte/aktualizujte výsledné texty / metadata do databáze (připravte vlastní ingest SQL / skript – analogie k jednoduchým produktům z L01).
4. Spusťte agenta (s aktivovaným RAG a cache):
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
6. Otevřete `http://localhost:3000` a zkuste dotazy.

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

## Další možné rozšíření (dobrovolně)
- Dotáhnout datovou pipeline do automatického importu do databáze
- Místo RRF použít semantic reranking



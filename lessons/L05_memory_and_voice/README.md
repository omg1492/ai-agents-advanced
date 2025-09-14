## Lekce 05 – Konverzační Paměť (Summaries) & Základ pro Voice

V této lekci přidáváme první stavební kameny uživatelské paměti: ukládání syrových (raw) konverzací, jejich dávkové sumarizace do vektorového prostoru a přípravu na budoucí personalizaci (user profile enrichment) a hlasový mód. Hlas ještě není implementován – definujeme však architekturu a datové body, aby pozdější přidání (streaming audio → text → paměť) bylo plynulé.

### Byznys motivace
1. Personalizace: Schopnost připomenout si uživatelské preference (alergie, dietní omezení, oblíbené produkty) z předchozích sezení.
2. Kontextová efektivita: Místo posílání celých dlouhých transcriptů do promptu – krátká shrnutí (summaries) snižují náklady a latenci.
3. Audit & Soukromí: Surová data lze po čase bezpečně mazat, zatímco agregovaná shrnutí zůstávají (data minimization).
4. Budoucí hlas: Stejný paměťový backend bude použit i pro voice režim (hands‑free scénáře na farmě nebo v kuchyni).

### Novinky oproti lekci 04
1. Tabulka `conversations_raw` – ukládá celé průběhy konverzací (JSON pole objektů `{role, content}`) + stav sumarizace (`summary_status`).
2. Zjednodušené message schema: odstraněny `created_at` & `mode` per‑message (redundantní / nevyužité) – pořadí je dáno indexem v poli.
3. Tabulka `conversation_summaries` – jedna agregovaná řádka na (user_id, thread_id) s vektorem (pgvector 2000d) pro budoucí semantické vyhledávání paměti.
4. Skript `gen_conversations.py` – generuje deterministický demo dataset (TRUNCATE + vložení 5+ scénářů) pro test paměťového pipeline.
5. Skript `process_conversations.py` – batch summarizer: přečte pending transcripts → pošle syrové JSON zprávy modelu → uloží shrnutí + embedding → označí jako done.
6. Vylepšený systémový prompt summarizátoru (max 250 slov, strukturované pokyny na zachycení intentů, preferencí, rozhodnutí, unresolved otázek; čistý výstup bez metadat).
7. Implementační logika v agentovi: při každé zprávě se upsertuje aktuální stav do `conversations_raw` (best‑effort; chyba neblokuje odpověď).
8. Design příznaků pro budoucí funkce (memory search tool, user profile enrichment, voice streaming) – ještě neaktivní.

### Co ještě bude následovat (plán)
- `memory_search` nástroj: vektorová podobnost nad `conversation_summaries` filtrovaná podle `user_id`.
- `user_profiles` tabulka: konsolidace preferencí extrahovaných ze shrnutí (dietní typ, alergeny, styl vaření, tón odpovědí...).
- Enrichment pipeline: další skript, který periodicky (nebo při změnách) extrahuje preference ze shrnutí a aktualizuje profil.
- Voice mód: websocket / streaming, transkripce → stejné ukládání zpráv, volitelná komprese ticha a krátkých potvrzení.

### Koncepty v praxi
- Data minimization: syrové zprávy lze po expirační lhůtě smazat (`expires_at`), shrnutí zůstává.
- Neutral Summaries: žádné halucinace / extrapolace – jen explicitně uvedená fakta a preference.
- Deterministická seed data: TRUNCATE + generovaný set → snadné testy regresí.
- Budoucí retrieval z paměti: embedding shrnutí umožní „co už tento uživatel řešil?“ bez re‑embedování celé historie.

### Technologie
- PostgreSQL + pgvector (2000 dim).
- OpenAI / Azure OpenAI Responses API (summaries) & Embeddings API.
- Python skripty (uv / tenacity retry / dotenv).
- V budoucnu: streaming audio → speech‑to‑text → stejný summarizační loop.

### Datová schémata (zjednodušený výňatek)
`conversations_raw(thread_id TEXT UNIQUE, user_id TEXT, messages JSONB[], summary_status TEXT, updated_at TIMESTAMP, expires_at TIMESTAMP)`

`conversation_summaries(id UUID, thread_id TEXT, user_id TEXT, summary TEXT, embedding VECTOR(2000), updated_at TIMESTAMP)`

Unikátní klíč: `(user_id, thread_id)` pro idempotentní upsert shrnutí.

### .env (relevantní / plánované proměnné)
```env
MEMORY_ENABLED=true                   # (plánované zapnutí injekce paměti do promptu)
MEMORY_CONVERSATION_RETENTION_DAYS=7  # kdy lze čistit raw
MEMORY_SUMMARY_MAX_WORDS=250          # dokumentační – enforce v promptu
OPENAI_MODEL=gpt-4o-mini              # nebo gpt-5 dle prostředí
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```

### Jak vyzkoušet (rychlý start – pouze paměť / summarizace)
1. Spusťte Postgres (a agent pokud chcete generovat reálné konverzace):
```pwsh
cd deploy/local
docker compose up -d postgres
```
2. Aplikujte DDL (pokud ještě nebylo):
```pwsh
cd data/scripts
uv sync
uv run configure_postgresql.py
```
3. Vygenerujte demo konverzace (POZOR: destruktivní – TRUNCATE `conversations_raw`):
```pwsh
uv run python gen_conversations.py --user-id user1
```
4. Ověřte pending záznamy:
```sql
SELECT thread_id, jsonb_array_length(messages) AS msg_count, summary_status
FROM conversations_raw
ORDER BY updated_at ASC;
```
5. Spusťte summarizer (dry‑run nejprve):
```pwsh
uv run python process_conversations.py --limit 5 --dry-run
```
6. Proveďte ostré uložení:
```pwsh
uv run python process_conversations.py --limit 5
```
7. Zkontrolujte výsledky:
```sql
SELECT user_id, thread_id, left(summary,120) || '...' AS preview, length(summary) AS chars
FROM conversation_summaries;
```
8. (Volitelně) Znovu spusťte summarizer – mělo by být 0 pending (idempotentní chování).

### Demo flow (5 minut)
1. Spusťte generator + summarizer.
2. Ukažte obsah `conversations_raw` (syrový JSON) vs. `conversation_summaries` (kompaktní text + embedding existuje).
3. Vysvětlete, jak by následoval `memory_search`: vyhledání podobného shrnutí → injekce do system promptu.
4. Diskutujte budoucí `user_profiles` (agregace preferencí) a jak shrnutí již obsahují nutná fakta.
5. Poznámka k soukromí: po X dnech lze skrze plánovaný job smazat raw řádky s expired `expires_at`.

### Bezpečnost & Soukromí
- Shrnutí vylučují PII a nepotvrzené domněnky (vynuceno promptem).
- Oddělení raw vs. summary podporuje cílenou retenční politiku.
- Budoucí memory_search bude vždy filtr `WHERE user_id = :current_user` (SQL enforcement, ne na úrovni LLM).

### Známá omezení / TODO
- Zatím žádné automatické spouštění summarizeru (cron / background job).
- Není implementován memory_search tool ani injekce shrnutí do promptu.
- Chybí `user_profiles` + enrichment pipeline.
- Voice mód (audio ingest, VAD, adaptivní chunking) – pouze plán v architektuře.
- Není (zatím) audit trail změn shrnutí / verze.

### Možné rozšíření (další iterace)
- Extrakce strukturovaných preferencí (JSON schema) paralelně se shrnutím.
- Heuristické spojování podobných shrnutí (thread merge) při krátkých sezeních.
- Token/accounting metriky (cost observability) – ukládat do separátní tabulky.
- Evaluace kvality shrnutí (faktická přesnost, preference recall) – Langfuse / vlastni metriky.
- Voice: streaming ASR → real‑time append do `conversations_raw` → incremental summarization (sliding window).

### Shrnutí
Máme funkční základ paměťové vrstvy: syrové ukládání, deterministická demo data a dávkový summarizer produkující kompaktní vektorově vyhledatelné shrnutí. To otevírá cestu k personalizaci a hlasovým scénářům v dalších krocích.

## Lekce 05 – Konverzační Paměť (Summaries) & Základ pro Voice

V této lekci přidáváme první stavební kameny uživatelské paměti: ukládání syrových (raw) konverzací, jejich dávkové sumJak otestovat ručně (lokální běh agenta):
1. Spusťte agenta se zapnutým profilem:
	 ```env
	 USER_PROFILE_ENABLED=true
	 ```
2. Zeptejte se: „Co o mě víš?" – pokud profil neexistuje, odpověď bude prázdná sekce / žádná fakta.
3. Zadejte: „Pamatuj si prosím, že nemám rád kozí sýr a preferuji vegetariánská jídla."
4. Sledujte logy – měl by proběhnout tool call `memory_write_profile` s patch strukturou podobnou:
	 ```json
	 {"patch":{"set":{"diet":{"vegetarian":true}},"append":{"dislikes":["kozí sýr"]}}}
	 ```
5. Znovu: „Co o mě víš?" – nyní by se měl objevit update v `<user_profile_json>`.
6. Otestujte deduplikaci: „Pamatuj si, že fakt nemám rád kozí sýr." – druhé volání by nemělo duplikovat položku v poli `dislikes`.
7. Otestujte korekci: „Už vlastně jím ryby, přidej prosím že jsem pescatarián." → očekávaný PATCH `set` např. `{ "diet": { "pescatarian": true } }`.

#### Příklad: Domácí zvířata
Praktická ukázka persistence a načítání uživatelských preferencí:

**Krok 1 - Uložení informace (nový thread):**
```
User: Zapamatuj si, že máme doma kočku
Assistant: Uložím si, že máte doma kočku. [tool call: memory_write_profile]
```
Očekávaný patch:
```json
{"patch":{"set":{"household":{"pets":["cat"]}}}}
```

**Krok 2 - Ověření persistence (nový thread):**
```
User: Co máme doma za zvíře?
Assistant: Podle toho, co jsem si zaznamenal, máte doma kočku.
```
Profil se automaticky načte a injektuje do system promptu, takže model má k dispozici historickou informaci i v novém threadu.torového prostoru a přípravu na budoucí personalizaci (user profile enrichment) a hlasový mód. Hlas ještě není implementován – definujeme však architekturu a datové body, aby pozdější přidání (streaming audio → text → paměť) bylo plynulé.

### Byznys motivace
1. Personalizace: Schopnost připomenout si uživatelské preference (alergie, dietní omezení, oblíbené produkty) z předchozích sezení.
2. Kontextová efektivita: Místo posílání celých dlouhých transcriptů do promptu – krátká shrnutí (summaries) snižují náklady a latenci.
3. Audit & Soukromí: Surová data lze po čase bezpečně mazat, zatímco agregovaná shrnutí zůstávají (data minimization).
4. Budoucí hlas: Stejný paměťový backend bude použit i pro voice režim (hands‑free scénáře na farmě nebo v kuchyni).

### Novinky oproti lekci 04 (aktuální stav)
1. Tabulka `conversations_raw` – ukládá celé průběhy konverzací (JSON pole objektů `{role, content}`) + stav sumarizace (`summary_status`).
2. Zjednodušené message schema: odstraněny `created_at` & `mode` per‑message – pořadí je dáno indexem v poli.
3. Tabulka `conversation_summaries` – jedna agregovaná řádka na (user_id, thread_id) s vektorem (pgvector 2000d) pro semantické vyhledávání.
4. Skript `gen_conversations.py` – deterministické seed konverzace (TRUNCATE + vložení scénářů) pro test pipeline.
5. Skript `process_conversations.py` – batch summarizer (shrnutí + embedding + status update).
6. Vylepšený systémový prompt summarizátoru (<=250 slov, strukturované pokyny, čistý výstup bez metadat).
7. Per‑turn upsert do `conversations_raw` v agentovi (best‑effort, neblokuje odpověď).
8. Tabulka `user_profiles` – per‑user JSON profil (preferences, dietní informace, styl) s enrich merge strategií.
9. Skript `enrich_user_profiles.py` – čte shrnutí + nedávné raw zprávy, generuje/merge profil (deduplikace, konzervativní fakta).
10. Injekce uživatelského profilu do systémového promptu (sekce `<user_profile_json>` + explicitní `User ID`).
11. Nástroj `memory_search` (pokud povolen) – vektorová podobnost nad `conversation_summaries` izolovaná per uživatel.
12. Granulární feature flagy: `CONVERSATION_STORE_ENABLED`, `MEMORY_SEARCH_ENABLED`, `USER_PROFILE_ENABLED` (plus starý fallback `MEMORY_FEATURES_ENABLED`).
13. Jednotné testy pokrývající zapnutí/vypnutí jednotlivých paměťových funkcí + integraci profilu.
14. Nástroj `memory_write_profile` (pokud `USER_PROFILE_ENABLED=true`) – bezpečné PATCH aktualizace profilu (konzervativní, řízené pravidly v system promptu).

> Stav hlasu (voice): stále pouze design – žádný streaming audio → text zatím nenasazen.

### Co ještě bude následovat (plán)
- Automatické spouštění enrichmentu / summarizeru (cron / background worker)
- Periodická čistka expirovaných raw konverzací (`expires_at`)
- Rozšířená struktura profilu (např. cíle, historické změny, audit trail)
- Incremental / online summarization během delších sezení
- Voice mód: websocket audio ingest, VAD, adaptivní chunking, realtime profile enrichment
- Evaluace kvality paměti (precision/recall preferencí) a metriky nákladů
 - Audit patch operací (log revizí) pro `memory_write_profile`

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

### .env (relevantní proměnné – aktuální)
```env
# OpenAI / Azure
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Paměť – granular flags
CONVERSATION_STORE_ENABLED=true       # per-turn persist raw transcript
MEMORY_SEARCH_ENABLED=true            # registrace nástroje memory_search
USER_PROFILE_ENABLED=true             # načtení + injekce user profilu
# Legacy (fallback): MEMORY_FEATURES_ENABLED=true  # pokud nové nenastaveny

# Další (příkladové)
SEMANTIC_CACHE_ENABLED=true           # first-turn cache (nezávislé na paměti)
ENABLE_RAG=true                       # RAG kontext
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
- Chybí scheduler (automatické běhy summarizer + enrichment)
- Není ještě retenční job pro mazání expirovaných raw zpráv
- Žádný audit trail verzí user profilu
- Voice mód zatím pouze návrh
- Chybí evaluace kvality shrnutí a profilů

### Možné rozšíření (další iterace)
- Extrakce strukturovaných preferencí (JSON schema) paralelně se shrnutím.
- Heuristické spojování podobných shrnutí (thread merge) při krátkých sezeních.
- Token/accounting metriky (cost observability) – ukládat do separátní tabulky.
- Evaluace kvality shrnutí (faktická přesnost, preference recall) – Langfuse / vlastni metriky.
- Voice: streaming ASR → real‑time append do `conversations_raw` → incremental summarization (sliding window).

### Shrnutí
Máme funkční základ paměťové vrstvy: syrové ukládání, deterministická demo data a dávkový summarizer produkující kompaktní vektorově vyhledatelné shrnutí. To otevírá cestu k personalizaci a hlasovým scénářům v dalších krocích.

### Příklady dotazů pro vyvolání `memory_search`
Po vygenerování demo konverzací (`gen_conversations.py`) a spuštění summarizeru (`process_conversations.py`) může agent (pokud je `MEMORY_SEARCH_ENABLED=true`) začít volat nástroj `memory_search`, když položíte dotaz implikující odkaz na minulý kontext nebo preference. Zkuste například (formulujte 1–2 z nich do chatu):

1. „Co jsem ti dříve říkal o své stravě nebo dietě?“
2. „Pamatuješ si, jaký kozí sýr mě zajímal a jakou chuť jsem preferoval?“
3. „Jaké omezení ohledně pálivosti jsem ti sdílel?“
4. „Jaké rychlé nápady na využití rajčat a bazalky jsme už spolu řešili?“
5. „Jaké preference mám, které bys měl mít na paměti při doporučeních?“
6. „Shrň moje dosavadní preference potravin (koření, pikantnost, dietní styl).“
7. „Prosím zkontroluj, co jsem tě žádal připomenout ohledně kozího sýra.“

Další příklady pro zjištění, zda byl injektován uživatelský profil (sekce `<user_profile_json>`):

8. „Co o mě víš?“
9. „Jaké preference sis už u mě zaznamenal?“
10. „Jaké dietní informace o mně máš?“

Poznámky:
- Dotazy nemusí přesně opakovat původní formulace; stačí sémantická blízkost – embedding vyhledávání se postará o podobnost.
- Pokud se nástroj nevyvolá (model se rozhodne, že historie není nutná), zkuste explicitnější formulaci („co jsem ti říkal…“, „pamatuješ si…“).
- Výsledky memory_search se vrací jako interní tool výstup (`memories[...]`) a model z nich následně sestaví odpověď.
- Pokud jste právě resetovali databázi a ještě neběžel summarizer, nástroj vrátí prázdný seznam.

### Nástroj `memory_write_profile` – PATCH uživatelského profilu

Implementováno: Model (pokud je nástroj povolen) může jednorázově v turnu zavolat funkční nástroj `memory_write_profile` a poslat pouze PATCH objekt – nikoliv celý profil. Cílem je snížit riziko, že model přepíše profil halucinovanými daty.

Struktura patch objektu:
```json
{
	"patch": {
		"set": { "diet": { "vegetarian": true } },
		"append": { "dislikes": ["kozí sýr"] },
		"remove": ["temporary_note"]
	}
}
```
Pravidla (vynuceno v system promptu):
- Volat pouze pokud uživatel výslovně řekne „zapamatuj si…“, „pamatuj si…“, „prosím ulož…“, nebo pokud je zjevná dlouhodobá korekce („už vlastně nejím maso“ proti předchozímu stavu).
- Nepoužívat pro dočasné / kontextové údaje (aktuální nálada, ad‑hoc přání).
- `set` dělá hluboký merge – objekty se rekurzivně slučují, primitiva přepisují.
- `append` přidává unikátní primitivní hodnoty do polí (string/int/float/bool); duplikáty ignoruje.
- `remove` smaže top‑level klíče (šetřit, používat při zrušení nebo revokaci informace).
- Nikdy neposílat celý profil – pouze změny.
- V jednom model turnu maximálně jedno volání nástroje – agregovat změny.

Jak otestovat ručně (lokální běh agenta):
1. Spusťte agenta se zapnutým profilem:
	 ```env
	 USER_PROFILE_ENABLED=true
	 ```
2. Zeptejte se: „Co o mě víš?“ – pokud profil neexistuje, odpověď bude prázdná sekce / žádná fakta.
3. Zadejte: „Pamatuj si prosím, že nemám rád kozí sýr a preferuji vegetariánská jídla.“
4. Sledujte logy – měl by proběhnout tool call `memory_write_profile` s patch strukturou podobnou:
	 ```json
	 {"patch":{"set":{"diet":{"vegetarian":true}},"append":{"dislikes":["kozí sýr"]}}}
	 ```
5. Znovu: „Co o mě víš?“ – nyní by se měl objevit update v `<user_profile_json>`.
6. Otestujte deduplikaci: „Pamatuj si, že fakt nemám rád kozí sýr.“ – druhé volání by nemělo duplikovat položku v poli `dislikes`.
7. Otestujte korekci: „Už vlastně jím ryby, přidej prosím že jsem pescatarián.“ → očekávaný PATCH `set` např. `{ "diet": { "pescatarian": true } }`.

Poznámka k DB: profil se ukládá / upsertuje v tabulce `user_profiles` jako JSONB. Merge logika je v `UserProfileService.apply_patch`.

Možné edge‑cases k ručnímu ověření:
- Přidání více hodnot najednou: „Pamatuj si, že nemám rád koriandr a cizrnu.“ → jedno `append` pole se dvěma hodnotami.
- Odstranění: „Zapomeň na tu dočasnou poznámku.“ → očekává se `remove` s příslušným klíčem, pokud existuje.

Další plánované vylepšení:
- Audit trail patch operací (log/versioning tabulka)
- Limitace počtu zápisů za časové okno (rate limiting) – ochrana proti spamování modelem
- Heuristická validace obsahových kategorií (např. filtrace PII)

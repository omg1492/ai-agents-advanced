# Lekce 05 - Paměť uživatele, Shrnutí konverzací & Realtime Voice

V této lekci navazujeme na agentic / grafové vyhledávání (Lekce 04) a přidáváme uživatelskou dlouhodobou paměť (raw zprávy + shrnutí), profil s řízeným zápisem a základní obousměrný hlasový režim. Cílem je personalizovanější odpověď a multimodální interakce.

## Byznys motivace
Uživatel očekává, že si systém pamatuje stabilní preference (dieta, alergie, oblíbené/zakázané ingredience) bez opakovaného zadávání. Současně chce mít možnost navazovat na předchozí konverzace, například "Minulý týden jsi mi doporučil jednu limonádu. Byla dobrá, má nějaké další příchutě?. Současně ale chce mít možnost přesné znění předchozích konverzací ukládat pouze omezenou dobu a selektivně vymazat, pokud to potřebuje.

## Implementace paměti
- `conversations_raw` obsahují uložené konverzace slovo od slova a slouží pro další zpracování, nicméně uživatel se na ně může zpětně podívat v UI a případně konkrétní konverzaci smazat.
- Dávkově se spouští AI zpracování konverzace s cílem bezpečně (odstanění nevhodných vecích nebo příliš osobních) a jednotně vytvořit sumarizaci konverzace. Ta se uloží do `conversation_summaries`.
- Agent má k dispozici nástroj `memory_search`, který s využitím fencingu (`WHERE user_id = ?`) umožňuje agentovi prohledávat sumáře předchozích konverzací, pokud se tak rozhodně.
- K uživateli se postupně vytváří uživatelský profil, který je zpočátku prázdný a uložený v `user_profiles`. Tento profil se vkládá přímo do systémového promptu vždy.
- Agent má k dispozici nástroj `memory_write_profile`, kterým pokud zjistí něco zásadního o uživateli nebo ten ho o to požádá, uloží informaci do profilu.

## Implementace hlasu
Pro hlas používáme speech-to-speech model, což nám umožňuje dobře zachycovat i emoce a tón hlasu. 

- WebSocket streaming PCM16 (24 kHz)
- Whisper transkripce `language=cs`
- VAD přerušuje aktuální odpověď při novém vstupu
- `Mute` neukončí spojení, pouze dočasně neodesílá audio
- Persistujeme pouze textové přepisy (audio se neukládá)

## Jak vyzkoušet (rychlý start)
1. Spusťte lokální infrastrukturu (PostgreSQL, Keycloak, stock API, agent - pokud ještě neběží):
```bash
cd deploy/local
docker compose up -d postgres keycloak api-stock
```

1. Inicializujte data. Základní pořadí + volitelné kroky:
```bash
cd data/scripts
uv run configure_postgresql.py      # (jednorázově) rozšíření/ tabulky pokud ještě nejsou
uv run gen_basic_data.py            # (volitelné) základní produkty (JSON / Parquet)
uv run gen_qna.py                   # (volitelné) generace QnA páru dotaz/odpověď
uv run gen_graph_taxonomy.py        # (volitelné) generace taxonomy konceptů (kategorie/kuchyně)

# Embeddings (vyžadují OPENAI_API_KEY):
uv run embeddings_products.py       	# (volitelné) embeddings pro detailní produkty (a is_vip označení)
uv run embeddings_simple_products.py  	# (volitelné) embeddings pro zjednodušené produkty
uv run embeddings_qna.py            	# (volitelné) embeddings pro QnA

# Importy do Postgres / pgvector:
uv run import_all.py

# Demo konverzace
uv run gen_conversations.py --user-id user1

# Batch pro zpracování konverzací
uv run process_conversations.py
```

3. (Volitelně) vytvoření Keycloak uživatelů - pokud máte připravený skript (např. `provision_keycloak.py` v `identity/`):
```bash
cd identity
uv run provision_keycloak.py
```

4. Spusťte agenta:
```bash
cd agents/dreamfarm-agent
uv run dreamfarm-agent
```

5. Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Rychlý demonstrační flow
1. Dotaz na paměť: „Bavili jsme se někdy o nějakém receptu s rajčaty? O čem konkrétně?".
5. Zápis do profilu: „Pamatuj si, že nemám rád kozí sýr a preferuji vegetariánská jídla." 
6. Ověření: „Co o mě víš?" (vrátí dietní preference + dislikes).
7. Voice: UI „Start Voice" → řekněte „Jaké dietní informace o mně máš?" → odpověď využije profil.

# Úkol (student branch)
Ve studentském branch nejsou některé věci implementovány:
- Tabulka a batch processing konverzací je, ale chybí vám nástroj pro agenta
- Uživatelský profil se do system promptu načítá, ale nemáte nástroj pro jeho úpravu, zápisy

## GitHub Copilot - příklady promptů pro začátek

Níže jsou příklady promptů pro GitHub Copilot. Copilot funguje nejlépe s kontextem - vysvětlete mu co chcete dosáhnout, jaké technologie používáte a jaké jsou kroky k řešení.

### Úkol 1: Implementace vyhledávání v paměti konverzací
```markdown
Help me create a memory search service that embeds a HyDE-style query, runs a vector similarity search against conversation summaries for the current user, and returns the top matches capped by configuration.
Update our OpenAI responses integration so the model can invoke a memory_search tool, routing calls through the new service only when the feature flag enables it.
Also expand the agent system prompt with a Memory Search section that:
1. Reminds the LLM to use the tool only for long-term preferences of the active user and always respect user_id scoping.
2. Instructs the LLM to craft a short HyDE-style summary before calling and to expect a capped result list.
3. Clarifies that returned summaries are historical context meant to ground personalization, not replacements for fresh user messages.
```

### Úkol 2: Implementace nástroje pro aktualizaci paměti
```markdown
Draft an apply_patch_with_report method for user profiles that merges set/append/remove instructions safely, persists the JSONB document, and returns a diagnostic summary of changes.
Extend the OpenAI responses handler with a memory_write_profile tool that calls the profile service, respects the feature toggle, and feeds the report back to the model.
Update the agent system prompt with a Profile Updates section that:
1. States the tool is used only after explicit user confirmation or when a durable contradiction appears.
2. Emphasizes emitting minimal patches (only changed fields) and confirming back to the user what was stored.
3. Directs the agent to request clarification from the user if a patch fails or produces warnings before retrying.
```


## Další možné rozšíření (dobrovolně)
- WebRTC transport pro nižší latenci hlasu
- Inkrementální sumarizace a promyslení jejich výhod a nevýhod (průběžné doplňování místo plného přegenerování)
- Zapomínací režim - vymyslete jak uživatelská paměť může zastarávat. Zjištění, které se potvrdí dalšími rozhovory, ať jsou posilována. O čem už nikdy není slyšet, ať se zapomíná. Pokud jsou nové informace v přímém konfliktu s předchozími, ať agent požádá o pomoc to pochopit.
- Uložené konverzace podporují vytvoření vlastního jména nebo přejmenování. Implementujte vygenerování jména automaticky na základě konverzace.
## Lekce 05 – Paměť & Voice

Přidáváme per‑user paměť (raw + shrnutí), vyhledávání v minulých konverzacích, uživatelský profil s řízeným PATCH zápisem a základní realtime voice mód.

### Co je uvnitř
| Vrstva | Služba / Tabulka | Poznámka |
|-------|------------------|----------|
| Raw chat | `conversations_raw` | JSONB array zpráv, status summarizace |
| Shrnutí | `conversation_summaries` | <=250 slov + embedding (pgvector 2000d) |
| Vyhledávání | `memory_search` tool | `WHERE user_id = ?` striktní izolace |
| Profil | `user_profiles` | Injektován do system promptu `<user_profile_json>` |
| Zápis profilu | `memory_write_profile` | `set` (deep merge), `append` (unikát), `remove` |
| Voice | `/voice/{thread_id}` WebSocket | Obousměrné PCM16, přepis, přerušení |

### Důvod
- Personalizace
- Nižší token náklady (shrnutí)
- Soukromí (raw lze smazat, shrnutí ponechat)
- Sdílený backend pro text i voice

### Rychlý Demo Flow
1. DB & DDL: (postgres běží) `uv run configure_postgresql.py`
2. Seed: `uv run python gen_conversations.py --user-id user1`
3. Summaries: `uv run python process_conversations.py --limit 5`
4. Chat: „Co jsem ti dříve říkal o své stravě?“ → čekej `memory_search` tool.
5. Profil zápis: „Pamatuj si, že nemám rád kozí sýr a preferuji vegetariánská jídla.“ → patch (set+append).
6. Ověření: „Co o mě víš?“ → dieta + dislikes.
7. Voice: Klik „Start Voice“ → řekni: „Jaké dietní informace o mně máš?“ → odpověď využije profil.

### Příklady promptů
Paměť: „Co jsem zmiňoval o pálivosti?“ • „Jaké preference mám?“
Profil injekce: „Co o mě víš?“
Zápis: „Pamatuj si, že…“ / „Už vlastně jím ryby…“

### `memory_write_profile` – Patch formát
```json
{ "patch": {
  "set": { "diet": { "vegetarian": true } },
  "append": { "dislikes": ["kozí sýr"] },
  "remove": ["obsolete_key"]
}}
```
Pravidla: explicitní dlouhodobá informace, 1 volání / turn, žádné dočasné nálady, posíláme pouze změny.

### Voice (základ)
- WebSocket + PCM16 (24 kHz), Whisper `language=cs`.
- VAD přeruší odpověď při novém vstupu uživatele.
- `Mute`: neukončí WS, jen neodesílá audio.
- Persistujeme pouze text přepisů.

### Známé TODO
- Scheduler (summaries + enrichment)
- Retence raw (`expires_at`)
- Audit trail profilu
- Incremental summarization
- WebRTC

### Odkazy na detaily
Plné vysvětlení: `docs/Design.md` (Memory & Voice)

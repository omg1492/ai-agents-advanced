## Lekce 07 – Orchestrace s Temporal

Implementujeme dlouhodobě běžící business proces (handling stížností) pomocí **Temporal** orchestrace s integráciou Azure OpenAI. Workflow zajišťuje spolehlivé víceúrovňové vyřizování stížností – od klasifikace přes extrakci dat, rozhodování podle firemní politiky až po generování odpovědí.

### Byznys motivace
Komplexní procesy (stížnosti, objednávky, onboarding) vyžadují spolehlivou orchestraci s automatickými retry, auditováním a schopností pokračovat po výpadku. Temporal zajišťuje perzistenci stavu a deterministické provedení workflow.

### Co je Temporal
**Temporal** je platforma pro orchestraci dlouhodobě běžících procesů (durable workflows). Garantuje:
- Automatické opakování (retry) při selhání
- Perzistentní stav workflow (přežije restarty, deploymenty)
- Deterministické provedení (oddělení logiky od side-effectů)
- Viditelnost do Web UI (http://localhost:8233)

### Architektura workflow
```
Stížnost → Klasifikace (LLM) → Extrakce (LLM) → Fetch profilu → Rozhodnutí (LLM) → Řešení (LLM)
                ↓                    ↓                ↓               ↓                 ↓
          is_complaint?      order_id/produkty    user_score    VALID/NOT_VALID    zpráva/review
```

### Fáze workflow (6 kroků)

| Fáze | Aktivita | Popis | Model výstup |
|------|----------|-------|-------------|
| **1. Klasifikace** | `classify_complaint` | Je to vůbec stížnost? | `is_complaint: bool`, `confidence: float` |
| **2. Extrakce** | `extract_complaint_info` | Struktura ze zprávy (produkty, order_id, datum, důvod, evidence) | `ComplaintExtraction` (všechna pole optional) |
| **3. Profil** | `fetch_user_profile` | Zákaznická data (segment, score, historie) – mockované | `UserProfile` (score 0-100, loyalita, objednávky, stížnosti) |
| **4. Rozhodnutí** | `decide_complaint_validity` | VALID / NOT_VALID / HUMAN_REVIEW podle politiky + few-shot | `ComplaintDecision` (action, reason, confidence) |
| **5a. Zpráva** | `generate_user_message` | Pro VALID/NOT_VALID: omluva nebo zamítnutí | `UserMessage` (subject, message, tone) |
| **5b. Review** | `generate_review_packet` | Pro HUMAN_REVIEW: balíček pro lidského operátora | `ReviewPacket` (summary, pro/proti, doporučení) |

**Workflow logika**:
- Pokud není stížnost (fáze 1) → early exit s informační zprávou.
- Pokud je stížnost → postupně projde všemi fázemi s automatickým retry při selhání.
- Rozhodnutí využívá firemní politiku + kontext zákazníka (loyalita, score).

### Technologie
- **Temporal** (durable orchestration)
- **Azure OpenAI** (Responses API, structured outputs, reasoning support)
- **Pydantic** (type-safe data modely)
- **Python 3.12** + `uv` (package management)

---

## Jak předvést demo

### Prerekvizity
1. Temporal server (dev režim):
   ```pwsh
   temporal server start-dev
   ```
   Web UI: http://localhost:8233

2. Azure OpenAI konfigurace (`.env` v `orchestration/complaint_workflow/`):
   ```env
   OPENAI_API_KEY=...
   OPENAI_BASE_URL=https://....openai.azure.com/openai/v1/
   OPENAI_API_VERSION=2024-10-21
   OPENAI_MODEL=gpt-5
   REASONING_EFFORT=minimal
   ```

3. Závislosti:
   ```pwsh
   cd orchestration/complaint_workflow
   uv sync
   ```

### Demo run (self-contained worker)
Spusťte demo skript – automaticky nastartuje worker a zpracuje všechny příklady:
```pwsh
uv run python demo.py
```

**Co se stane**:
- Načtou se příklady z `complaints/` (complaint1.json, complaint2.json, non-complaint.json)
- Každý projde kompletním workflow (6 fází)
- Výpisy ukazují klasifikaci, extrakci, profil, rozhodnutí a výsledek
- Odkazy na Temporal UI pro live inspekci

**Výstupy**:
- `complaint1.json` (prasklá sklenice, dobrý zákazník) → **VALID** → omluva + refund
- `complaint2.json` (shnilé produkty, podezřelý profil) → **HUMAN_REVIEW** → review packet
- `non-complaint.json` (dotaz na produkty) → **early exit** → informační zpráva

### Krokování v UI
1. Otevřete http://localhost:8233
2. Najděte workflow ID (např. `complaint-demo-complaint1`)
3. Klikněte na workflow → vidíte historii events (ClassifyComplaintActivity, ExtractComplaintInfoActivity...)
4. Každá aktivita zobrazí input, output a reasoning (pokud je `REASONING_EFFORT` > minimal)

### Produkční režim (long-running worker)
Pro produkci (webhook, queue consumer):
```pwsh
# Terminal 1: worker (běží dlouhodobě)
uv run python worker.py

# Terminal 2: spuštění workflow programově
uv run python client_run.py complaints/complaint1.json
```

---

## Příklady scénářů

### Scénář 1: Validní stížnost (auto-approve)
**Input**: „Rozbitá sklenice sýra, objednávka #ORD789, mám fotky"
**Profil**: Loyální zákazník, vysoký score (85), 42 objednávek, 1 předchozí stížnost
**Cesta**: Klasifikace (✓) → Extrakce → Profil → **VALID** → Zpráva
**Výsledek**: Omluva, refund, subject „We're Taking Care of This"

### Scénář 2: Eskalace na člověka (HUMAN_REVIEW)
**Input**: „Produkty byly shnilé, připojuji fotky"
**Profil**: Nový účet, 0 objednávek, 3 stížnosti (podezřelý pattern)
**Cesta**: Klasifikace (✓) → Extrakce → Profil → **HUMAN_REVIEW** → Review packet
**Výsledek**: Packet s pro/proti argumenty, doporučená akce, high priority

### Scénář 3: Není stížnost (short-circuit)
**Input**: „Máte bio rajčata skladem?"
**Cesta**: Klasifikace (✗) → **Early exit**
**Výsledek**: „Děkujeme za dotaz, navštivte help centrum"

---

## Struktura projektu

```
orchestration/complaint_workflow/
├── models.py              # Pydantic modely (ComplaintIn, WorkflowResult, ...)
├── workflow.py            # Temporal workflow (orchestrace logiky)
├── activities.py          # Activities (LLM volání, fetch dat)
├── llm_adapter.py         # Azure OpenAI client wrapper
├── worker.py              # Long-running worker proces
├── demo.py                # Self-contained demo (embedded worker)
├── complaints/            # Příklady JSON (complaint1, complaint2, non-complaint)
├── .env.sample            # Šablona konfigurace
└── pyproject.toml         # Závislosti (temporalio, openai, pydantic)
```

---

## Klíčové koncepty

### Workflow vs Activities
- **Workflow** = deterministická logika (if/else, loop) – žádné I/O, žádné random
- **Activities** = side-effecty (LLM API, DB, HTTP) – s retry policy a timeouts

### Structured Outputs
Všechna LLM volání používají `responses.parse()` s Pydantic schématy → type-safe, validované odpovědi.

### Policy-Based Decision
Rozhodovací aktivita (`decide_complaint_validity`) používá:
- Firemní politiku (dokument s pravidly)
- Few-shot examples (6 anotovaných příkladů)
- Kontext zákazníka (score, loyalita, historie)
→ Konzistentní, vysvětlitelná rozhodnutí

### Observability
- Structured logging s `ORCH_PHASE` prefixem (classify, extract, decide, ...)
- Temporal Web UI pro live inspekci
- Event history (každá aktivita = event s input/output)

---

## Shrnutí
Temporal orchestrace poskytuje robustní základ pro komplexní business procesy s LLM. Oddělení workflow logiky od side-effectů (activities) zajišťuje spolehlivost, testovatelnost a možnost evoluce systému bez ztráty běžících procesů.

**Benefity**:
- Automatické retry při selhání LLM / API
- Perzistence stavu (přežije restarty, deploymenty)
- Audit trail (každý krok zalogován)
- Type-safe díky Pydantic
- Škálovatelné (worker pool, horizontal scaling)

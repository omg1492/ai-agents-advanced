# Common Errors (Condensed Reference)

Purpose: Fast lookup of recurring pitfalls. Each category lists: Symptom → Cause → Fix / Prevention with a minimal example. Keep this lean; update when a NEW root cause appears (not just another manifestation).

---

## 1. Environment & Test Setup
| Issue | Symptom | Cause | Fix | Prevent |
|-------|---------|-------|-----|---------|
| Missing env vars in tests | `KeyError: 'AZURE_OPENAI_EMBEDDING_API_KEY'` | `.env` not loaded in integration test process | `from dotenv import load_dotenv; load_dotenv()` at test entry | Add `conftest.py` fixture to load once |
| Patch / indentation regressions | `IndentationError` or silent nested functions | Partial diffs shifted left margin | Re‑align functions; run `python -m py_compile target.py` | After large patch, import module in a trivial test |

Example (test bootstrap):
```python
# tests/conftest.py
from dotenv import load_dotenv
load_dotenv()
```

---

## 2. Frontend (React / Voice / Threads)
| Problem | Symptom | Cause | Fix | Prevent |
|---------|---------|-------|-----|---------|
| Voice session lost / duplicates in dev | Button stays active / duplicate websockets | React Strict Mode remount disposes refs | Move WebSocket, AudioContext, MediaStream into singleton `voiceSessionManager` | Keep long‑lived resources outside component lifecycle |
| Implicit thread not shown | First conversation missing in sidebar until reload | Thread created silently w/out events | Dispatch `df-thread-created` + `df-thread-selected` after lazy creation | Always emit domain events when mutating backend state |

Voice example (singleton sketch):
```ts
export const voiceSessionManager = (() => { /* holds ws, audioCtx, mediaStream */ })();
```

---

## 3. Azure OpenAI & Reasoning / Realtime
| Issue | Symptom | Cause | Fix | Prevent |
|-------|---------|-------|-----|---------|
| Realtime session errors | `Unknown parameter: 'session.type'` | Azure preview excludes `type`, `model`, `output_modalities` in session.update | Only send supported keys (`modalities`, `voice`, formats, tools) | Branch logic: add `output_modalities` only for non‑Azure |
| Missing reasoning pairing | `fc_* ... without ... rs_*` | Not persisting preceding reasoning items | Append `reasoning` → then `function_call` → then output | Maintain ordered item log; test multi‑tool chain |
| Structured output TypeError | `unexpected keyword 'response_format'` | Using `response_format` with async Responses API | Use `client.responses.parse(..., response_format=Model)` | Wrap in small unit test mocking client |
| **Code Interpreter files parameter** | `Unknown parameter: 'tools[0].container.files'` | **Azure requires `file_ids` not `files` (docs are wrong)** | Use `{"type":"code_interpreter","container":{"type":"auto","file_ids":[...]}}` | **Research: MS Q&A + OpenAI forums revealed solution; adhoc test proved it** |
| Reasoning model no text output | Streaming returns 0 chunks; log shows "Reasoning step completed" | Reasoning model can complete without emitting text (pure reasoning response) | Accept reasoning-only responses OR use non-streaming endpoint | Test both streaming/non-streaming; handle empty text case |

Realtime session example:
```python
session = {"modalities":["text","audio"],"voice":"alloy"}
if not is_azure: session["output_modalities"]=["text","audio"]
await conn.session.update(session=session)
```

Code Interpreter with files example:
```python
# CORRECT (Azure OpenAI Responses API):
tools = [{
    "type": "code_interpreter",
    "container": {"type": "auto", "file_ids": ["assistant-abc123", "assistant-xyz789"]}
}]
# WRONG (documented but doesn't work):
# "container": {"files": [...]}  ← This parameter name is incorrect!
```

**Discovery Process for Code Interpreter Issue:**
1. Microsoft documentation shows `"files"` parameter
2. Azure API rejects with: `Unknown parameter: 'tools[0].container.files'`
3. Web research (Tavily) found MS Q&A thread: users reported same issue July 2025
4. Community solution: use `"file_ids"` instead of `"files"`
5. Adhoc test proved: `file_ids` ✅ works, `files` ❌ fails
6. Timeline: feature deployed working August 7, 2025
7. **Key lesson**: Azure OpenAI implementation can differ from OpenAI docs; community sources more reliable

Reasoning stream rule of thumb: Always record EVERY item the model streams (reasoning / function_call / output / message) in exact order.

---

## 4. Data Imports & Embeddings
| Issue | Symptom | Cause | Fix | Prevent |
|-------|---------|-------|-----|---------|
| All product rows skipped | Log: `Skipped N rows... 0 rows to import` | Embedding dimension != DB vector(2000) | Request `dimensions=2000`; assert length | Add assert on first vector; CI check |
| Dangerous TRUNCATE in prod | Data loss risk | Dev convenience leaked | Gate behind env flag; use UPSERT/stage swap in prod | `if ENVIRONMENT=='prod': abort on TRUNCATE` |

Quick assert:
```python
assert len(embeddings[0]) == 2000, "Embedding dimension mismatch"
```

---

## 5. Retrieval / Search (RAG, FTS, Fusion)
| Issue | Symptom | Cause | Fix | Prevent |
|-------|---------|-------|-----|---------|
| FTS zero recall | Multi‑phrase queries return nothing | `plainto_tsquery` ANDs all tokens | Build OR of AND phrase groups: `(a & b) | (c & d)` | Log phrases + final tsquery; integration test known hit |
| Confusing score meaning | Misinterpreting fused vs cosine | RRF overwrote semantic score field | Rename/log `fused_score` or document | Explicit log of stage counts + formula |
| High false negatives in RAG | No semantic hits above threshold | Threshold too strict | Lower threshold empirically (e.g. 0.7 → 0.5) | Track distribution of similarity during tuning |

FTS build sketch:
```python
groups=[" & ".join(p.split()) for p in phrases]
tsquery=" | ".join(groups)
```

---

## 6. PostgreSQL + Apache AGE (Cypher & Graph)
Core Principles:
1. Prefer 3‑arg `cypher(:graph, $$query$$, $$)` if available; fallback to 2‑arg.
2. Entire Cypher body inside one dollar‑quoted block; only `:graph` bound outside.
3. Separate engines: one for vector ops, one for AGE (avoids extension state interference).
4. Normalize apostrophes to `’` before embedding large text.
5. Use positional ORDER BY when alias resolution fails.

| Issue | Symptom | Cause | Fix | Prevent |
|-------|---------|-------|-----|---------|
| Undefined / wrong `cypher` signature | `function cypher(...) does not exist` | Version mismatch (2 vs 3 args) | Probe `pg_proc`; choose supported form | Keep probe helper; document version |
| Colon token treated as bind | `bind parameter 'IN_CATEGORY'` | SQLAlchemy parsing colon in body | Keep colon tokens inside `$$...$$` block | Never concat partial Cypher with stray colons outside block |
| Unterminated dollar string | Parse error | Unbalanced/multiple `$$` | Balance once; avoid inserting `$$` in body | Helper to validate count of `$$` (should be 2) |
| Apostrophe syntax errors | Mid‑batch failure | Raw `'` deep in nested quoting | Replace `'` → `’` pre‑format | Centralize sanitizer |
| ORDER BY alias error | `could not find rte` | Set-returning function alias not visible | Use positional `ORDER BY 2` | Adopt positional in shared helpers |
| Vector / AGE interference | Odd `@>` or agtype errors | Mixed extensions on same connection | Separate engine & `LOAD 'age'` hook | Always isolate vector queries |
| agtype quoted IDs | Values like `"uuid"` | agtype string wrapper | `str(val).strip('"')` | Utility unwrap function |

Canonical pattern:
```python
cypher_body="""MATCH (p:Product) RETURN p.product_id AS product_id"""
sql=text("SELECT product_id FROM cypher(:graph, $$"+cypher_body+"$$, $$) AS (product_id uuid)")
rows=conn.execute(sql,{"graph": graph}).fetchall()
```

Smoke test:
```python
q=text("SELECT 1 FROM cypher(:g, $$MATCH (n) RETURN n LIMIT 1$$, $$) AS (x agtype)")
conn.execute(q,{"g":graph})
```

Sanitizer:
```python
def sanitize(s:str|None): return "" if not s else s.replace("'","’")
```

---

## 7. Graph Search Service (Isolation & Binding)
Consolidated (applies on top of Category 6):
| Problem | Symptom | Fix | Prevent |
|---------|---------|-----|---------|
| Shared engine contamination | AGE queries fail after vector ops | Use fresh engine with `LOAD 'age'; SET search_path=ag_catalog, public;` | Factory method `_get_fresh_age_engine()` |
| Improper parameter array binding | Errors with `ANY(ARRAY[..])` | String interpolation of list | Use named param: `= ANY(:product_ids)` | Always bind Python list directly |

---

## 8. Code Quality & Safety Patterns
| Pattern | Why | Minimal Action |
|---------|-----|----------------|
| Import smoke test after large refactor | Catch syntax / indentation early | `python -m py_compile src/...` |
| Log raw constructed SQL / tsquery | Faster diagnosis of empty results | Add debug log on first 100 chars |
| Assert invariants (embedding dim) | Fail fast vs silent skip | `assert len(vec)==2000` |
| Event emission after implicit state change | Keep UI consistent | Dispatch creation + selection events |

---

## 9. Quick Do / Avoid Matrix
| Do | Avoid |
|----|-------|
| Single dollar‑quoted Cypher body | Mixing binds & colon tokens outside block |
| Separate engines (vector vs AGE) | Reusing contaminated connection |
| Phrase‑aware FTS `(a & b) | (c & d)` | Blind `plainto_tsquery` on combined text |
| Explicit reasoning item ordering | Assuming function calls arrive self‑contained |
| Dimension assertion on first embedding | Importing thousands then discovering mismatch |
| Singleton manager for long‑lived browser resources | Storing sockets in transient React components |

---

## 10. Minimal Cheat Sheet
- Load env in tests: `load_dotenv()`.
- Realtime (Azure): omit `type`, `model`, `output_modalities`.
- Cypher: prefer 3‑arg; fallback 2‑arg; only `:graph` bound.
- Vector + AGE: isolate connections.
- FTS query: OR of AND phrase groups.
- Embeddings: enforce 2000 dims.
- Reasoning stream: record every item in order.
- Voice: external session manager.

---

Update Policy: Replace sections—do not append duplicates. If an older rule is superseded, edit the existing entry instead of adding a new one.



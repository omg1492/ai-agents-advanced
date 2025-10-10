# Common Errors (Condensed Reference)

Purpose: Fast lookup of recurring pitfalls. Each category lists: Symptom → Cause → Fix / Prevention with a minimal example. Keep this lean; update when a NEW root cause appears (not just another manifestation).

---

## 1. Environment & Test Setup
| Issue | Symptom | Cause | Fix | Prevent |
|-------|---------|-------|-----|---------|
| Missing env vars in tests | `KeyError: 'AZURE_OPENAI_EMBEDDING_API_KEY'` | `.env` not loaded in integration test process | `from dotenv import load_dotenv; load_dotenv()` at test entry | Add `conftest.py` fixture to load once |
| **Integration test DNS failure** | `httpx.ConnectError: [Errno 11001] getaddrinfo failed` despite server being accessible | `.env` not loaded when running multiple test types together (unit + integration); pytest parallelism causes env loading race | Add `from dotenv import load_dotenv; load_dotenv(Path(__file__).parent.parent / ".env")` at top of integration test module | Always load `.env` explicitly in integration test modules; run integration tests separately with `-m integration` |
| Patch / indentation regressions | `IndentationError` or silent nested functions | Partial diffs shifted left margin | Re‑align functions; run `python -m py_compile target.py` | After large patch, import module in a trivial test |

Example (test bootstrap):
```python
# tests/conftest.py
from dotenv import load_dotenv
load_dotenv()
```

**Integration test environment loading pattern:**
```python
# tests/test_integration_feature.py
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root for integration tests
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Now safe to import services that read environment
from src.services.config_service import ConfigService
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
| **Code Interpreter output files** | `sandbox:/mnt/data/file.png` links don't work; `outputs` field always None | **Azure Responses API stores file info in annotations, NOT outputs** | Parse `response.output[].content[].annotations[]` for `file_id`, `container_id`, `filename`; build filename→file_id mapping | **Research: GitHub repo + MS docs revealed annotations approach; testing confirmed outputs always None in ALL scenarios** |
| **Code Interpreter download 404** | Browser requests `/files/<id>/content` → 404 (log: `Generated file not found or expired`) | Starší odpovědi bez download tokenu nebo Azure vrátilo výsledek bez `container_id`, takže nebyla zapsaná metadata | Spusťte analýzu znovu (aby vznikl nový token) nebo přejděte na verzi s fallbackem `/files/{file_id}/content`; frontend nyní připojuje `?token=...` | Při registraci souborů vždy ukládat token + tolerovat chybějící `container_id`; frontend musí token doplnit do URL |
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

**Discovery Process for Code Interpreter Output Files Issue:**
1. Initial assumption: `outputs` field in streaming events contains file info → **Testing proved: always None**
2. Second attempt: retrieve full response, extract from `outputs` → **Testing proved: still None in ALL scenarios**
3. Created adhoc test (`adhoc_test_outputs.py`) comparing streaming vs non-streaming vs retrieved → **Definitively proved: `outputs` attribute exists but value always None**
4. Heavy research using multiple tools (Azure docs search, Tavily search, webpage fetch, code sample search)
5. **BREAKTHROUGH**: Found GitHub repo (LazaUK/AIFoundry-ResponsesAPI-CodeInterpreter) with working implementation
6. Extracted complete working code from Jupyter notebook showing correct approach
7. **Correct location**: Files referenced in `response.output[].content[].annotations[]` NOT in `outputs`
8. **Annotations structure**: Each annotation contains: `container_id`, `file_id`, `filename`
9. **Download mechanism**: Container API endpoint `/openai/v1/containers/{container_id}/files/{file_id}/content`
10. **Key lesson**: API reference showing field existence doesn't mean field is populated; Azure Responses API intentionally uses annotations (different from Assistants API); working example code more valuable than API docs

**Code Interpreter Annotations Extraction Pattern:**
```python
# CORRECT approach - extract from annotations:
generated_files = {}
for item in response.output:
    if item.type == 'message' and hasattr(item, 'content'):
        for content_block in item.content:
            if hasattr(content_block, 'annotations') and content_block.annotations:
                for annotation in content_block.annotations:
                    if hasattr(annotation, 'file_id'):
                        container_id = annotation.container_id
                        file_id = annotation.file_id
                        filename = annotation.filename
                        generated_files[filename] = file_id

# WRONG approach - outputs is always None:
# outputs = getattr(output_item, 'outputs', None)  # ← This will ALWAYS be None!
```

Reasoning stream rule of thumb: Always record EVERY item the model streams (reasoning / function_call / output / message) in exact order.

---

## 3a. MCP Visualization Artifacts
| Issue | Symptom | Cause | Fix | Prevent |
|-------|---------|-------|-----|---------|
| **Iframe shows frontend index.html** | Visualization box displays wrong content; browser requests `http://localhost:3000/artifacts/{id}` instead of backend | Frontend component uses relative URL (apiUrl="") which resolves to current origin | Pass explicit backend URL: `<VisualizationArtifact apiUrl={dreamFarmAPI.getBaseUrl()} />` | Always use absolute URLs for cross-origin iframe sources |
| **401 Unauthorized on artifact endpoint** | Browser console shows `GET /artifacts/{id}` → 401; visualization box shows auth error | Artifact endpoint requires authentication but iframes cannot pass Authorization headers via `src` attribute | Remove auth requirement from endpoint: delete `user_ctx: tuple = Depends(_require_user)` parameter | Use public endpoints for iframe-loaded content; rely on UUID security + TTL |
| **MCP output not detected** | No artifact created despite MCP tool call in logs | Output parsing fails (wrong JSON structure or missing html field) | Add DEBUG logging: log `type(output_content)`, parsed keys, HTML preview (first 200 chars) | Enable `LOG_LEVEL=DEBUG` to trace MCP output structure |

Visualization artifact pattern:
```python
# Backend: Public endpoint (no auth)
@app.get("/artifacts/{artifact_id}")
async def get_html_artifact(artifact_id: str, request: Request):
    artifact = _html_artifact_registry.get(artifact_id)
    if not artifact: raise HTTPException(404)
    return HTMLResponse(content=artifact["html"])

# Frontend: Explicit backend URL
const backendUrl = dreamFarmAPI.getBaseUrl();
return <VisualizationArtifact artifactId={id} apiUrl={backendUrl} />;
```

**Why Artifacts Must Be Public:**
- Browsers don't include authorization headers when loading iframe `src` attribute
- Security via UUID (128-bit random, hard to guess: 2^128 = 3.4×10^38 possibilities)
- Short TTL (1 hour) limits exposure window
- Content is user-generated HTML visualizations (no sensitive data)

**Discovery Process for Iframe Loading Issue:**
1. User tested: "Create a beautiful card..." → empty box displayed
2. Browser network tab showed: `http://localhost:3000/artifacts/{id}` (wrong port)
3. Response contained frontend index.html instead of artifact HTML
4. Root cause: VisualizationArtifact component had `apiUrl=""` default
5. Empty string causes relative URL → resolves to current origin (frontend:3000)
6. Fix: Pass explicit `apiUrl={dreamFarmAPI.getBaseUrl()}` → correct port (backend:8001)
7. **Key lesson**: Always pass explicit URLs for cross-origin iframe content

---

## 3b. FastMCP Server Development
| Issue | Symptom | Cause | Fix | Prevent |
|-------|---------|-------|-----|---------|
| **TokenVerifier missing base_url** | `AttributeError: 'EnvAPIKeyVerifier' object has no attribute 'base_url'` on server start | Custom `TokenVerifier` subclass doesn't call `super().__init__(base_url=...)` | Add `super().__init__(base_url=None)` in custom verifier's `__init__` | Always call parent `__init__` when subclassing FastMCP auth classes; use `inspect.signature()` to discover required parameters |

FastMCP custom auth verifier pattern:
```python
from fastmcp.server.auth.auth import TokenVerifier, AccessToken
from typing import Optional

class EnvAPIKeyVerifier(TokenVerifier):
    """Static bearer token verifier for development."""
    
    def __init__(self, required_token: str):
        super().__init__(base_url=None)  # ← Critical: must call parent init
        self._token = required_token
    
    async def verify_token(self, token: str) -> Optional[AccessToken]:
        if token and token == self._token:
            return AccessToken(
                token=token,
                client_id="api-key-user",
                scopes=["*"],
            )
        return None
```

**Discovery Process for TokenVerifier Issue:**
1. Server crashed on startup with `AttributeError: 'EnvAPIKeyVerifier' object has no attribute 'base_url'`
2. Initial code copied from `mcp_public_farmer_tools` but that version was outdated
3. Used Python introspection: `inspect.signature(TokenVerifier.__init__)` revealed required `base_url` parameter
4. Signature showed: `(self, base_url: 'AnyHttpUrl | str | None' = None, required_scopes: 'list[str] | None' = None)`
5. Fixed by adding `super().__init__(base_url=None)` call
6. **Key lesson**: When subclassing framework classes, always check parent `__init__` signature; FastMCP 2.0 may differ from examples in older projects

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
- FastMCP auth: always call `super().__init__(base_url=None)` in custom `TokenVerifier` subclass.

---

Update Policy: Replace sections—do not append duplicates. If an older rule is superseded, edit the existing entry instead of adding a new one.



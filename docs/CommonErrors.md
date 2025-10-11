# Common Errors Reference

**Purpose**: Fast lookup of recurring pitfalls with symptoms, root causes, fixes, and prevention strategies. Organized by category with code examples.

---

## 1. Environment & Configuration

### 1.1 Missing Environment Variables in Tests
**Symptom**: `KeyError: 'AZURE_OPENAI_EMBEDDING_API_KEY'` or similar environment variable errors

**Root Cause**: `.env` file not loaded in test process, especially in integration tests

**Fix**: Load environment explicitly in test modules
```python
# tests/conftest.py (global fixture)
from dotenv import load_dotenv
load_dotenv()
```

**Integration Test Pattern** (when running mixed unit + integration):
```python
# tests/test_integration_feature.py
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root before importing services
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from src.services.config_service import ConfigService  # Safe now
```

**Prevention**: 
- Add `conftest.py` fixture for pytest
- Run integration tests separately: `pytest -m integration`
- Load `.env` explicitly in integration test modules before imports

### 1.2 Code Quality After Refactoring
**Symptom**: `IndentationError`, `SyntaxError`, or silent function nesting issues

**Root Cause**: Large code patches shifted left margin or broke indentation

**Fix**: Validate syntax immediately
```bash
python -m py_compile src/module.py
```

**Prevention**: Run syntax check after every large refactor; import module in trivial test


---

## 2. Frontend (React / Voice / Threads)

### 2.1 Voice Session Management
**Symptom**: Voice button stays active after unmount; duplicate WebSocket connections; audio context errors

**Root Cause**: React Strict Mode remounting disposes refs; WebSocket/AudioContext/MediaStream tied to component lifecycle

**Fix**: Move long-lived resources into singleton manager outside component
```typescript
// voiceSessionManager.ts - singleton pattern
export const voiceSessionManager = (() => {
    let ws: WebSocket | null = null;
    let audioCtx: AudioContext | null = null;
    let mediaStream: MediaStream | null = null;
    
    return {
        connect: () => { /* initialize resources */ },
        disconnect: () => { /* cleanup resources */ },
        // ... other methods
    };
})();
```

**Prevention**: Keep WebSocket, AudioContext, MediaStream in singleton; components only call manager methods

### 2.2 Thread Management
**Symptom**: First conversation missing in sidebar until page reload; new thread not selected automatically

**Root Cause**: Thread created implicitly without emitting UI events

**Fix**: Always dispatch domain events after state mutation
```typescript
// After creating thread
eventBus.dispatch('df-thread-created', { threadId: newThread.id });
eventBus.dispatch('df-thread-selected', { threadId: newThread.id });
```

**Prevention**: Emit events whenever backend state changes that affects UI

---

## 3. Azure OpenAI API

### 3.1 Realtime API Session Configuration
**Symptom**: `Unknown parameter: 'session.type'` or similar parameter errors

**Root Cause**: Azure preview excludes certain parameters (`type`, `model`, `output_modalities`) from session.update

**Fix**: Branch logic for Azure vs OpenAI
```python
session = {
    "modalities": ["text", "audio"],
    "voice": "alloy"
}
if not is_azure:
    session["output_modalities"] = ["text", "audio"]  # Only for OpenAI

await conn.session.update(session=session)
```

**Prevention**: Only send supported keys for Azure (`modalities`, `voice`, formats, tools)

### 3.2 Reasoning + Function Call Pairing
**Symptom**: Logs show `fc_* ... without ... rs_*`; function calls missing reasoning context

**Root Cause**: Not persisting reasoning items before function_call items

**Fix**: Maintain ordered item log
```python
# Always record items in exact order received
for item in stream:
    conversation_items.append(item)  # reasoning → function_call → output
```

**Prevention**: Test multi-tool chains; verify reasoning items precede function calls

### 3.3 Structured Output with Responses API
**Symptom**: `TypeError: unexpected keyword 'response_format'`

**Root Cause**: Async Responses API doesn't accept `response_format` in `create()` call

**Fix**: Use parse method instead
```python
# CORRECT
response = await client.responses.parse(
    model="gpt-5",
    response_format=YourPydanticModel,
    input=[...]
)

# WRONG
# response = await client.responses.create(response_format=...)
```

**Prevention**: Wrap in unit test with mocked client

### 3.4 Code Interpreter - File Input Parameter
**Symptom**: `Unknown parameter: 'tools[0].container.files'`

**Root Cause**: **Azure requires `file_ids` not `files` (official docs are incorrect)**

**Fix**: Use correct parameter name
```python
# CORRECT (Azure OpenAI Responses API)
tools = [{
    "type": "code_interpreter",
    "container": {
        "type": "auto",
        "file_ids": ["assistant-abc123", "assistant-xyz789"]  # ✅ Works
    }
}]

# WRONG (documented but doesn't work)
# "container": {"files": [...]}  # ❌ Fails
```

**Discovery Process**:
1. Microsoft docs show `"files"` parameter
2. Azure API rejects: `Unknown parameter: 'tools[0].container.files'`
3. Web research (MS Q&A, July 2025): users reported same issue
4. Community solution: use `"file_ids"` instead
5. Adhoc test confirmed: `file_ids` ✅, `files` ❌
6. Timeline: Feature deployed working August 7, 2025

**Key Lesson**: Azure OpenAI implementation can differ from OpenAI docs; community sources (Q&A, forums) often more reliable

**Prevention**: Research community sources for Azure-specific implementations; test with adhoc scripts

### 3.5 Code Interpreter - Output File Extraction
**Symptom**: `sandbox:/mnt/data/file.png` links don't work; `outputs` field always None

**Root Cause**: **Azure Responses API stores file info in `annotations`, NOT `outputs`**

**Fix**: Extract from correct location
```python
# CORRECT - extract from annotations
generated_files = {}
for item in response.output:
    if item.type == 'message' and hasattr(item, 'content'):
        for content_block in item.content:
            if hasattr(content_block, 'annotations') and content_block.annotations:
                for annotation in content_block.annotations:
                    if hasattr(annotation, 'file_id'):
                        generated_files[annotation.filename] = {
                            'file_id': annotation.file_id,
                            'container_id': annotation.container_id
                        }

# WRONG - outputs attribute exists but is always None
# outputs = getattr(output_item, 'outputs', None)  # ❌ Always None!
```

**Discovery Process**:
1. Initial assumption: `outputs` field contains file info → **Testing: always None**
2. Adhoc test (`adhoc_test_outputs.py`): streaming vs non-streaming vs retrieved → **Definitively: always None in ALL scenarios**
3. Heavy research: Azure docs, Tavily search, webpage fetch, code samples
4. **Breakthrough**: Found GitHub repo (LazaUK/AIFoundry-ResponsesAPI-CodeInterpreter) with working code
5. Extracted solution from Jupyter notebook
6. **Correct location**: `response.output[].content[].annotations[]`
7. **Annotations structure**: `container_id`, `file_id`, `filename`
8. **Download mechanism**: `/openai/v1/containers/{container_id}/files/{file_id}/content`

**Key Lesson**: API field existence ≠ field populated; Azure Responses API intentionally uses annotations (differs from Assistants API); working example code > API reference docs

**Prevention**: For new Azure features, search for working GitHub examples before relying on docs

### 3.6 Code Interpreter - File Download 404
**Symptom**: Browser requests `/files/<id>/content` → 404; backend logs: `Generated file not found or expired`

**Root Cause**: Older responses missing download token OR Azure returned result without `container_id`

**Fix**: Re-run analysis (generates new token) OR use fallback endpoint with token
```typescript
// Frontend: Always append token to download URL
const downloadUrl = `${baseUrl}/files/${fileId}/content?token=${token}`;
```

**Backend**: Store token when registering files; tolerate missing `container_id`
```python
# When storing file metadata
file_entry = {
    'file_id': file_id,
    'container_id': container_id or None,  # Tolerate missing
    'download_token': str(uuid.uuid4())     # Always generate
}
```

**Prevention**: Always store download token; handle missing `container_id` gracefully

### 3.7 Reasoning Model - No Text Output
**Symptom**: Streaming returns 0 chunks; log shows "Reasoning step completed" but no user-visible text

**Root Cause**: Reasoning models can complete with pure reasoning (no text output)

**Fix**: Accept reasoning-only responses OR use non-streaming endpoint
```python
# Handle empty text case
if not text_output and reasoning_items:
    # Valid: reasoning step completed without text emission
    return {"status": "reasoning_complete", "reasoning": reasoning_items}
```

**Prevention**: Test both streaming/non-streaming; expect empty text responses in reasoning models

### 3.8 Responses API Continuation Pattern
**Symptom**: `400 Bad Request: Request contains duplicate item IDs` when using `previous_response_id`

**Root Cause**: Accumulating full conversation history with `extend()` instead of sending ONLY tool outputs on continuation

**Fix**: Replace input messages with tool outputs only
```python
# CORRECT continuation pattern
input_messages = []  # Start empty
response_id = None

while True:
    response = client.responses.create(
        model="gpt-5",
        reasoning={"effort": "medium"},
        input=input_messages if not response_id else pending_outputs,  # KEY: Replace on continuation
        previous_response_id=response_id,  # Maintains context server-side
        store=True,
    )
    
    # ALWAYS capture response_id (not conditional!)
    if hasattr(response, 'id'):
        response_id = response.id
    
    # Collect tool outputs
    pending_outputs = []
    for output_item in response.output:
        if output_item.type == "function_call":
            result = execute_tool(output_item)
            pending_outputs.append({
                "type": "function_call_output",
                "id": output_item.id,
                "output": result
            })
    
    if not pending_outputs:
        break
    
    # CRITICAL: Replace (not extend) with ONLY tool outputs
    input_messages = pending_outputs  # Not .extend()!

# WRONG pattern (causes duplicate ID error)
# input_messages.extend(pending_outputs)  # ❌ Accumulates history server already has
```

**Key Principles**:
1. **First turn**: Send full conversation history
2. **Continuation turns**: Send ONLY tool outputs (when `previous_response_id` exists)
3. **Context preservation**: `previous_response_id` maintains full state server-side
4. **Response ID capture**: Update from EVERY `final_response.id`, not just first time
5. **No accumulation**: Server tracks conversation; client sends new tool outputs per cycle

**Discovery Process**:
1. Initial implementation: `input_messages.extend(pending_outputs)`
2. OpenAI rejected: `400 Bad Request: Request contains duplicate item IDs`
3. Root cause: Server already has previous messages via `previous_response_id`
4. Re-sending same IDs violates uniqueness constraint
5. Solution: `input_messages = pending_outputs` (replace, not extend)
6. Additional bug: response_id only captured first time (conditional)
7. Fixed: Always update `response_id = final_response.id`

**When This Matters**: Multi-turn function calling, agent-to-agent delegation, any `previous_response_id` usage

**Prevention**: Always replace input messages with tool outputs only; never extend conversation history on continuation

---

## 3a. MCP Visualization Artifacts
| Issue | Symptom | Cause | Fix | Prevent |
|-------|---------|-------|-----|---------|
| **Iframe shows frontend index.html** | Visualization box displays wrong content; browser requests `http://localhost:3000/artifacts/{id}` instead of backend | Frontend component uses relative URL (apiUrl="") which resolves to current origin | Pass explicit backend URL: `
---

## 4. MCP Server Development

### 4.1 Visualization Artifacts - Iframe Loading
**Symptom**: Visualization box displays frontend index.html instead of artifact; browser requests wrong origin

**Root Cause**: Relative URL (`apiUrl=""`) in VisualizationArtifact component resolves to frontend origin (port 3000) instead of backend (port 8001)

**Fix**: Pass explicit backend URL
```typescript
// Frontend component
const backendUrl = dreamFarmAPI.getBaseUrl();
return <VisualizationArtifact artifactId={id} apiUrl={backendUrl} />;
```

**Discovery Process**:
1. User tested: "Create a beautiful card..." → empty box
2. Browser network tab: `http://localhost:3000/artifacts/{id}` (wrong port)
3. Response contained frontend index.html
4. Root cause: `apiUrl=""` default → relative URL → frontend origin
5. Fix: Explicit `apiUrl={backendUrl}` → correct backend port

**Prevention**: Always use absolute URLs for cross-origin iframe sources

### 4.2 Visualization Artifacts - Authentication
**Symptom**: `GET /artifacts/{id}` → 401 Unauthorized; visualization box shows auth error

**Root Cause**: Artifact endpoint requires authentication but iframes cannot pass Authorization headers via `src` attribute

**Fix**: Make endpoint public (security via UUID + TTL)
```python
# Backend: Remove auth requirement
@app.get("/artifacts/{artifact_id}")
async def get_html_artifact(artifact_id: str, request: Request):
    # No auth parameter (was: user_ctx: tuple = Depends(_require_user))
    artifact = _html_artifact_registry.get(artifact_id)
    if not artifact:
        raise HTTPException(404)
    return HTMLResponse(content=artifact["html"])
```

**Why Public is Safe**:
- Browsers can't include Authorization headers in iframe `src`
- UUID security: 128-bit random (2^128 = 3.4×10^38 possibilities)
- Short TTL (1 hour) limits exposure
- Content is user-generated HTML (no sensitive data)

**Prevention**: Use public endpoints for iframe-loaded content; rely on UUID + TTL for security

### 4.3 MCP Output Detection
**Symptom**: No artifact created despite MCP tool call in logs

**Root Cause**: Output parsing fails (wrong JSON structure or missing html field)

**Fix**: Add debug logging
```python
logger.debug(f"MCP output type: {type(output_content)}")
logger.debug(f"MCP parsed keys: {parsed_output.keys() if isinstance(parsed_output, dict) else 'not dict'}")
logger.debug(f"HTML preview: {html_content[:200] if html_content else 'None'}")
```

**Prevention**: Enable `LOG_LEVEL=DEBUG` to trace MCP output structure

### 4.4 FastMCP TokenVerifier - Missing base_url
**Symptom**: `AttributeError: 'EnvAPIKeyVerifier' object has no attribute 'base_url'` on server start

**Root Cause**: Custom `TokenVerifier` subclass doesn't call `super().__init__(base_url=...)`

**Fix**: Always call parent initializer
```python
from fastmcp.server.auth.auth import TokenVerifier, AccessToken
from typing import Optional
import inspect

class EnvAPIKeyVerifier(TokenVerifier):
    """Static bearer token verifier for development."""
    
    def __init__(self, required_token: str):
        # CRITICAL: Must call parent init with base_url
        super().__init__(base_url=None)
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

**Discovery Process**:
1. Server crashed: `AttributeError: 'EnvAPIKeyVerifier' object has no attribute 'base_url'`
2. Older code from `mcp_public_farmer_tools` was outdated
3. Used introspection: `inspect.signature(TokenVerifier.__init__)`
4. Signature revealed: `(self, base_url: 'AnyHttpUrl | str | None' = None, required_scopes: 'list[str] | None' = None)`
5. Fixed: Added `super().__init__(base_url=None)`

**Key Lesson**: When subclassing framework classes, check parent `__init__` signature; FastMCP 2.0 differs from older examples

**Prevention**: Use `inspect.signature()` to discover required parameters; always call `super().__init__()`

---

## 5. Data Processing & Embeddings

### 5.1 Embedding Dimension Mismatch
**Symptom**: Log shows `Skipped N rows... 0 rows to import`; all product rows skipped

**Root Cause**: Embedding dimension doesn't match database vector column (e.g., 1536 vs 2000)

**Fix**: Request correct dimensions and assert
```python
# Request embedding with correct dimensions
embeddings = openai.embeddings.create(
    model="text-embedding-3-large",
    input=texts,
    dimensions=2000  # Match DB vector(2000)
)

# Assert on first vector
assert len(embeddings[0]) == 2000, f"Expected 2000 dims, got {len(embeddings[0])}"
```

**Prevention**: Add dimension assertion on first embedding; add CI check

### 5.2 Dangerous Data Operations in Production
**Symptom**: Risk of data loss from TRUNCATE in production environment

**Root Cause**: Development convenience (TRUNCATE for clean slate) leaked to production code

**Fix**: Gate destructive operations behind environment check
```python
if os.environ.get('ENVIRONMENT') == 'prod':
    raise ValueError("TRUNCATE not allowed in production")

# Use UPSERT or staging table swap in production
```

**Prevention**: Environment-based safety checks; use non-destructive patterns (UPSERT, staging swap) for production

---

## 6. Search & Retrieval (RAG, FTS, Fusion)

### 6.1 Full-Text Search Zero Recall
**Symptom**: Multi-phrase queries return nothing; single-word queries work fine

**Root Cause**: `plainto_tsquery` ANDs all tokens; multi-phrase input creates impossible condition

**Fix**: Build OR of AND phrase groups
```python
# Split into phrases and create OR groups
phrases = ["farmers market", "organic produce"]
groups = [" & ".join(phrase.split()) for phrase in phrases]
tsquery = " | ".join(groups)  # "(farmers & market) | (organic & produce)"

# Use in query
sql = text("""
    SELECT * FROM products
    WHERE to_tsvector('english', name || ' ' || description) @@ to_tsquery('english', :tsquery)
""")
result = conn.execute(sql, {"tsquery": tsquery})
```

**Prevention**: Log phrases + final tsquery; add integration test for known multi-phrase hit

### 6.2 Confusing Score Interpretation
**Symptom**: Misinterpreting fused scores vs semantic cosine similarity

**Root Cause**: RRF (Reciprocal Rank Fusion) overwrote semantic score field without renaming

**Fix**: Use distinct field names
```python
# Separate fields for different score types
results = {
    'semantic_score': 0.85,      # Cosine similarity
    'fts_score': 0.92,            # Full-text search rank
    'fused_score': 0.88           # RRF combined score
}
```

**Prevention**: Explicit logging of stage counts + fusion formula; document score types

### 6.3 High False Negatives in RAG
**Symptom**: Semantic search misses relevant documents; user queries return empty results

**Root Cause**: Similarity threshold too strict for diverse query patterns

**Fix**: Lower threshold empirically
```python
# Start with lower threshold
SIMILARITY_THRESHOLD = 0.5  # Was 0.7, too strict

# Track distribution during tuning
logger.info(f"Similarity scores: min={min(scores)}, max={max(scores)}, avg={sum(scores)/len(scores)}")
```

**Prevention**: Track similarity score distribution during tuning; test with diverse queries

---

## 7. PostgreSQL + Apache AGE (Graph Database)

### 7.1 Core Principles
1. Prefer 3-arg `cypher(:graph, $$query$$, $$)` if available; fallback to 2-arg
2. Entire Cypher body inside one dollar-quoted block; only `:graph` bound outside
3. Separate engines: one for vector ops, one for AGE (avoids extension interference)
4. Normalize apostrophes to `'` before embedding large text
5. Use positional ORDER BY when alias resolution fails

### 7.2 Cypher Function Signature Mismatch
**Symptom**: `function cypher(...) does not exist`

**Root Cause**: Apache AGE version mismatch (2-arg vs 3-arg signature)

**Fix**: Probe database and choose supported form
```python
# Probe for supported signature
probe = text("""
    SELECT count(*) FROM pg_proc 
    WHERE proname='cypher' AND pronargs=3
""")
has_3_arg = conn.execute(probe).scalar() > 0

# Use appropriate form
if has_3_arg:
    sql = text("SELECT * FROM cypher(:graph, $$MATCH (n) RETURN n$$, $$) AS (node agtype)")
else:
    sql = text("SELECT * FROM cypher(:graph, $$MATCH (n) RETURN n$$) AS (node agtype)")
```

**Prevention**: Keep probe helper function; document AGE version in README

### 7.3 Cypher Bind Parameter Errors
**Symptom**: `bind parameter ':IN_CATEGORY' does not exist` or similar token errors

**Root Cause**: SQLAlchemy parsing colon in Cypher body as bind parameter

**Fix**: Keep all colons inside dollar-quoted block
```python
# CORRECT: All Cypher inside $$...$$
cypher_body = "MATCH (p:Product)-[:IN_CATEGORY]->(c:Category) RETURN p"
sql = text("SELECT * FROM cypher(:graph, $$" + cypher_body + "$$, $$) AS (node agtype)")
conn.execute(sql, {"graph": "product_graph"})

# WRONG: Colon token outside dollar quotes
# sql = text("SELECT * FROM cypher(:graph, $$MATCH (p$$) WHERE p.type=:type")
```

**Prevention**: Never concatenate partial Cypher with stray colons outside dollar block

### 7.4 Dollar String Syntax Errors
**Symptom**: `unterminated dollar-quoted string` parse error

**Root Cause**: Unbalanced `$$` delimiters or multiple `$$` in body

**Fix**: Balance delimiters exactly once
```python
# Helper to validate
def validate_dollar_quotes(sql_str: str) -> bool:
    return sql_str.count("$$") == 2  # Should appear exactly twice

cypher_body = "MATCH (n) RETURN n"
sql = text("SELECT * FROM cypher(:graph, $$" + cypher_body + "$$, $$) AS (node agtype)")
assert validate_dollar_quotes(sql.text)
```

**Prevention**: Centralize Cypher query builder; validate dollar quote count

### 7.5 Apostrophe Syntax Errors in Text
**Symptom**: Mid-batch failure with syntax error in Cypher string literals

**Root Cause**: Raw `'` (curly apostrophe) in nested quoting breaks syntax

**Fix**: Sanitize text before formatting
```python
def sanitize_text(text: str | None) -> str:
    """Replace curly apostrophes with straight quotes."""
    return "" if not text else text.replace("'", "'")

# Use in Cypher
description = sanitize_text(product.description)
cypher = f"CREATE (p:Product {{description: '{description}'}})"
```

**Prevention**: Centralize sanitizer for all text inputs

### 7.6 ORDER BY Alias Resolution Failure
**Symptom**: `could not find rte for column` when using ORDER BY with alias

**Root Cause**: Set-returning function alias not visible in ORDER BY scope

**Fix**: Use positional ORDER BY
```python
# CORRECT: Positional reference
sql = text("""
    SELECT product_id, score 
    FROM cypher(:graph, $$...$$, $$) AS (product_id uuid, score float)
    ORDER BY 2 DESC  -- Position 2 = score column
""")

# WRONG: Alias reference (may fail)
# ORDER BY score DESC
```

**Prevention**: Adopt positional ORDER BY in shared AGE query helpers

### 7.7 Vector + AGE Extension Interference
**Symptom**: Odd `@>` operator errors or agtype parsing failures

**Root Cause**: Mixed extensions (pgvector + age) on same connection causing state interference

**Fix**: Separate database engines
```python
# Engine for vector operations (pgvector)
vector_engine = create_engine(DATABASE_URL)

# Engine for graph operations (AGE)
age_engine = create_engine(DATABASE_URL, poolclass=NullPool)

@event.listens_for(age_engine, "connect")
def load_age(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("LOAD 'age';")
    cursor.execute("SET search_path = ag_catalog, public;")
    cursor.close()
```

**Prevention**: Always isolate vector queries from AGE queries using separate engines

### 7.8 agtype Quoted String Values
**Symptom**: Values returned as `"uuid-string"` with quotes instead of plain string

**Root Cause**: agtype wrapper includes quotes in string representation

**Fix**: Strip quotes when extracting
```python
def unwrap_agtype_string(value: Any) -> str:
    """Remove agtype string quotes."""
    return str(value).strip('"')

# Use when processing results
product_id = unwrap_agtype_string(row.product_id)
```

**Prevention**: Create utility unwrap function for agtype value extraction

### 7.9 Canonical AGE Query Pattern
```python
# Complete pattern with all best practices
cypher_body = """
    MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
    WHERE p.price < 100
    RETURN p.product_id AS product_id, p.name AS name
"""

sql = text("""
    SELECT product_id, name
    FROM cypher(:graph, $$""" + cypher_body + """$$, $$) 
    AS (product_id uuid, name text)
    ORDER BY 2
""")

with age_engine.connect() as conn:
    rows = conn.execute(sql, {"graph": "product_graph"}).fetchall()
    
for row in rows:
    product_id = unwrap_agtype_string(row.product_id)
    name = str(row.name)
```

**Smoke Test**:
```python
# Quick validation that AGE is working
test_sql = text("""
    SELECT 1 FROM cypher(:g, $$MATCH (n) RETURN n LIMIT 1$$, $$) 
    AS (x agtype)
""")
conn.execute(test_sql, {"g": graph_name})
```

---

## 8. Multi-Agent Architecture

### 8.1 Graph Search Service Isolation
**Symptom**: AGE queries fail after vector operations; extension state errors

**Root Cause**: Shared engine contamination between pgvector and AGE extensions

**Fix**: Use fresh engine with proper initialization
```python
def _get_fresh_age_engine():
    """Create isolated engine for AGE operations."""
    engine = create_engine(DATABASE_URL, poolclass=NullPool)
    
    @event.listens_for(engine, "connect")
    def configure_age(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("LOAD 'age';")
        cursor.execute("SET search_path = ag_catalog, public;")
        cursor.close()
    
    return engine
```

**Prevention**: Factory method for AGE engine; never reuse vector engine for graph operations

### 8.2 Parameter Array Binding
**Symptom**: Errors with `= ANY(ARRAY[...])` syntax in queries

**Root Cause**: String interpolation of list instead of proper parameter binding

**Fix**: Use named parameter with list
```python
# CORRECT: Bind list directly
product_ids = ["uuid1", "uuid2", "uuid3"]
sql = text("SELECT * FROM products WHERE product_id = ANY(:product_ids)")
result = conn.execute(sql, {"product_ids": product_ids})

# WRONG: String interpolation
# sql = text(f"SELECT * FROM products WHERE product_id = ANY(ARRAY{product_ids})")
```

**Prevention**: Always bind Python lists directly; never string-format array literals

---

## 9. Development Best Practices

### 9.1 Post-Refactor Validation
**Action**: Run syntax check immediately
```bash
python -m py_compile src/**/*.py
```

**Why**: Catches indentation/syntax errors before runtime

### 9.2 Debugging Empty Results
**Action**: Log constructed queries/filters
```python
logger.debug(f"FTS tsquery: {tsquery}")
logger.debug(f"SQL (first 200 chars): {str(sql)[:200]}")
```

**Why**: Faster diagnosis than stepping through complex logic

### 9.3 Invariant Assertions
**Action**: Assert critical invariants early
```python
assert len(embedding_vector) == EXPECTED_DIM, "Dimension mismatch"
assert container_id is not None, "Container ID required for download"
```

**Why**: Fail fast vs silent skip/error propagation

### 9.4 UI Event Consistency
**Action**: Emit domain events after state mutations
```typescript
// After backend state change
eventBus.dispatch('resource-created', { id: newResource.id });
eventBus.dispatch('resource-selected', { id: newResource.id });
```

**Why**: Keeps UI synchronized with backend state

---

## 10. Quick Reference Cheat Sheet

**Environment**:
- Load `.env` in tests: `load_dotenv()` in `conftest.py`
- Integration tests: explicit path loading before imports

**Azure OpenAI**:
- Realtime: omit `type`, `model`, `output_modalities` for Azure
- Code Interpreter: use `file_ids` not `files`
- Output files: extract from `annotations` not `outputs`
- Continuation: replace input with tool outputs only, never extend
- Response ID: capture from EVERY response, not just first

**PostgreSQL + AGE**:
- Cypher: prefer 3-arg; fallback 2-arg; only `:graph` bound outside `$$`
- Separate engines: vector (pgvector) vs graph (AGE)
- Positional ORDER BY for set-returning functions
- Sanitize apostrophes: `'` → `'`

**Search & Retrieval**:
- FTS: OR of AND phrase groups `(a & b) | (c & d)`
- Embeddings: assert dimensions match DB vector column
- Thresholds: tune empirically, track distribution

**Frontend**:
- Voice/WebSocket: singleton manager outside component lifecycle
- Iframe sources: explicit absolute URLs for cross-origin content
- Events: dispatch after every backend state mutation

**MCP Development**:
- FastMCP: always call `super().__init__(base_url=None)` in TokenVerifier subclass
- Artifacts: public endpoints for iframe loading (UUID + TTL security)

**Data Safety**:
- Gate TRUNCATE behind environment check
- Use UPSERT or staging swap for production

---

## 11. Update Policy

**Rules**:
1. Replace sections when updating—never append duplicates
2. Edit existing entries for superseded rules (don't add new ones)
3. Add new error only if it represents a NEW root cause
4. Consolidate similar errors into single entry with variants
5. Keep code examples minimal but complete` | Always use absolute URLs for cross-origin iframe sources |
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



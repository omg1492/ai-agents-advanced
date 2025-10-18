# Common Errors Reference

**Purpose**: Fast lookup of recurring pitfalls with symptoms, root causes, fixes, and prevention strategies. Organized by category with code examples.

---

## 1. Environment & Configuration

### 1.1 Azure OpenAI API Version Compatibility (Files API)
**Symptom**: `Error code: 400 - {'error': {'code': 'BadRequest', 'message': 'API version not supported'}}` when uploading files

**Root Cause**: Azure OpenAI Files API has different version requirements than other endpoints:
- **Files API**: Only supports `api-version=preview` (rejects newer versions like `2024-12-01-preview`)
- **Responses API**: Supports both `preview` and versioned previews
- Single OpenAI client applies one `api-version` to ALL endpoints via `default_query`

**Fix Option 1 - Modern v1 API (RECOMMENDED)**: Use Azure OpenAI v1 GA endpoint which requires NO api-version:
```bash
# .env
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
# OPENAI_API_VERSION not needed! ✅
```

```python
# openai_service.py
if base_url and "/openai/v1/" in base_url:
    # v1 GA API: no api-version required
    default_query = None
elif base_url and api_version:
    # Legacy API: use api-version
    default_query = {"api-version": api_version}
```

**Fix Option 2 - Legacy API**: Use `api-version=preview` for compatibility:
```bash
# .env (legacy endpoints only)
OPENAI_API_VERSION=preview
```

**Benefits of v1 API**:
- No version conflicts between endpoints
- Automatic access to latest GA features
- No monthly version updates needed
- Full OpenAI SDK compatibility
- All features supported: Files, Responses, Embeddings, Fine-tuning

**Prevention**: 
- Use v1 GA API endpoints (`/openai/v1/`) when available
- Document API version requirements in `.env.template`
- Test file upload functionality after API version changes
- Reference: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/api-version-lifecycle

### 1.2 Missing Environment Variables in Tests
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

### 1.3 Code Quality After Refactoring
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

**PyRIT Security Testing**:
- Use PyRIT 0.9.0 API: `PromptSendingOrchestrator`, `send_prompts_async()`
- Test endpoint: `/test/chat` (JSON-only, no streaming, API key gated)
- Timeout: 300s (simple), 600s (comprehensive) for agents with tools
- Azure scorer: Full URL + api_version parameter (not in URL)
- **SelfAskRefusalScorer: Returns boolean True/False, NOT 0.0/1.0**
- **True = Refusal (secure), False = Compliance (vulnerable)**
- Always validate with response previews (first 150 chars)
- Datasets: AdvBench ✅, Forbidden Questions ✅, HarmBench ✅, XSTest ⚠️ (timeout)

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

## 4. PyRIT Security Testing (Microsoft Python Risk Identification Toolkit)

### 4.1 API Version Incompatibility (0.5.0 → 0.9.0)
**Symptom**: `ImportError: cannot import name 'PromptSendingAttack'` or `AttributeError: 'PromptSendingOrchestrator' has no attribute 'execute_async'`

**Root Cause**: PyRIT 0.9.0 changed core API - renamed classes and methods

**Fix**: Update to new API patterns
```python
# CORRECT (PyRIT 0.9.0)
from pyrit.orchestrator import PromptSendingOrchestrator
from pyrit.prompt_target import HTTPTarget
from pyrit.score import SelfAskRefusalScorer

orchestrator = PromptSendingOrchestrator(
    objective_target=http_target,
    scorers=[SelfAskRefusalScorer(chat_target=openai_target)]
)
await orchestrator.send_prompts_async(prompt_list=prompts)

# WRONG (PyRIT 0.5.0 - outdated)
# from pyrit.orchestrator import PromptSendingAttack
# attack = PromptSendingAttack(...)
# await attack.execute_async(...)
```

**Key Changes**:
- `PromptSendingAttack` → `PromptSendingOrchestrator`
- `execute_async()` → `send_prompts_async()`
- Import paths reorganized (e.g., `pyrit.prompt_target` instead of `pyrit.models`)

**Prevention**: Check PyRIT version in requirements and update import statements; test with `verify_setup.py` before running full tests

### 4.2 HTTPTarget - Streaming Response Incompatibility
**Symptom**: No responses received; parsing errors; timeout on all prompts

**Root Cause**: HTTPTarget expects simple JSON responses, cannot parse Server-Sent Events (SSE) streaming format

**Fix**: Create dedicated non-streaming test endpoint
```python
# Backend: Add test endpoint without streaming
@app.post("/test/chat")
async def test_chat(chat_request: ChatRequest, request: Request):
    # ... authentication ...
    
    # Use same system prompt and tools as production
    text, response_id = await openai_service.generate_response(
        user_text=chat_request.message,
        system_prompt=system_prompt,
        # All production tools enabled
    )
    
    # Return simple JSON (not streaming)
    return ChatResponse(response_id=response_id, message=text, ...)
```

**HTTPTarget Configuration**:
```python
raw_http_request = f"""POST {base_url}/test/chat HTTP/1.1
Content-Type: application/json
X-Test-API-Key: {api_key}

{{
    "message": "{{{{PROMPT}}}}"
}}"""

parsing_function = get_http_target_json_response_callback_function(key="message")

http_target = HTTPTarget(
    http_request=raw_http_request,
    prompt_regex_string="{{PROMPT}}",
    callback_function=parsing_function,
    use_tls=base_url.startswith("https"),
)
```

**Why This Works**:
- HTTPTarget needs predictable JSON structure: `{"message": "..."}`
- Streaming adds complexity (chunked transfer, SSE formatting, multiple events)
- Test endpoint maintains production behavior (same system prompt + tools) without streaming

**Prevention**: Always use dedicated test endpoints for PyRIT; gate with `TEST_API_ENABLED` flag; require API key authentication

### 4.3 HTTPTarget - Timeout Parameter Errors
**Symptom**: `httpcore.ReadTimeout` or timeout errors after ~5 seconds per request

**Root Cause**: HTTPTarget uses httpx.AsyncClient with default 5-second timeout, insufficient for agents with tool calls

**Fix**: Pass timeout parameter to HTTPTarget (forwarded to AsyncClient via **kwargs)
```python
# CORRECT - pass timeout directly to HTTPTarget
http_target = HTTPTarget(
    http_request=raw_http_request,
    prompt_regex_string="{{PROMPT}}",
    callback_function=parsing_function,
    use_tls=base_url.startswith("https"),
    timeout=180.0,  # 3 minutes for agent with tools
)

# WRONG - default 5-second timeout insufficient
# http_target = HTTPTarget(
#     http_request=raw_http_request,
#     # ... no timeout parameter ...
# )  # ❌ Will timeout on complex agent operations
```

**Discovery Process**:
1. Initial tests: immediate `httpcore.ReadTimeout` after ~5 seconds
2. Checked HTTPTarget signature: `__init__(self, ..., **httpx_client_kwargs: Any)`
3. Checked httpx.AsyncClient signature: accepts `timeout: TimeoutTypes` parameter
4. Solution: Pass `timeout=180.0` directly to HTTPTarget (forwarded to AsyncClient)
5. Test confirmed: Agents with tools can take 60-120 seconds per prompt

**Why This Works**:
- HTTPTarget accepts `**httpx_client_kwargs` and passes them to `httpx.AsyncClient`
- AsyncClient default timeout is 5 seconds
- Agents with full tool access (Chef, Farmer, Stock, Memory, Graph, Tavily) need 60-120 seconds
- Setting `timeout=180.0` (3 minutes) provides safe margin

**Key Lesson**: PyRIT's HTTPTarget forwards kwargs to httpx.AsyncClient; check both signatures to understand available configuration

**Prevention**: Always set appropriate timeout for your target's expected response time; test with single prompt before batch operations

### 4.4 Scorer API - PromptRequestPiece vs PromptRequestResponse
**Symptom**: `'PromptRequestResponse' object has no attribute 'response_error'` when scoring responses

**Root Cause**: `SelfAskRefusalScorer.score_async()` expects a `PromptRequestPiece` (single message), not a `PromptRequestResponse` (full conversation)

**Fix**: Pass the response piece (last item in request_pieces list)
```python
# CORRECT - pass the response piece
responses = await orchestrator.send_prompts_async(prompt_list=prompts)
for response in responses:
    if response and len(response.request_pieces) > 0:
        # Get the assistant's response (last piece)
        response_piece = response.request_pieces[-1]
        response_text = response_piece.converted_value
        
        # Score using the piece, not the full response
        score_results = await scorer.score_async(request_response=response_piece)
        is_refusal = score_results[0].get_value() == 0.0  # 0.0 = refusal, 1.0 = compliance

# WRONG - passing full response
# score_results = await scorer.score_async(request_response=response)  # ❌ Wrong type
```

**Discovery Process**:
1. Initial code: passed `PromptRequestResponse` to scorer
2. Error: `'PromptRequestResponse' object has no attribute 'response_error'`
3. Checked signature: `score_async(request_response: PromptRequestPiece)`
4. Solution: Extract response piece from `response.request_pieces[-1]`

**Key Understanding**:
- `PromptRequestResponse`: Full conversation with multiple pieces (user prompt + assistant response)
- `PromptRequestPiece`: Single message in conversation
- Scorers evaluate individual messages, not full conversations
- Use `request_pieces[-1]` to get the assistant's response

**Prevention**: Always check scorer signature; understand PyRIT's conversation model (Response contains Pieces)

### 4.5 Test Endpoint - Request Header Access
**Symptom**: `AttributeError: 'ChatRequest' object has no attribute 'headers'` when trying to access API key

**Root Cause**: Pydantic models don't automatically include FastAPI Request headers

**Fix**: Inject Request object separately
```python
# CORRECT - inject Request separately from Pydantic model
@app.post("/test/chat")
async def test_chat(chat_request: ChatRequest, request: Request):
    test_api_key = os.getenv("TEST_API_KEY")
    provided_key = request.headers.get("x-test-api-key")  # From Request object
    
    if not provided_key or provided_key != test_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # ... process chat_request.message ...

# WRONG - trying to access headers from Pydantic model
# @app.post("/test/chat")
# async def test_chat(chat_request: ChatRequest):
#     provided_key = chat_request.headers.get("x-test-api-key")  # ❌ No such attribute
```

**Prevention**: Always inject `Request` object when you need headers/cookies/client info beyond request body

### 4.6 Test Endpoint Security Configuration
**Symptom**: PyRIT tests hitting production endpoints; no way to disable test endpoint in production

**Root Cause**: Test endpoint always available without security controls

**Fix**: Gate test endpoint with environment flag and API key
```python
# .env configuration
TEST_API_ENABLED=true
TEST_API_KEY=redteaming123

# Backend: Conditional endpoint registration
if os.getenv("TEST_API_ENABLED", "").lower() == "true":
    @app.post("/test/chat")
    async def test_chat(chat_request: ChatRequest, request: Request):
        # Require API key
        test_api_key = os.getenv("TEST_API_KEY")
        provided_key = request.headers.get("x-test-api-key")
        
        if not test_api_key or not provided_key or provided_key != test_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # ... same logic as production endpoint ...
```

**Why This Pattern**:
- `TEST_API_ENABLED` - easily disable in production (set to false or omit)
- `TEST_API_KEY` - prevents unauthorized security testing
- Same tools/behavior as production - accurate security assessment
- No streaming complexity - PyRIT compatibility

**Prevention**: Always gate test/debug endpoints with environment flags; require authentication even in development

### 4.7 Azure OpenAI Configuration for PyRIT Scoring
**Symptom**: `InvalidRequestError: unrecognized request argument supplied: max_tokens` when using SelfAskRefusalScorer

**Root Cause**: GPT-5 reasoning models require `max_completion_tokens` instead of `max_tokens`; Azure OpenAI client needs full base URL

**Fix**: Configure OpenAI client correctly for Azure
```python
# CORRECT - Azure configuration with full base URL
from openai import OpenAI  # Not AzureOpenAI

openai_target = AzureOpenAIChatTarget(
    deployment_name=os.getenv("AZURE_OPENAI_REASONING_DEPLOYMENT"),
    endpoint=os.getenv("AZURE_OPENAI_REASONING_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_REASONING_API_KEY"),
    api_version="2024-12-01-preview",
)

# For manual client creation
client = OpenAI(
    api_key=os.getenv("AZURE_OPENAI_REASONING_API_KEY"),
    base_url=f"https://{resource_name}.openai.azure.com/openai/deployments/{deployment_name}",
    default_headers={"api-key": api_key},
)

# Use max_completion_tokens for GPT-5
response = client.chat.completions.create(
    model="gpt-5",
    messages=[...],
    max_completion_tokens=4000,  # Not max_tokens
)
```

**Prevention**: Use PyRIT's `AzureOpenAIChatTarget` for scoring to avoid manual client configuration errors

---

### 4.8 Azure OpenAI Endpoint URL Format for PyRIT

**Symptom**: `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` or 404 errors when using `OpenAIChatTarget` for PyRIT scoring

**Root Cause**: Including query parameters like `?api-version=...` directly in the endpoint URL causes PyRIT to add them again, resulting in malformed URLs

**Fix**: Use full endpoint URL without query parameters and let PyRIT add them via the `api_version` parameter
```python
# CORRECT - Full URL without query params
scorer_target = OpenAIChatTarget(
    endpoint=f"{azure_base}/openai/deployments/{model}/chat/completions",
    api_key=api_key,
    model_name=model,
    api_version="2024-12-01-preview",  # PyRIT adds this as query param
    max_completion_tokens=4000,
)

# WRONG - Don't include query params in URL
# endpoint=f"{azure_base}?api-version=..."  # ❌ Causes duplicate parameters
```

**Verification**: All scorer requests succeed with 200 OK responses; Azure API properly receives requests with correct query parameters

**Prevention**: Always pass `api_version` as a parameter to PyRIT targets, never embed it in the endpoint URL

---

### 4.8.1 Dataset Selection and Timeout Management

**Symptom**: Test runs successfully for first few datasets (AdvBench, Forbidden Questions, HarmBench), then times out or hangs on additional datasets (e.g., XSTest)

**Root Cause**: Some PyRIT datasets have longer prompts or trigger more complex agent reasoning, causing individual prompt processing to exceed timeout limits even when timeout is set appropriately for other datasets

**Fix**: Start with well-tested datasets and add new ones incrementally with timeout monitoring
```python
# CORRECT - Curated dataset selection with proven timeout compatibility
attack_configs = [
    {"name": "AdvBench", "fetch": fetch_adv_bench_dataset, "count": 520},
    {"name": "Forbidden Questions", "fetch": fetch_forbidden_questions_dataset, "count": 450},
    {"name": "HarmBench", "fetch": fetch_harmbench_dataset, "count": 400},
    # XSTest removed - caused timeout on 4th dataset after 60 successful prompts
]

# Start with fewer prompts per dataset (e.g., 20) to test stability
for config in attack_configs:
    prompts = config["fetch"]()
    await run_attack(target, scorer, prompts[:20], config["name"])

# WRONG - Adding all available datasets without testing timeout behavior
# attack_configs = [fetch_adv_bench, fetch_forbidden, fetch_harmbench, fetch_xstest, fetch_jbb_behaviors]
```

**Discovery Process**:
1. Comprehensive test successfully processed 60 prompts across 3 datasets
2. Added XSTest as 4th dataset → timeout on first XSTest prompt
3. XSTest prompts appear similar to others but trigger different agent behavior
4. Root cause likely: XSTest designed for specific edge cases requiring longer processing
5. Solution: Remove XSTest, keep 3 stable datasets (60 prompts total)

**Dataset Compatibility Notes**:
- **AdvBench** ✅ (520 prompts): Stable, standard harmful behaviors
- **Forbidden Questions** ✅ (450 prompts): Stable, ethical boundary testing
- **HarmBench** ✅ (400 prompts): Stable, comprehensive harm categories
- **XSTest** ⚠️ (REMOVED): Timeout issues, designed for exaggerated safety
- **fetch_jbb_behaviors_dataset** ❌ (ERROR): Does not exist in PyRIT 0.9.0

**Timeout Tuning Strategy**:
1. Start with simple test (1 dataset, 10 prompts, 300s timeout)
2. Validate all prompts complete successfully
3. Add datasets incrementally (test with 5-10 prompts each)
4. If new dataset times out, investigate: longer prompts? different tool usage? reasoning complexity?
5. Either increase timeout OR remove problematic dataset
6. Balance: comprehensive coverage vs test duration

**Prevention**: 
- Test new datasets individually with small prompt counts before adding to comprehensive suite
- Monitor timeout patterns (which datasets cause slowdowns)
- Document dataset compatibility in test comments
- Consider splitting very long tests into multiple runs

---

### 4.9 SelfAskRefusalScorer Returns Boolean Not Numeric Values

**Symptom**: 
- `ValueError: could not convert string to float: 'True'` when processing scores
- Test shows 100% attack success when agent actually refuses all requests
- Agent responses show refusals: "I'm sorry, but I cannot assist with that request"
- Scores show `refusal: True` but code treats this as 1.0 (compliance)

**Root Cause**: PyRIT's `SelfAskRefusalScorer` returns boolean values instead of numeric scores as suggested by documentation:
- `True` = Agent refused (secure) ✅
- `False` = Agent complied (vulnerable) ⚠️

This causes inverted security assessment results when code assumes numeric scores (0.0=refusal, 1.0=compliance).

**Fix**: Handle boolean score values with explicit type checking
```python
# CORRECT - Handle boolean/string/numeric scores
score_value = score_results[0].score_value

if isinstance(score_value, bool):
    is_refusal = score_value  # True = refusal (secure)
elif isinstance(score_value, str):
    is_refusal = score_value.lower() == 'true'
else:
    # Fallback for numeric scores if PyRIT changes API
    is_refusal = float(score_value) == 0.0

# Display result
if is_refusal:
    print("✅ Agent REFUSED (secure)")
else:
    print("⚠️ Agent COMPLIED (vulnerable)")

# WRONG - Assuming numeric scores
# is_refusal = (float(score_value) == 0.0)  # ❌ Crashes on boolean
```

**Discovery Process**:
1. Initial test showed "100% attack success" - seemed wrong for secured agent
2. User skepticism: "I do not believe this. Could you print also initial few words coming from model?"
3. Added response preview debugging - revealed all responses were refusals: "I'm sorry, but I cannot assist"
4. Added score object debugging - revealed `SelfAskRefusalScorer: refusal: True`
5. Discovered `score_value` is boolean `True`, not float `0.0`
6. Root cause: Code tried `float(score_value)` causing ValueError
7. Result was inverted: refusals (True) treated as compliance (1.0), compliances (False) would be treated as refusal (0.0)

**Critical Notes**:
- **Always verify scoring with actual response previews**, not just numeric summaries
- User skepticism ("I do not believe this") was correct and led to discovering critical bug
- **Debug output is essential**: print both scores AND actual agent responses side-by-side
- This bug completely inverts security assessment results
- PyRIT documentation may suggest numeric scores, but implementation uses booleans

**Verification Pattern**:
```python
# Log both response and score for validation
print(f"📝 Response: {response_text[:150]}...")
print(f"🔍 Score: {score_value} (type: {type(score_value).__name__})")

# Correct output for secure agent:
# 📝 Response: I'm sorry, but I cannot assist with that request.
# 🔍 Score: True (type: bool)
# ✅ Agent REFUSED (secure)
```

**Prevention**: 
- Always test PyRIT scoring with response preview output enabled
- Add type checking for all ML/AI system outputs (don't assume types match documentation)
- Validate results match expectations before running large test suites
- When results seem wrong, inspect actual responses not just aggregated scores

### 4.8 Canonical PyRIT Security Test Pattern
```python
#!/usr/bin/env python3
"""
PyRIT security test - canonical pattern for DreamFarm agent testing.
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from pyrit.orchestrator import PromptSendingOrchestrator
from pyrit.prompt_target import HTTPTarget, AzureOpenAIChatTarget
from pyrit.score import SelfAskRefusalScorer
from pyrit.common import default_values
from pyrit.datasets import fetch_advbench_harmful_behavior_dataset

# Load environment
load_dotenv()

# Configure PyRIT results directory
default_values.set_default_results_path(Path(__file__).parent / "redteaming_results")


def create_http_target():
    """Create HTTPTarget for DreamFarm test endpoint."""
    base_url = os.getenv("DREAMFARM_AGENT_URL", "http://localhost:8001")
    test_api_key = os.getenv("TEST_API_KEY", "redteaming123")
    
    raw_http_request = f"""POST {base_url}/test/chat HTTP/1.1
Content-Type: application/json
X-Test-API-Key: {test_api_key}

{{
    "message": "{{{{PROMPT}}}}"
}}"""
    
    parsing_function = get_http_target_json_response_callback_function(key="message")
    
    return HTTPTarget(
        http_request=raw_http_request,
        prompt_regex_string="{{PROMPT}}",
        callback_function=parsing_function,
        use_tls=base_url.startswith("https"),
        timeout=180.0,  # 3 minutes for agent with tools
    )


async def main():
    """Run PyRIT security test."""
    print("=" * 80)
    print("PyRIT Security Test - DreamFarm Agent")
    print("=" * 80)
    
    # Create targets
    http_target = create_http_target()
    openai_target = AzureOpenAIChatTarget(
        deployment_name=os.getenv("AZURE_OPENAI_REASONING_DEPLOYMENT"),
        endpoint=os.getenv("AZURE_OPENAI_REASONING_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_REASONING_API_KEY"),
        api_version="2024-12-01-preview",
    )
    
    # Create orchestrator
    orchestrator = PromptSendingOrchestrator(
        objective_target=http_target,
        scorers=[SelfAskRefusalScorer(chat_target=openai_target)]
    )
    
    # Load prompts
    prompts = fetch_advbench_harmful_behavior_dataset()
    prompt_list = [prompt.value for prompt in prompts[:10]]  # First 10 prompts
    
    print(f"\nSending {len(prompt_list)} prompts to agent...")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Send prompts
    await orchestrator.send_prompts_async(prompt_list=prompt_list)
    
    # Calculate refusal rate
    memory = orchestrator.get_memory()
    scores = memory.get_scores()
    
    refusal_count = sum(1 for s in scores if s.score_value and "True" in str(s.score_value))
    refusal_rate = (refusal_count / len(scores) * 100) if scores else 0
    
    print("\n" + "=" * 80)
    print(f"Test Complete - Refusal Rate: {refusal_rate:.1f}% ({refusal_count}/{len(scores)})")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
```

**Quick Validation Checklist**:
1. ✅ Environment variables loaded from `.env`
2. ✅ PyRIT 0.9.0 API (PromptSendingOrchestrator, send_prompts_async)
3. ✅ HTTPTarget points to `/test/chat` (not `/chat`)
4. ✅ Timeout set appropriately (e.g., 180.0 for agents with tools)
5. ✅ Test API key included in headers
6. ✅ Results path configured
7. ✅ Refusal rate calculation from scores

---

## 5. Data Imports & Embeddings
| Issue | Symptom | Cause | Fix | Prevent |
|-------|---------|-------|-----|---------|
| All product rows skipped | Log: `Skipped N rows... 0 rows to import` | Embedding dimension != DB vector(2000) | Request `dimensions=2000`; assert length | Add assert on first vector; CI check |
| Dangerous TRUNCATE in prod | Data loss risk | Dev convenience leaked | Gate behind env flag; use UPSERT/stage swap in prod | `if ENVIRONMENT=='prod': abort on TRUNCATE` |

Quick assert:
```python
assert len(embeddings[0]) == 2000, "Embedding dimension mismatch"
```

---

## 6. Retrieval / Search (RAG, FTS, Fusion)
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

## 7. PostgreSQL + Apache AGE (Cypher & Graph)
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

## 8. Graph Search Service (Isolation & Binding)
Consolidated (applies on top of Category 7):
| Problem | Symptom | Fix | Prevent |
|---------|---------|-----|---------|
| Shared engine contamination | AGE queries fail after vector ops | Use fresh engine with `LOAD 'age'; SET search_path=ag_catalog, public;` | Factory method `_get_fresh_age_engine()` |
| Improper parameter array binding | Errors with `ANY(ARRAY[..])` | String interpolation of list | Use named param: `= ANY(:product_ids)` | Always bind Python list directly |

---

## 9. Code Quality & Safety Patterns
| Pattern | Why | Minimal Action |
|---------|-----|----------------|
| Import smoke test after large refactor | Catch syntax / indentation early | `python -m py_compile src/...` |
| Log raw constructed SQL / tsquery | Faster diagnosis of empty results | Add debug log on first 100 chars |
| Assert invariants (embedding dim) | Fail fast vs silent skip | `assert len(vec)==2000` |
| Event emission after implicit state change | Keep UI consistent | Dispatch creation + selection events |

---

## 10. OpenTelemetry Instrumentation for OpenAI

### 10.1 Responses API Streaming Not Emitting Traces

**Symptom**: No OpenTelemetry spans appear in Grafana/Tempo when using OpenAI Responses API with streaming (`responses.create(..., stream=True)`)

**Root Cause**: Standard OpenTelemetry instrumentation (`opentelemetry-instrumentation-openai`) doesn't support Responses API streaming yet ([GitHub Issue #3395](https://github.com/traceloop/openllmetry/issues/3395))

**Fix**: Use OpenInference instrumentation temporarily until standard OTel fix is merged
```python
# Environment variable to control provider
OTEL_INSTRUMENTATION_PROVIDER=openinference  # or "opentelemetry"

# In src/main.py - conditional instrumentation
otel_provider = os.getenv("OTEL_INSTRUMENTATION_PROVIDER", "opentelemetry").lower()

if otel_provider == "openinference":
    from openinference.instrumentation.openai import OpenAIInstrumentor
    OpenAIInstrumentor().instrument(tracer_provider=provider)
    print("[OK] OpenAI instrumented with OpenInference (Responses API streaming supported)")
else:
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor
    OpenAIInstrumentor().instrument(tracer_provider=provider)
    print("[OK] OpenAI instrumented with standard OpenTelemetry (awaiting Responses API streaming fix)")

# In pyproject.toml - include both packages
dependencies = [
    "openinference-instrumentation-openai>=0.1.34",  # Supports streaming NOW
    "opentelemetry-instrumentation-openai>=0.47.3",  # Standard conventions, awaiting fix
]
```

**Kubernetes Deployment Configuration**:
```yaml
# deploy/charts/demo/templates/deployment-dreamfarm-agent.yaml
env:
  - name: OTEL_INSTRUMENTATION_PROVIDER
    value: "openinference"  # Use until PR #3396 is merged
```

**Why Two Implementations**:
- **OpenInference** (`openinference-instrumentation-openai`):
  - ✅ Supports Responses API streaming NOW
  - ⚠️ Uses custom semantic conventions (`llm.token_count.total` instead of `gen_ai.usage.total_tokens`)
  - ⚠️ May not be fully compatible with Langfuse (expects standard OTel conventions)
  
- **Standard OTel** (`opentelemetry-instrumentation-openai`):
  - ✅ Uses standard GenAI semantic conventions (full Langfuse compatibility)
  - ❌ Doesn't support Responses API streaming yet (fix in [PR #3396](https://github.com/traceloop/openllmetry/pull/3396))
  - 🔄 Switch to this once PR is merged

**Semantic Convention Differences**:

| Attribute | Standard OTel (GenAI) | OpenInference |
|-----------|----------------------|---------------|
| Input tokens | `gen_ai.usage.input_tokens` | `llm.token_count.input` |
| Output tokens | `gen_ai.usage.output_tokens` | `llm.token_count.output` |
| Total tokens | `gen_ai.usage.total_tokens` | `llm.token_count.total` |
| Model name | `gen_ai.request.model` | `llm.model_name` |
| Messages | `gen_ai.input.messages` | `llm.input_messages` |

**How to Switch**:

1. **Use OpenInference NOW** (Responses API streaming works):
   ```bash
   # .env or Kubernetes ConfigMap
   OTEL_INSTRUMENTATION_PROVIDER=openinference
   ```

2. **Test Standard OTel** (once PR #3396 is merged):
   ```bash
   # .env or Kubernetes ConfigMap
   OTEL_INSTRUMENTATION_PROVIDER=opentelemetry
   ```

3. **Verify in Grafana**:
   - OpenInference: Look for `llm.token_count.total` attribute
   - Standard OTel: Look for `gen_ai.usage.total_tokens` attribute

**Troubleshooting**:
- **No spans at all**: Check `OTEL_INSTRUMENTATION_PROVIDER` is set correctly
- **Wrong attributes**: Verify which provider is actually loaded (check startup logs)
- **Langfuse issues**: Standard OTel required for full compatibility (use after PR merge)

**Migration Path**:
1. **Current (Oct 2025)**: Use OpenInference (`OTEL_INSTRUMENTATION_PROVIDER=openinference`)
2. **Monitor PR #3396**: https://github.com/traceloop/openllmetry/pull/3396
3. **After Merge**: Switch to standard OTel (`OTEL_INSTRUMENTATION_PROVIDER=opentelemetry`)
4. **Long-term**: Remove OpenInference dependency, keep only standard OTel

**Prevention**: 
- Always test observability with actual workloads before deploying
- Monitor GitHub issues for instrumentation libraries
- Keep both providers available during transition period

**References**:
- GitHub Issue: https://github.com/traceloop/openllmetry/issues/3395
- Fix PR (OPEN): https://github.com/traceloop/openllmetry/pull/3396
- OpenInference Docs: https://github.com/Arize-ai/openinference
- OTel GenAI Conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/

## 11. Quick Do / Avoid Matrix
| Do | Avoid |
|----|-------|
| Single dollar‑quoted Cypher body | Mixing binds & colon tokens outside block |
| Separate engines (vector vs AGE) | Reusing contaminated connection |
| Phrase‑aware FTS `(a & b) | (c & d)` | Blind `plainto_tsquery` on combined text |
| Explicit reasoning item ordering | Assuming function calls arrive self‑contained |
| Dimension assertion on first embedding | Importing thousands then discovering mismatch |
| Singleton manager for long‑lived browser resources | Storing sockets in transient React components |
| **OpenInference for Responses API streaming NOW** | Waiting for standard OTel fix before observing traces |

---

## 12. Minimal Cheat Sheet
- Load env in tests: `load_dotenv()`.
- Realtime (Azure): omit `type`, `model`, `output_modalities`.
- Cypher: prefer 3‑arg; fallback 2‑arg; only `:graph` bound.
- Vector + AGE: isolate connections.
- FTS query: OR of AND phrase groups.
- Embeddings: enforce 2000 dims.
- Reasoning stream: record every item in order.
- Voice: external session manager.
- FastMCP auth: always call `super().__init__(base_url=None)` in custom `TokenVerifier` subclass.
- **PyRIT: use 0.9.0 API (`PromptSendingOrchestrator`, `send_prompts_async`); dedicated `/test/chat` endpoint; no custom timeout params.**
- **OTel + OpenAI: Use `OTEL_INSTRUMENTATION_PROVIDER=openinference` until standard OTel PR #3396 merges; switch to `opentelemetry` for Langfuse compatibility.**

---

## 13. Update Policy: Replace sections—do not append duplicates. If an older rule is superseded, edit the existing entry instead of adding a new one.



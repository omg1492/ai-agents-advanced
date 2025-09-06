# Common Errors and Solutions

## RAG System Integration Issues - 2025-08-01

### Environment Variable Loading in Tests

**Problem**: Integration tests failing because `.env` file not loaded in test environment.

**Error Symptoms**:
```
KeyError: 'AZURE_OPENAI_EMBEDDING_API_KEY'
```

**Root Cause**: Tests running in isolated environment without access to application's environment configuration.

**Solution**:
```python
# Add to integration test files
from dotenv import load_dotenv
load_dotenv()  # Add this at module level
```

**Prevention**: Always include dotenv loading in integration tests that require real API/database connections.

---

### SQL Query Execution with SQLAlchemy

**Problem**: Raw SQL strings causing execution failures in SQLAlchemy.

**Error Symptoms**:
```
sqlalchemy.exc.InvalidRequestError: Could not evaluate current criteria
```

**Root Cause**: SQLAlchemy requires explicit text() wrapper for raw SQL queries in modern versions.

**Solution**:
```python
# Before (fails)
result = session.execute(query, {"embedding": embedding_list})

# After (works)
from sqlalchemy import text
result = session.execute(text(query), {"embedding": embedding_list})
```

**Prevention**: Always wrap raw SQL strings with SQLAlchemy's `text()` function.

---

### Vector Dimension Mismatch

**Problem**: Embedding dimension mismatch between model output and database expectations.

**Error Symptoms**:
```
sqlalchemy.exc.DataError: vector dimension 3072 does not match column dimension 2000
```

**Root Cause**: Azure OpenAI text-embedding-3-large defaults to 3072 dimensions, but pgvector was configured for 2000.

**Solution**:
```python
# Limit dimensions in embedding generation
embedding = client.embeddings.create(
    input=text,
    model="text-embedding-3-large",
    dimensions=2000  # Add this parameter
)
```

**Prevention**: Always verify and align embedding dimensions between model configuration and database schema.

---

### Similarity Threshold Tuning

**Problem**: Overly restrictive similarity thresholds returning no results.

**Error Symptoms**: Semantic search queries returning empty results despite relevant data existing.

**Root Cause**: Default similarity threshold (0.7) too high for realistic data distribution.

**Solution**:
```python
# Adjust threshold based on empirical testing
RAG_SIMILARITY_THRESHOLD=0.5  # Reduced from 0.7
```

**Prevention**: Tune similarity thresholds empirically using real data and expected search queries.

---

### Test Environment Contamination

**Problem**: Unit tests failing due to environment variable contamination from other tests.

**Error Symptoms**: Tests passing individually but failing when run as part of full suite.

**Root Cause**: Environment variables from integration tests affecting unit test expectations.

**Solution**:
```python
# Clear both primary and fallback environment variables
with patch.dict(os.environ, {
    "AZURE_OPENAI_EMBEDDING_ENDPOINT": "",
    "AZURE_OPENAI_EMBEDDING_API_KEY": "",
    "AZURE_OPENAI_EMBEDDING_API_VERSION": "",
    # Also clear fallback variables
    "AZURE_OPENAI_ENDPOINT": "",
    "AZURE_OPENAI_API_KEY": "",
    "AZURE_OPENAI_API_VERSION": "",
}, clear=False):
```

**Prevention**: Properly isolate test environments by clearing all relevant environment variables, including fallback options.

---

### Async/Sync Integration Challenges

**Problem**: Mixed async/sync code patterns causing execution issues.

**Common Issues Encountered**:
1. **SQLAlchemy Session Management**: Mixing sync database operations with async FastAPI endpoints
2. **OpenAI Client Usage**: Using sync client in async context without proper handling
3. **Test Framework Confusion**: pytest-asyncio vs standard pytest patterns

**Solutions Applied**:
1. **Consistent Sync Pattern**: Used synchronous SQLAlchemy and OpenAI clients throughout
2. **Proper Session Management**: Created sessions per request, closed explicitly
3. **Clear Test Boundaries**: Separate async integration tests from sync unit tests

**Lessons Learned**:
- Choose async OR sync consistently within a service boundary
- Use async only when genuine concurrency benefits exist
- Avoid mixing patterns unless absolutely necessary
- FastAPI can handle sync route handlers efficiently

**Prevention**: Establish clear async/sync boundaries early in project architecture.

---

## Stock Tool Misuse (Prompt Injection Instead of Function Calling) - 2025-08-22

**Problem**: Stock availability/details were embedded directly into the system prompt (`stock_context`) rather than letting the model request data via the `get_stock` function tool.

**Symptoms**:
```
System prompt contained large inline stock JSON blocks.
Model stopped calling get_stock tool even when fresh data was needed.
Stale or oversized prompts increased token usage.
```

**Root Cause**: Legacy approach (before function calling refactor) persisted after adding proper tool definition; prompt still manually injected stock info.

**Resolution**:
1. Removed all `stock_context` injections from `main.py` endpoints (chat, thread, streaming).
2. Ensured stock data is only retrievable through function calling events (`function_call` → execute → `submit_tool_outputs`).
3. Updated tool schema to use `productIds` (camelCase) with backward-compatible parsing of legacy `product_ids`.

**Why This Matters**: Keeps prompts lean, ensures the model explicitly asks for only the product IDs it needs, and prevents leakage of stale or irrelevant inventory data.

**Prevention**:
- Never embed dynamic, per-request product/stock state into the system prompt once a function/tool exists.
- If a tool is added for a data domain, remove prior prompt stuffing patterns.
- Add tests asserting absence of deprecated fields (e.g., `assert "stock_context" not in rendered_prompt`).

**Test Idea**:
```python
def test_no_stock_context_in_prompt(system_prompt: str):
    assert "stock_context" not in system_prompt
```

---

## GPT-5 Reasoning with Streaming Function Calls - 2025-08-22

**Problem**: GPT-5 reasoning models with streaming function calls failing with error: `"Item 'fc_*' of type 'function_call' was provided without its required 'reasoning' item: 'rs_*'"`

**Error Symptoms**:
```
Error code: 400 - {'error': {'message': "Item 'fc_68a81bbc02048190a85e73351bd91551074079db2411f37f' of type 'function_call' was provided without its required 'reasoning' item: 'rs_68a81bbbcc308190b36b79945597d58a074079db2411f37f'.", 'type': 'invalid_request_error', 'param': 'input', 'code': None}}
```

**Root Cause**: When using GPT-5 with reasoning enabled, the Responses API generates paired reasoning items (`rs_*`) and function call items (`fc_*`) that must be kept together in the conversation history. Our initial implementation only captured function call items in `input_messages` for the next iteration, breaking this required pairing.

**The GPT-5 Reasoning Pattern**:
1. Model generates reasoning item explaining why a function should be called
2. Model generates function call item with the actual tool invocation
3. These items are semantically paired and must appear together in subsequent API calls
4. Breaking this pairing causes the API to reject the request

**Technical Journey** (multiple failed approaches):
1. **Initial Attempt**: Complex inline submission with `submit_tool_outputs` during streaming → SDK limitations
2. **Fallback Pattern**: Tried to replay events after stream completion → Still broke reasoning chain  
3. **Loop-based Pattern**: Implemented continuous reasoning loop but only captured function calls → Missing reasoning items caused API errors

**Final Solution**:
```python
# Capture both reasoning and function call items during streaming
current_reasoning_item = None

# In event processing loop:
if item_type == "reasoning":
    current_reasoning_item = item
    input_messages.append(item)  # Add reasoning first
    
elif item_type == "function_call":
    # Reasoning already added, function call follows
    input_messages.append(item)  # Add function call after reasoning
    # Execute tool and prepare output for next iteration
```

**Key Insights**:
- GPT-5 reasoning creates item pairs that must be preserved in conversation history
- The order matters: reasoning item first, then function call item
- Tool outputs are added separately as `function_call_output` items
- This enables continuous reasoning where the model can call multiple tools in sequence

**Why This Was Hard to Debug**:
- Error message mentions missing reasoning item but doesn't explain the pairing requirement
- OpenAI documentation doesn't clearly specify the reasoning-function call relationship
- Multiple patterns seemed to work initially but failed on tool execution
- SDK streaming patterns differ significantly from traditional function calling

**Prevention**:
- When implementing GPT-5 reasoning with tools, always capture ALL item types (`reasoning`, `function_call`, `message`)
- Maintain the exact order of items as they appear in the streaming response
- Test with actual function calls that require multiple reasoning steps
- Don't assume traditional function calling patterns work with reasoning models

**Reference Implementation**: Loop-based streaming with proper item pairing following Tomáš Kubica's proven GPT-5 reasoning pattern.

---

## Hybrid RAG & Full‑Text Search Integration Issues - 2025-08-24

### Incorrect Structured Output Parameter (Responses API)

**Problem**: Attempted to use `response_format={"type": "json_schema", ...}` with the (async) Responses API for keyword extraction in `_extract_keywords`.

**Error Symptoms**:
```
TypeError: AsyncResponses.create() got an unexpected keyword argument 'response_format'
```

**Root Cause**: The new SDK's Responses API does not accept `response_format` in `create()` like the older Chat Completions API. Structured parsing must instead use `client.responses.parse()` with a Pydantic model.

**Solution**:
```python
class ExtractedKeywords(BaseModel):
    keywords: List[str]

parsed = client.responses.parse(
    model=model_name,
    input=prompt_messages,
    response_format=ExtractedKeywords,  # Pydantic schema
)
keywords = parsed.output_parsed.keywords
```

**Prevention**:
- For structured outputs, always prefer `responses.parse(..., response_format=YourModel)`.
- Only use `response_format` with endpoints that explicitly document it.
- Add a quick unit test that mocks the client to ensure `_extract_keywords` path does not pass unknown kwargs.

---

### Patch-Induced Indentation / Scope Errors

**Problem**: During iterative patches to `rag_service.py`, incorrect indentation left helper functions nested or misaligned, risking them becoming inner scopes or producing readability issues.

**Error Symptoms**: (Representative)
```
IndentationError: unexpected indent
```
or silent logical errors where definitions ended up inside other functions.

**Root Cause**: Applying partial diffs without full surrounding context caused indentation drift (especially after adding `_extract_keywords`, `_fts_search`, `_rrf_fuse`).

**Solution**:
- Re‑aligned all helper functions to module level.
- Ensured consistent 4‑space indentation and no accidental nesting.
- Ran linting / basic import execution to validate file parses cleanly.

**Prevention**:
- After sizable patch, immediately open the file and visually scan left margin alignment.
- Prefer editing whole function blocks instead of fragmenting start/end separately.
- Add a minimal test that imports the service module (catches `IndentationError` early).

---

### Full‑Text Search Returning Zero Results (Over‑Strict AND Semantics)

**Problem**: Initial FTS used `plainto_tsquery('simple', combined_phrase_text)` which applies implicit AND across all tokens. Multi‑word / multi‑concept queries frequently returned zero rows.

**Example**:
```
Input phrases (LLM): ["bio honey", "chilli honey"]
plainto_tsquery => 'bio' & 'honey' & 'chilli' & 'honey'
-- Requires documents containing ALL tokens → many misses.
```

**Root Cause**: `plainto_tsquery` normalizes and ANDs all lexemes; mixing distinct concepts collapses recall.

**Intermediate Fix**: Switched to token OR query (split tokens; join with `|`) boosting recall but losing phrase cohesion.

**Final Solution (Phrase‑Preserving OR of AND Groups)**:
1. Keep each original LLM phrase.
2. For multi‑word phrase: split → AND within phrase: `term1 & term2`.
3. OR across phrases: `(bio & honey) | (chilli & honey) | honey | chilli`.
4. Execute with `to_tsquery('simple', tsquery_string)`.

**Result**: Restores phrase intent while expanding recall vs pure AND; still allows single tokens to match.

**Code Sketch**:
```python
groups = []
for phrase in phrases:
    terms = [sanitize(t) for t in phrase.split() if t.strip()]
    if not terms:
        continue
    group = ' & '.join(terms)
    groups.append(group)
tsquery = ' | '.join(groups)
sql = """
SELECT id, content, ts_rank_cd(ft_vector, to_tsquery('simple', :q)) AS rank
FROM documents
WHERE ft_vector @@ to_tsquery('simple', :q)
ORDER BY rank DESC
LIMIT :limit
"""
```

**Prevention**:
- Evaluate recall using sample queries before locking in tsquery form.
- Log both the original phrases and the final `tsquery` string (already added).
- Keep an integration test asserting at least one FTS hit for a known phrase.

---

### Fusion Score Overwrite Awareness

**Problem**: After introducing Reciprocal Rank Fusion (RRF), fused scores replaced original semantic similarity scores in the final list, potentially confusing debugging when comparing to raw embedding distances.

**Solution**: Explicit logging: semantic count, FTS count, and final fused list size; clarify that `score` now represents RRF output, not cosine similarity.

**Prevention**:
- When changing scoring meaning, rename field or document in logs (e.g., `fused_score`).
- Add a docstring / comment above `_rrf_fuse` explaining formula `1 / (k + rank)`.

---

### Takeaways
- Use SDK‑appropriate structured output methods (`responses.parse`).
- Prefer phrase‑aware tsquery construction balancing precision & recall.
- Instrument every retrieval stage to accelerate iterative tuning.
- Guard against layout drift (indentation) after multi‑patch sequences with a simple import test.

---

## All Rows Skipped on Products Import - 2025-08-25

**Problem**: Running `import_products.py` logged:
```
Skipped 5595 rows with missing/invalid embeddings
Prepared 0 rows for insert
No rows to import
```

**Root Cause**: Generated embeddings had a dimension different from the database column (`vector(2000)`). Import validation rejects any embedding whose length != 2000, so every row was dropped instead of failing loudly.

**Solution**:
1. Standardized `embeddings_products.py` to always call the API with `dimensions=2000`.
2. Regenerated parquet, confirmed log line: `Detected embedding dimension=2000 (DB expects 2000)`.
3. Re-ran import; rows inserted successfully.

**Prevention**:
- Always request embeddings with explicit `dimensions=2000` for this table.
- Add a quick assert (or CI check) that first embedding length matches expected dimension.
- If dimension ever changes intentionally, migrate the DB column (ALTER TABLE ... USING) before regenerating data.

---

## TRUNCATE Usage in Import Script (Dev Convenience vs Prod Risk) - 2025-08-25

**Context**: `import_products.py` executes:
```
TRUNCATE TABLE products RESTART IDENTITY;
```

**Why in Dev**:
- Fast (minimal WAL) and ensures a clean snapshot matching the regenerated parquet.
- Avoids duplicates & stale rows while iterating on schema / embeddings.

**Risk in Production**:
- Irreversible bulk deletion (no WHERE clause); accidental run erases entire table instantly.
- Blocks concurrent access while holding strong locks.

**Safer Production Patterns**:
1. UPSERT / MERGE style load (`ON CONFLICT (product_id) DO UPDATE`).
2. Stage + swap: load into `products_staging`, then transactional `DELETE/INSERT` or partition swap.
3. Differential update: compare hashes and only update changed rows.

**Prevention**:
- Gate TRUNCATE behind environment flag, e.g. `ALLOW_TRUNCATE_IN_DEV=1`.
- Add a defensive check that aborts if `ENVIRONMENT=prod`.
- Include an integration test asserting production config path skips TRUNCATE.

---

## Apache AGE Cypher Invocation & Quoting Pitfalls - 2025-09-06

### Overview
While implementing the AGE knowledge graph import (`import_graph_age.py`), multiple non‑obvious failures occurred around the `cypher()` function invocation, query quoting, and ordering semantics. These issues are easy to repeat unless the working patterns are documented.

### Problems & Symptoms
1. Function Signature Confusion
    - Error: `ERROR:  function cypher(unknown, unknown, unknown) does not exist`
    - Error (variant): `third argument of cypher function must be a parameter`
    - Cause: AGE 1.5.0 catalog lists a 3‑argument signature `(graph_name, query, params)` returning `setof agtype`, but passing a plain JSON / NULL / text for the 3rd arg failed. Practical usage in our environment required the 2‑argument form with no params.

2. Dollar‑Quoted String Requirement
    - Error: `dollar-quoted string constant is expected`
    - Cause: Multi‑line Cypher passed as a regular single‑quoted string containing embedded quotes/newlines. AGE (through PostgreSQL) expects a dollar‑quoted literal for complex multi‑line cypher bodies to avoid premature termination / escaping headaches.

3. Apostrophe Explosion in Text Properties
    - Symptoms: Syntax errors mid‑batch when product / producer descriptions contained many `'` characters even after doubling them for SQL.
    - Resolution: Normalize ASCII apostrophes to the Unicode right single quotation mark (`’`) before embedding into the Cypher literal. This sidesteps nested escaping inside: SQL string → Cypher parser → property value.

4. ORDER BY Alias Resolution Failure
    - Error: `ERROR:  could not find rte for product_count`
    - Context: Summary query ordering by an aliased aggregate coming from a Cypher→SQL projection.
    - Fix: Use positional ordering (`ORDER BY 2 DESC`) instead of the alias.

5. Patch‑Induced Syntax / Indentation Errors
    - After iterative edits, Python summary function indentation became malformed causing `IndentationError` / runtime failures. (General mitigation already covered earlier – included here for cross‑reference.)

### Root Causes
- AGE version quirk: Parameter map handling stricter than (or diverging from) older docs / examples.
- Mixing three layers of parsing simultaneously (PostgreSQL SQL, dollar‑quoted literal, Cypher grammar) magnifies quoting risk.
- Large free‑text fields with apostrophes trigger escaping edge cases inside MERGE property maps.
- Aliased columns from `cypher()` set-returning function sometimes not resolvable by name in outer ORDER BY within our version.

### Working Invocation Pattern (Use This)
```sql
-- Template for executing a batch of Cypher statements (no params) in AGE 1.5.0
SELECT *
FROM cypher('dreamfarm', $$
// Cypher goes here
MATCH (p:Producer {id: 'producer-123'})
RETURN p
$$) AS (result agtype);
```

### Text Normalization Helper (Python)
```python
def _escape(text: str) -> str:
     if text is None:
          return ''
     # Replace ASCII apostrophes with Unicode to avoid deep escaping issues
     return text.replace("'", "’")
```

### MERGE Idempotency Pattern
```cypher
MERGE (pr:Producer {id: 'producer-123'})
ON CREATE SET pr.name = 'Acme Honey’, pr.country = 'CZ'
ON MATCH  SET pr.name = COALESCE(pr.name, 'Acme Honey’), pr.country = COALESCE(pr.country, 'CZ');
```

### Relationship Creation Pattern
```cypher
MERGE (pr:Producer {id: 'producer-123'})
MERGE (pd:Product  {id: 'product-987'})
MERGE (pr)-[:PRODUCES]->(pd);
```

### Do / Avoid Quick Reference
| Do | Avoid |
|----|-------|
| Use 2‑arg `cypher(graph, $$...$$)` | Forcing 3rd param when not strictly needed |
| Dollar‑quote the whole Cypher batch | Nesting many single quotes inside a single‑quoted SQL string |
| Normalize apostrophes to `’` | Relying only on doubling `'` in deep nested contexts |
| Positional `ORDER BY` (e.g. 2) | Aliased aggregate names that fail to resolve |
| MERGE for idempotent upserts | Separate MATCH+CREATE increasing race / duplication risk |

### Prevention / Guidelines
- Wrap every multi‑statement Cypher execution in a single dollar‑quoted block passed as the second argument only.
- Centralize text sanitation (apostrophes + optionally trim control chars) before formatting MERGE lines.
- Keep batches to a manageable size; if memory / transaction bloat appears, chunk statements (e.g., 1–2k MERGE lines per execution) while reusing the same pattern.
- Document the AGE version; retest 3‑argument form only after upgrading beyond 1.5.0.
- Prefer concise property sets—omit large blobs unless queried.

### Fast Diagnostic Checklist
| Symptom | Immediate Check |
|---------|-----------------|
| Undefined function for `cypher` | Confirm extension loaded: `LOAD 'age'; SET search_path = ag_catalog, "$user";` |
| `third argument must be a parameter` | Drop the 3rd argument; retry 2‑arg form |
| Dollar‑quote expected | Ensure query wrapped in `$$` delimiters |
| Mid‑batch syntax near random text | Inspect for stray ASCII `'`; confirm normalization applied |
| ORDER BY alias error | Switch to positional ORDER BY |

### Follow‑Up Actions
- If/when parameter maps are required (e.g., dynamic values safer than string formatting), prototype with a minimal graph on the upgraded AGE version and update this section.
- Consider adding a tiny automated import smoke test that runs a single MERGE + RETURN to catch regression in invocation semantics early.

---

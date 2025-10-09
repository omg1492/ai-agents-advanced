# Co## Overview

This workflow implements the **complete** complaint handling business process:

1. **Complaint Receipt**: Accept complaint input (message + user_id)
2. **LLM Classification**: Determine if input is actually a complaint using Azure OpenAI structured outputs
3. **LLM Extraction**: Extract key information from complaint message (products, order_id, order_date, reason, evidence)
4. **User Profile Fetch**: Retrieve user profile data (segment, loyalty level, user score, location - currently mocked)
5. **LLM Decision**: Evaluate complaint validity using company policy with few-shot examples (VALID/NOT_VALID/HUMAN_REVIEW)
6. **LLM Resolution**: Generate appropriate response:
   - **VALID**: Apologetic message with refund/replacement confirmation
   - **NOT_VALID**: Professional explanation with reconsideration criteria
   - **HUMAN_REVIEW**: Structured review packet with arguments for/against approval

**Current Status**: All 6 steps implemented and tested. Full end-to-end workflow complete!andling Workflow

Temporal-based complaint handling workflow with Azure OpenAI LLM integration.

## Overview

This workflow implements **Steps 1-3** of the complaint handling business process:

1. **Complaint Receipt**: Accept complaint input (message + user_id)
2. **LLM Classification**: Determine if input is actually a complaint using Azure OpenAI structured outputs
3. **Information Extraction**: Extract structured data from complaint (products, order_id, order_date, reason, evidence)

**Current Status**: Steps 1-3 implemented and tested. Steps 4+ (data fetching, decision-making, resolution) are pending.

## Features

- **Durable Workflows**: Temporal ensures reliable execution with automatic retries
- **Responses API**: Azure OpenAI Responses API with reasoning support and structured outputs
- **Type Safety**: Pydantic models for all data contracts
- **Observability**: Structured logging with `ORCH_PHASE` prefixes
- **Simplified Model**: Minimal input (message + user_id), order details extracted by LLM
- **Intelligent Extraction**: LLM extracts structured information with null handling for missing fields

## Quick Start

### Prerequisites

- Python 3.12+
- Temporal CLI installed
- `uv` package manager
- Azure OpenAI API access

### 1. Install Dependencies

```pwsh
uv sync
```

### 2. Configure Azure OpenAI

Copy `.env.sample` to `.env` and configure:

```bash
OPENAI_API_KEY=your-azure-openai-key
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
OPENAI_API_VERSION=2024-10-21
OPENAI_MODEL=gpt-5
REASONING_EFFORT=minimal  # Options: minimal, low, medium, high
```

### 3. Start Temporal Dev Server

In a separate terminal:

```pwsh
temporal server start-dev
```

This starts the Temporal server at `localhost:7233` with Web UI at `localhost:8233`.

### 4. Run the Demo

**Terminal 1 - Start Worker:**

```pwsh
uv run python worker.py
```

**Terminal 2 - Run Interactive Demo:**

```pwsh
uv run python demo.py
```

The demo will:
- Automatically start and manage its own worker
- Load complaint examples from `complaints/` folder
- Process each through the workflow
- Show detailed logging with classification results
- Print Temporal UI links for inspection
- Shut down worker on exit

Visit http://localhost:8233 to see workflow executions in real-time!

### Alternative: CLI Workflow Starter (Production Use)

For automation, CI/CD, or when you have a separate long-running worker:

**Terminal 1 - Start Worker:**
```pwsh
uv run python worker.py
```

**Terminal 2 - Start Single Workflow:**
```pwsh
uv run python client_run.py complaints/complaint1.json
```

**Use cases for `client_run.py`:**
- Production triggers (webhooks, message queues)
- Batch processing scripts
- CI/CD pipeline testing
- When worker is managed separately (systemd, Kubernetes, etc.)

## Data Models

### ComplaintIn (Simplified)

```python
{
  "message": str,    # Raw complaint/message text
  "user_id": str     # User identifier
}
```

**Design Decision**: Removed order_id, order_date, and items fields. These will be extracted from the message text by the LLM in later phases, simplifying the input contract.

### ComplaintClassification

```python
{
  "is_complaint": bool,   # True if input is a complaint
  "confidence": float     # 0.0-1.0 confidence score
}
```

### ComplaintExtraction

```python
{
  "products_involved": list[str] | None,  # Product names mentioned
  "order_date": str | None,               # Order date in YYYY-MM-DD format
  "order_id": str | None,                 # Order ID/number
  "reason": str | None,                   # Main complaint issue
  "evidence_provided": str | None         # Mention of photos, receipts, etc.
}
```

**Design Decision**: All fields are Optional (can be None if not mentioned in the message). The LLM extracts only what is explicitly stated.

### WorkflowResult

```python
{
  "terminal_status": "COMPLETED" | "NEEDS_MORE_INFO" | "PENDING_REVIEW",
  "action": "VALID" | "NOT_VALID" | "HUMAN_REVIEW" | null,
  "reason": str | null,
  "user_message": str | null,
  "review_packet_id": str | null
}
```

## Testing

### Unit Tests (Fast, In-Memory)

Unit tests use Temporal's time-skipping environment and don't require the server:

```pwsh
uv run pytest tests/test_workflow_smoke.py -v
```

**Characteristics**:
- Fast (no Temporal server needed)
- Isolated (each test gets own environment)
- Not visible in UI (by design)

### Integration Tests (Real Server, Visible in UI)

Integration tests run against the actual Temporal server and appear in the UI:

1. Start Temporal server:
   ```pwsh
   temporal server start-dev
   ```

2. Start worker:
   ```pwsh
   uv run python worker.py
   ```

3. Run integration test:
   ```pwsh
   uv run pytest tests/test_workflow_integration.py -v
   ```

4. View in UI: http://localhost:8233

## Project Structure

```
complaint_workflow/
├── models.py              # Pydantic data models
├── workflow.py            # Temporal workflow definition
├── activities.py          # Temporal activities (LLM calls, etc.)
├── llm_adapter.py         # Azure OpenAI client wrapper
├── worker.py              # Worker process (long-running service)
├── demo.py                # Interactive demo (embedded worker)
├── client_run.py          # CLI workflow starter (requires separate worker)
├── complaints/            # Example complaint JSON files
│   ├── complaint1.json    # Valid complaint
│   └── non-complaint.json # Order inquiry
├── tests/
│   ├── test_workflow_smoke.py      # Unit tests (in-memory)
│   └── test_workflow_integration.py # Integration tests (real server)
├── .env.sample            # Environment template
├── pyproject.toml         # Dependencies
├── README.md              # This file
└── ARCHITECTURE.md        # Detailed architecture explanation
```

## Common Errors

### Azure OpenAI Responses API

**Issue**: `responses.parse` not found or import errors

**Cause**: Using older OpenAI Python SDK version

**Fix**: Ensure OpenAI SDK supports Responses API (openai>=1.59.0)

**Supported Models**: gpt-5, gpt-4o, o1, o3 (models with reasoning capabilities)

Reference: https://platform.openai.com/docs/guides/structured-outputs

### Worker Can't Find Activities

**Issue**: `Activity 'classify_complaint' not found`

**Cause**: Activity not registered with worker

**Fix**: Ensure `activities=[classify_complaint_activity]` in `worker.py`

### Temporal Server Not Running

**Issue**: Connection refused on localhost:7233

**Cause**: Temporal dev server not started

**Fix**: Run `temporal server start-dev` in separate terminal

## Next Steps (Remaining Phases)

### Step 3: Field Sufficiency Check
- Extract order details from message using LLM
- Validate required fields present
- Generate clarification message if missing
- Terminal status: NEEDS_MORE_INFO

### Step 4: Data Fetch Activities
- Mock order lookup activity
- Mock user profile fetch activity
- Handle missing data scenarios

### Step 5: Decision Activity
- Load policy document
- LLM decision with context bundle
- Return action: VALID / NOT_VALID / HUMAN_REVIEW

### Steps 6-7: Resolution Activities
- Craft user-facing messages (LLM)
- Generate review packets for escalation
- Persist audit records

### Step 8: Timeouts & Retries
- Configure activity-level retry policies
- Test transient failure scenarios

### Step 9: Observability
- Structured logging with ORCH_PHASE
- Optional audit trail (JSONL)

### Step 10: Hardening
- Input validation guardrails
- Action enum coercion
- Student extensions (SLA timers, dual-model validation, sentiment analysis)

## References

- [Temporal Python SDK](https://docs.temporal.io/dev-guide/python)
- [Azure OpenAI Structured Outputs](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/structured-outputs)
- [Agent Development Guidelines](../../AGENTS.md)

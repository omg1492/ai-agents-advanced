# Complaint Workflow - Temporal Orchestration Demo

AI-assisted complaint handling workflow using Temporal for durable execution with Azure OpenAI integration.

## Overview

This workflow demonstrates how to build reliable, multi-step business processes with AI decision-making. It processes customer complaints through a 6-phase pipeline: classification → extraction → profile enrichment → policy-based decision → resolution generation.

### Why Temporal?

- **Durable Execution**: Workflow state persists across restarts and failures
- **Automatic Retries**: Activities retry on transient errors with configurable backoff
- **Deterministic Replay**: Separates business logic (workflow) from side-effects (activities)
- **Observability**: Built-in Web UI for debugging and monitoring
- **Production-Ready**: Battle-tested by Uber, Netflix, Stripe for mission-critical workflows

## Workflow Phases

```
User Message
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Classification                                      │
│  ├─ LLM: Is this a complaint?                               │
│  └─ Output: is_complaint (bool), confidence (float)         │
└─────────────────────────────────────────────────────────────┘
    ↓
    ├─ NO → Return help center message (exit early)
    └─ YES → Continue ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Information Extraction                             │
│  ├─ LLM: Extract structured data from message               │
│  └─ Output: products, order_id, order_date, reason, evidence│
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: User Profile Fetch                                 │
│  ├─ Mock API: Retrieve customer history                     │
│  └─ Output: segment, loyalty, score, order/complaint counts │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Policy-Based Decision                              │
│  ├─ LLM: Evaluate with company policy + few-shot examples   │
│  └─ Output: action (VALID/NOT_VALID/HUMAN_REVIEW), reason   │
└─────────────────────────────────────────────────────────────┘
    ↓
    ├─ VALID → Phase 5a: Generate apology + refund message
    ├─ NOT_VALID → Phase 5a: Generate rejection explanation
    └─ HUMAN_REVIEW → Phase 5b: Generate review packet for operator
┌─────────────────────────────────────────────────────────────┐
│ Phase 5a: User Message Generation (VALID/NOT_VALID)        │
│  ├─ LLM: Craft appropriate customer response                │
│  └─ Output: subject, message, tone                          │
└─────────────────────────────────────────────────────────────┘
                          OR
┌─────────────────────────────────────────────────────────────┐
│ Phase 5b: Review Packet Generation (HUMAN_REVIEW)          │
│  ├─ LLM: Create structured case summary for human           │
│  └─ Output: summary, pros/cons, recommendation, priority    │
└─────────────────────────────────────────────────────────────┘
    ↓
Final Result: terminal_status, action, resolution
```

## Key Features

### 1. **Structured Outputs (Type-Safe)**
All LLM responses use Pydantic schemas with strict validation:
```python
class ComplaintClassification(BaseModel):
    is_complaint: bool
    confidence: float = Field(ge=0.0, le=1.0)
```

### 2. **Policy-Based Decision Making**
Decision phase includes:
- Embedded company policy (farm-to-table marketplace rules)
- 6 annotated few-shot examples
- Context: complaint details + customer profile (segment, loyalty, score, history)

### 3. **Deterministic Workflow**
- Workflow = pure orchestration logic (if/else, loops)
- Activities = side-effects (LLM calls, API requests, DB queries)
- State persists → workflow can pause/resume/retry safely

### 4. **Mock User Profile Service**
Deterministic hash-based profile generation (no external API needed for demo):
- Consistent profiles per user_id (same ID → same profile)
- Realistic segments: premium (20%), regular (50%), occasional (30%)
- Varying loyalty levels: platinum, gold, silver, bronze
- Synthetic order/complaint history

## Prerequisites

### 1. Temporal Server
Start local dev server:
```powershell
temporal server start-dev
```

Web UI will be available at: http://localhost:8233

### 2. Azure OpenAI Configuration
Create `.env` file (copy from `.env.sample`):
```env
OPENAI_API_KEY=your-azure-openai-key
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
OPENAI_API_VERSION=2024-10-21
OPENAI_MODEL=gpt-5
REASONING_EFFORT=minimal
```

**Requirements:**
- Azure OpenAI resource with GPT-5 (or GPT-4o) deployment
- Responses API support (api-version 2024-10-21 or later)

### 3. Python Environment
```powershell
# Install dependencies with uv
uv sync

# Verify installation
uv run python -c "import temporalio; print(temporalio.__version__)"
```

## Quick Start: Demo Mode

The easiest way to see the workflow in action:

```powershell
# Runs embedded worker + processes all example complaints
uv run python demo.py
```

**What happens:**
1. Loads 3 example complaints from `complaints/` folder
2. Starts embedded worker (auto-cleanup)
3. Processes each through full 6-phase workflow
4. Displays real-time progress with structured logging
5. Outputs final decisions and resolutions

**Example output:**
```
================================================================================
COMPLAINT WORKFLOW DEMO - Complete Implementation
================================================================================

✅ Connected to Temporal server at localhost:7233
🔧 Starting worker...
✅ Worker started on task queue: complaint-workflow-queue

================================================================================
🚀 Processing: complaint1.json
================================================================================
   Workflow ID: complaint-demo-complaint1
   View in UI: http://localhost:8233/namespaces/default/workflows/complaint-demo-complaint1

📤 Sending to workflow...
ORCH_PHASE=classify workflow_id=complaint-demo-complaint1
ORCH_PHASE=classify_complete workflow_id=complaint-demo-complaint1 is_complaint=True confidence=0.95
ORCH_PHASE=extract workflow_id=complaint-demo-complaint1
ORCH_PHASE=extract_complete workflow_id=complaint-demo-complaint1 order_id=ORD789 products=1 has_reason=True
ORCH_PHASE=fetch_user_profile workflow_id=complaint-demo-complaint1 user_id=user123
ORCH_PHASE=fetch_user_profile_complete workflow_id=complaint-demo-complaint1 segment=premium score=85.0 orders=42 complaints=1
ORCH_PHASE=decide workflow_id=complaint-demo-complaint1 user_score=85.0 segment=premium
ORCH_PHASE=decide_complete workflow_id=complaint-demo-complaint1 action=VALID confidence=0.92

✅ Workflow completed!
   Status: COMPLETED
   Action: VALID
   Reason: Clear product quality issue (broken glass jar) with safety concern. Evidence provided (photos). Excellent customer history (score 85, 42 orders, only 1 prior complaint). Auto-approve refund.
```

## Example Scenarios

### Scenario 1: Valid Complaint (Auto-Approve)
**File**: `complaints/complaint1.json`

**Input**:
```json
{
  "user_id": "user123",
  "message": "I received my order #ORD789 yesterday and the glass jar of artisan honey was completely shattered. Glass shards everywhere in the box. I have photos. This is dangerous and I'm very disappointed."
}
```

**Workflow path**: Classification ✓ → Extraction → Profile (premium, score 85) → **VALID** → Apology message

**Output**:
```
Subject: We're Taking Care of This - Full Refund Processed
Message: Dear Valued Customer, We sincerely apologize for receiving damaged products...
[Full refund confirmation, 3-5 business days]
```

---

### Scenario 2: Escalation to Human (HUMAN_REVIEW)
**File**: `complaints/complaint2.json`

**Input**:
```json
{
  "user_id": "user999",
  "message": "All the vegetables in my order were rotten and moldy. I have pictures. This is unacceptable!"
}
```

**Workflow path**: Classification ✓ → Extraction → Profile (occasional, score 28, suspicious pattern) → **HUMAN_REVIEW** → Review packet

**Output**:
```json
{
  "summary": "Quality complaint about rotten vegetables. Evidence mentioned. Low user score (28) with high complaint rate (3 complaints / 0 orders) raises fraud concern.",
  "arguments_for_approval": [
    "Food safety issue (rotten/moldy produce)",
    "Evidence mentioned (photos)",
    "Clear product quality defect"
  ],
  "arguments_against_approval": [
    "User score very low (28/100)",
    "Zero order history but 3 complaints (suspicious pattern)",
    "Possible fraud or serial complainer"
  ],
  "recommended_action": "Request additional verification (order receipt, photos) before approval. Consider account review.",
  "priority": "high"
}
```

---

### Scenario 3: Not a Complaint (Early Exit)
**File**: `complaints/non-complaint.json`

**Input**:
```json
{
  "user_id": "user456",
  "message": "Do you have organic tomatoes in stock? What varieties are available?"
}
```

**Workflow path**: Classification ✗ → **Early exit** (no further processing)

**Output**:
```
Reason: NOT_COMPLAINT
Message: Thank you for your inquiry. This doesn't appear to be a complaint. For product questions or orders, please visit our help center.
```

## Production Usage

For long-running production deployments (webhook consumers, queue processors):

### 1. Start Worker (separate process)
```powershell
# Terminal 1: Long-running worker
uv run python worker.py
```

Worker will:
- Connect to Temporal server
- Poll task queue: `complaint-workflow-queue`
- Execute workflows and activities
- Run until interrupted (Ctrl+C)

### 2. Trigger Workflows Programmatically
```python
# client_run.py (example - not included, show pattern)
from temporalio.client import Client
from models import ComplaintIn

async def submit_complaint(message: str, user_id: str):
    client = await Client.connect("localhost:7233")
    
    result = await client.execute_workflow(
        ComplaintWorkflow.run,
        ComplaintIn(message=message, user_id=user_id),
        id=f"complaint-{uuid.uuid4()}",
        task_queue="complaint-workflow-queue"
    )
    
    return result
```

### 3. Monitor in Web UI
Navigate to: http://localhost:8233

View:
- Workflow execution history (all 6 phases as events)
- Input/output for each activity
- Retry attempts and failures
- Workflow state snapshots

## Project Structure

```
complaint_workflow/
├── .env.sample              # Environment template
├── .python-version          # Python 3.12
├── pyproject.toml           # Dependencies (uv-managed)
├── README.md                # This file
│
├── models.py                # Pydantic data models
│   ├── ComplaintIn          # Input model
│   ├── ComplaintClassification
│   ├── ComplaintExtraction
│   ├── UserProfile
│   ├── ComplaintDecision
│   ├── UserMessage
│   ├── ReviewPacket
│   └── WorkflowResult       # Output model
│
├── workflow.py              # Temporal workflow (orchestration logic)
│   └── ComplaintWorkflow.run()
│
├── activities.py            # Temporal activities (side-effects)
│   ├── classify_complaint_activity
│   ├── extract_complaint_info_activity
│   ├── fetch_user_profile_activity
│   ├── decide_complaint_validity_activity
│   ├── generate_user_message_activity
│   └── generate_review_packet_activity
│
├── llm_adapter.py           # Azure OpenAI client wrapper
│   └── LLMAdapter           # Unified client pattern (same as agent)
│
├── worker.py                # Production worker process
├── demo.py                  # Self-contained demo (embedded worker)
│
└── complaints/              # Example complaint JSON files
    ├── complaint1.json      # Valid case (auto-approve)
    ├── complaint2.json      # Human review (escalation)
    └── non-complaint.json   # Early exit (not a complaint)
```

## Configuration

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | Azure OpenAI API key | (required) |
| `OPENAI_BASE_URL` | Azure endpoint (with `/openai/v1/` suffix) | (required) |
| `OPENAI_API_VERSION` | API version for Azure | `preview` |
| `OPENAI_MODEL` | Deployment/model name | `gpt-5` |
| `REASONING_EFFORT` | Reasoning effort level | `minimal` |

### Activity Configuration

**Timeout**: 30 seconds per activity (configurable in `activities.py`)

**Retry Policy**:
- Max attempts: 3
- Initial interval: 1 second
- Backoff coefficient: 2.0 (exponential)

## Logging & Observability

### Structured Logging
All activities log with `ORCH_PHASE=<phase>` prefix:

```
ORCH_PHASE=classify workflow_id=... is_complaint=True confidence=0.95
ORCH_PHASE=extract workflow_id=... order_id=ORD789 products=1
ORCH_PHASE=decide workflow_id=... action=VALID confidence=0.92
```

### Temporal Web UI
**Live inspection**: http://localhost:8233

Features:
- Event history (all activity calls)
- Input/output inspection
- Retry tracking
- Execution timeline
- State snapshots

### Workflow ID Pattern
```
complaint-demo-<scenario>        # Demo mode
complaint-prod-<uuid>            # Production
```

## Architecture Benefits

### 1. **Reliability**
- Automatic retry on transient failures (LLM timeouts, rate limits)
- State persistence (survives restarts, deploys)
- No lost complaints → every submission gets processed

### 2. **Auditability**
- Complete event history stored
- Every decision traceable (inputs + reasoning)
- Compliance-ready logs

### 3. **Testability**
- Activities are isolated units (easy to mock)
- Deterministic workflow logic (pure functions)
- Replay-based testing (time-travel debugging)

### 4. **Scalability**
- Horizontal worker scaling (add more worker processes)
- Task queue load balancing (automatic)
- No shared state between workers

### 5. **Evolvability**
- Add new phases without breaking running workflows
- Change activity implementation without touching workflow
- Schema versioning for backward compatibility

## Troubleshooting

### Issue: "Connection refused" when running demo
**Solution**: Start Temporal server first:
```powershell
temporal server start-dev
```

### Issue: "No module named 'openai'"
**Solution**: Install dependencies:
```powershell
uv sync
```

### Issue: "OPENAI_API_KEY not found"
**Solution**: Create `.env` file from template:
```powershell
Copy-Item .env.sample .env
# Then edit .env with your credentials
```

### Issue: Activities timing out
**Solution**: Check Azure OpenAI quota and increase timeout in `activities.py`:
```python
ACTIVITY_TIMEOUT = timedelta(seconds=60)  # Increase from 30
```

### Issue: "Workflow already started" error
**Solution**: Use unique workflow IDs or complete/terminate existing workflow in Web UI

## Advanced Topics

### Custom Policy
Edit the company policy in `llm_adapter.py` → `decide()` method:
```python
system_prompt = """You are a complaint validation system...

COMPANY POLICY:
[Your custom rules here]
"""
```

### Add New Activity Phase
1. Define Pydantic model in `models.py`
2. Implement activity in `activities.py`
3. Call from workflow in `workflow.py`
4. Register in worker (`worker.py` and `demo.py`)

### Production Deployment
- **Temporal Cloud**: Managed service (no ops)
- **Self-hosted**: Kubernetes + PostgreSQL/Cassandra backend
- **Worker deployment**: Docker containers, auto-scaling
- **Secrets**: Use secret manager (Azure Key Vault, AWS Secrets Manager)

## Related Resources

- [Temporal Documentation](https://docs.temporal.io/)
- [Lesson 07: Orchestration](../../lessons/L07_orchestration/README.md)
- [Main Design Document](../../docs/Design.md#181-complaint-handling-workflow)

## License

Part of the Advanced AI Applications course. See root README for details.

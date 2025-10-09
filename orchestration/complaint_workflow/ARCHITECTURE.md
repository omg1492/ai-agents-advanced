# Complaint Workflow Architecture

## Overview

This is a Temporal-based workflow system for processing customer complaints with AI classification.

## Component Roles

### Core Components

#### **workflow.py** - Orchestration Logic (The Brain)
```
Role: Defines WHAT steps to execute and in WHAT order
Restrictions: Must be deterministic (no random, no datetime.now(), no I/O)
Runs in: Temporal's sandbox (can replay from history)
```

**What it does:**
1. Receives complaint input
2. Calls activity to classify with LLM
3. Makes routing decisions based on classification
4. Returns final result

**Why deterministic?** Temporal can replay workflows from history to resume after crashes/restarts. Same inputs must always produce same outputs.

---

#### **activities.py** - Side Effects (The Hands)
```
Role: Executes non-deterministic operations (LLM calls, DB queries, HTTP)
Can: Fail, be retried, have timeouts
Runs in: Normal Python environment (no sandbox)
```

**What it does:**
- `classify_complaint_activity`: Calls Azure OpenAI to classify text
- Future: fetch_order_activity, fetch_user_activity, etc.

**Why separate?** Activities can be retried independently without replaying the entire workflow.

---

#### **worker.py** - The Execution Engine
```
Role: Long-running process that executes workflows and activities
Polling: Constantly asks Temporal "Do you have work for me?"
Registers: Which workflows and activities it can execute
```

**What it does:**
1. Connects to Temporal server
2. Registers `ComplaintWorkflow` and `classify_complaint_activity`
3. Polls the task queue: `complaint-workflow-queue`
4. Executes assigned tasks
5. Reports results back to Temporal

**When to run:** 
- In production: As a long-running service (systemd, Kubernetes, etc.)
- In development: In a separate terminal OR embedded in demo (see below)

---

### Client Components

#### **demo.py** - Interactive Demo (Self-Contained)
```
Role: Demonstrate workflow with embedded worker
User Experience: One command runs everything
Architecture: Starts worker, runs workflows, shuts down worker
```

**What it does:**
1. ✅ Starts its own worker in background
2. ✅ Loads complaint examples from JSON files
3. ✅ Executes workflows and waits for results
4. ✅ Shows detailed logging
5. ✅ Shuts down worker on exit

**Best for:** Development, testing, demonstrations

---

#### **client_run.py** - Simple Workflow Starter
```
Role: Start a single workflow from command line
Architecture: Requires separate worker already running
```

**What it does:**
1. Loads complaint from JSON file
2. Starts workflow execution
3. Prints result
4. Exits

**Best for:** Production triggers, CI/CD, manual testing

**Usage:**
```bash
# Terminal 1: Start worker
uv run python worker.py

# Terminal 2: Run workflow
uv run python client_run.py complaints/complaint1.json
```

---

### Supporting Files

#### **models.py** - Data Contracts
- Pydantic schemas for type safety
- Input: `ComplaintIn`
- Output: `WorkflowResult`, `ComplaintClassification`
- Enums: `TerminalStatus`, `Action`

#### **llm_adapter.py** - AI Integration
- Wraps Azure OpenAI Responses API
- Singleton pattern for reuse
- Handles structured outputs with Pydantic

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      USER INTERACTION                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────┐
        │         demo.py / client_run.py     │
        │  (Load JSON, start workflow)        │
        └─────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────┐
        │         TEMPORAL SERVER             │
        │  (Stores state, assigns tasks)      │
        └─────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────┐
        │            WORKER                   │
        │  (Polls for work, executes code)    │
        └─────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
        ┌───────────────────┐   ┌──────────────┐
        │   WORKFLOW        │   │  ACTIVITY    │
        │  (Orchestration)  │   │ (LLM Call)   │
        └───────────────────┘   └──────────────┘
                    │                   │
                    │                   ▼
                    │         ┌─────────────────┐
                    │         │  AZURE OPENAI   │
                    │         │ (Classification)│
                    │         └─────────────────┘
                    │                   │
                    └─────────┬─────────┘
                              ▼
        ┌─────────────────────────────────────┐
        │         WORKFLOW RESULT             │
        │  (Status, Action, Message)          │
        └─────────────────────────────────────┘
```

---

## Development Workflows

### Quick Demo (Recommended)
```bash
# Only need 2 terminals!

# Terminal 1: Temporal server
temporal server start-dev

# Terminal 2: Run demo (manages its own worker)
uv run python demo.py
```

### Traditional (Worker + Client)
```bash
# Terminal 1: Temporal server
temporal server start-dev

# Terminal 2: Long-running worker
uv run python worker.py

# Terminal 3: Start workflows
uv run python client_run.py complaints/complaint1.json
```

### Testing
```bash
# Unit tests (in-memory, fast)
uv run pytest tests/test_workflow_smoke.py -v

# Integration tests (real server, visible in UI)
uv run pytest tests/test_workflow_integration.py -v
```

---

## Why This Architecture?

### Separation of Concerns
- **Workflow**: Pure logic, deterministic, replayable
- **Activities**: Side effects, retryable, timeout-able
- **Worker**: Execution engine, scalable, resilient

### Benefits
1. **Resilience**: Workflows survive crashes and restarts
2. **Observability**: Full execution history in Temporal UI
3. **Scalability**: Add more workers to handle load
4. **Testability**: Time-skipping tests, unit vs integration
5. **Maintainability**: Clear boundaries between components

### Trade-offs
- **Learning Curve**: Temporal concepts (workflows, activities, determinism)
- **Complexity**: More moving parts than simple scripts
- **Infrastructure**: Requires Temporal server

---

## Common Questions

### Q: Why can't workflow.py call OpenAI directly?
**A:** Workflows must be deterministic for replay. External API calls are non-deterministic (network failures, timeouts, different responses). Activities isolate non-determinism.

### Q: Do I always need a separate worker?
**A:** No! `demo.py` embeds the worker. This is great for development. In production, run workers as separate services for better scaling and monitoring.

### Q: What happens if the worker crashes mid-workflow?
**A:** Temporal stores workflow state. When the worker restarts, it picks up where it left off. Activities can be retried.

### Q: Can I run multiple workers?
**A:** Yes! All workers poll the same task queue. Temporal distributes work among them. Great for horizontal scaling.

### Q: How do I debug workflows?
**A:** 
1. Check Temporal UI: http://localhost:8233
2. Look at workflow execution history (every step recorded)
3. Check worker logs for activity errors
4. Use `workflow.logger.info()` for debug logging

---

## Next Steps

When implementing remaining phases (Steps 3-10):
1. Add new activities to `activities.py`
2. Update workflow logic in `workflow.py`
3. Register new activities in `worker.py`
4. Update demo to test new features
5. Add tests for new behavior

Keep the architecture clean: workflows for orchestration, activities for side effects!

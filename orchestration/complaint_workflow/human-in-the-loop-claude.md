# Human-in-the-Loop (HITL) Extension

This document describes the extension of the complaint workflow to demonstrate **true human-in-the-loop** patterns using Temporal signals, queries, and wait conditions.

## Problem Statement

The current workflow terminates when `HUMAN_REVIEW` is needed:

```
Decision (HUMAN_REVIEW) → Generate Review Packet → Return PENDING_REVIEW → Workflow ENDS
```

This means:
- No mechanism to wait for human decision
- Cannot continue processing after human approves/rejects
- Cannot track the complete lifecycle in a single workflow execution

## Solution: Temporal HITL Patterns

### BPMN User Task Equivalent

In BPMN, a **User Task** pauses the process until a human completes an action. Temporal achieves the same with:

1. **Signal Handler** - Receives external input (human decision)
2. **workflow.wait_condition** - Pauses workflow until signal arrives
3. **Query Handler** - Allows checking workflow status without mutations

### New Flow Diagram

```
                                   ┌──────────────────────────────────────┐
                                   │         HUMAN_REVIEW Branch          │
                                   └──────────────────────────────────────┘
                                                    │
                                                    ▼
                                        ┌─────────────────────┐
                                        │ Generate Review     │
                                        │ Packet (LLM)        │
                                        └─────────────────────┘
                                                    │
                                                    ▼
                                        ┌─────────────────────┐
                                        │ Notify Reviewer     │
                                        │ (mock: log only)    │
                                        └─────────────────────┘
                                                    │
                                                    ▼
                              ┌─────────────────────────────────────────────┐
                              │  WAIT for Signal OR Timeout (10 min)        │
                              │  workflow.wait_condition(human_decision)    │
                              └─────────────────────────────────────────────┘
                                                    │
                     ┌──────────────────────────────┼──────────────────────────────┐
                     │                              │                              │
                     ▼                              ▼                              ▼
          ┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
          │    APPROVED     │            │    REJECTED     │            │    TIMEOUT      │
          │  (by human)     │            │  (by human)     │            │  (auto-escalate)│
          └─────────────────┘            └─────────────────┘            └─────────────────┘
                     │                              │                              │
                     ▼                              ▼                              ▼
          ┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
          │ Generate        │            │ Generate        │            │ Generate        │
          │ Approval Msg    │            │ Rejection Msg   │            │ Escalation Msg  │
          └─────────────────┘            └─────────────────┘            └─────────────────┘
                     │                              │                              │
                     ▼                              ▼                              ▼
              HUMAN_APPROVED                 HUMAN_REJECTED               TIMEOUT_ESCALATED
```

## Implementation Details

### New Data Models

```python
class HumanDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMEOUT_ESCALATED = "TIMEOUT_ESCALATED"

@dataclass
class HumanReviewInput:
    decision: HumanDecision
    reviewer_id: str
    reviewer_notes: Optional[str] = None
```

### Signal Handler (Receive Human Decision)

```python
@workflow.signal
def submit_human_decision(self, input: HumanReviewInput) -> None:
    """Receives human decision - fires and forgets, no return value"""
    self.human_decision = input
```

### Query Handler (Check Status)

```python
@workflow.query
def get_status(self) -> dict:
    """Returns current workflow state - read-only, cannot mutate"""
    return {
        "phase": self.current_phase,
        "awaiting_human": self.human_decision is None and self.review_packet is not None,
        "review_packet": self.review_packet
    }
```

### Wait Condition with Timeout

```python
HUMAN_REVIEW_TIMEOUT = timedelta(minutes=10)

# In workflow run method:
try:
    await asyncio.wait_for(
        workflow.wait_condition(lambda: self.human_decision is not None),
        timeout=HUMAN_REVIEW_TIMEOUT.total_seconds()
    )
except asyncio.TimeoutError:
    self.human_decision = HumanReviewInput(
        decision=HumanDecision.TIMEOUT_ESCALATED,
        reviewer_id="SYSTEM",
        reviewer_notes="Auto-escalated due to review timeout"
    )
```

## New Activities

| Activity | Purpose |
|----------|---------|
| `notify_reviewer_activity` | Mock notification (logs review packet details) |
| `generate_human_approved_message_activity` | Generate customer message after human approval |
| `generate_human_rejected_message_activity` | Generate customer message after human rejection |

## Demo Scripts

### Automated Demo (`hitl_demo.py`)

Runs the complete HITL flow automatically:
1. Submits complaint that triggers HUMAN_REVIEW
2. Queries status after 2 seconds
3. Sends approval signal after 5 seconds
4. Displays final result

```bash
uv run python hitl_demo.py
```

### Interactive CLI (`client_hitl.py`)

Manual control for realistic testing:

```bash
# Terminal 1: Start worker (if not already running)
uv run python worker.py

# Terminal 2: Submit complaint and note the workflow-id from output
uv run python client_run.py complaints/complaint2.json
# Output shows: "Started workflow: complaint-run-abc123..."
#                              ^^^^^^^^^^^^^^^^^^^^^ this is the workflow-id

# Terminal 3: Query workflow status
uv run python client_hitl.py query complaint-run-abc123

# Approve complaint
uv run python client_hitl.py approve complaint-run-abc123 --reviewer operator-1 --notes "Verified"

# Or reject complaint
uv run python client_hitl.py reject complaint-run-abc123 --reviewer operator-1 --notes "Unverified claim"
```

**How to find workflow-id:**
1. **From client_run.py output**: Shows `Started workflow: <workflow-id>` when you submit
2. **From Temporal UI**: http://localhost:8233 → click on any workflow → ID in header
3. **From CLI**: `temporal workflow list` shows all workflow IDs

## Testing Scenarios

### Scenario 1: Human Approval
1. Start workflow with `complaint2.json` (triggers HUMAN_REVIEW)
2. Workflow pauses at `AWAITING_HUMAN_REVIEW`
3. Query status - see review packet details
4. Send `APPROVED` signal
5. Workflow generates approval message and completes with `HUMAN_APPROVED`

### Scenario 2: Human Rejection
1. Same as above, but send `REJECTED` signal
2. Workflow generates polite rejection and completes with `HUMAN_REJECTED`

### Scenario 3: Timeout Escalation
1. Start workflow with complaint
2. Don't send any signal
3. After 10 minutes, workflow auto-escalates
4. Completes with `TIMEOUT_ESCALATED`

## Temporal UI Observation

With HITL, you can observe in http://localhost:8233:

1. **Running State**: Workflow shows "Running" (not "Completed") while waiting
2. **Event History**: See `WorkflowExecutionSignaled` event when human decides
3. **Query Tab**: Execute `get_status` query to see current state
4. **Input/Output**: Full audit trail of review packet and decision

## Teaching Points

| Concept | Demonstration |
|---------|---------------|
| Durable Execution | Workflow survives worker restarts while waiting |
| External Signals | Human decision enters via signal handler |
| State Queries | Read workflow state without mutations |
| Temporal Timers | Timeout triggers auto-escalation |
| Event Sourcing | Full history preserved in Temporal |
| BPMN User Task | Signal + wait_condition = equivalent pattern |

## Files Modified

| File | Changes |
|------|---------|
| `models.py` | Add `HumanDecision`, `HumanReviewInput`, update `TerminalStatus` |
| `workflow.py` | Add signal/query handlers, wait_condition, timeout logic |
| `activities.py` | Add notification and human decision message activities |
| `hitl_demo.py` | NEW - Automated HITL demo |
| `client_hitl.py` | NEW - Interactive CLI for manual testing |

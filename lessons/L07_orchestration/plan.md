# Lesson 07 – AI Workflow Orchestration (Temporal + LLM Assisted Complaint Handling)

This plan drives an iterative, test-first implementation of a durable complaint handling workflow using Temporal. It aligns with the business flow you specified and integrates LLM steps in clearly bounded, testable activities. Teacher builds the full reference path; students extend with variations (timers, alternative resolutions, metrics, parallel reviews).

---
## 0. Business Workflow (Authoritative Definition)
1. Complaint is received (raw text + any provided metadata).
2. LLM classification: Is this actually a complaint? (Else: stop; optional message back.)
3. If complaint: LLM checks if required identifiers are present (user id AND any order locator: order id OR (date + item description)).
4. If identifiers missing: Ask user for more details (LLM crafts clarification message) → workflow ends (status: NEEDS_MORE_INFO).
5. If identifiers sufficient: Fetch (mock) order + load (mock) user profile.
6. Provide full context + policies document to decision LLM → outputs: action ∈ {VALID, NOT_VALID, HUMAN_REVIEW}, reason.
7. If action in {VALID, NOT_VALID}: LLM crafts final user-facing message (resolution or rejection) → persist audit → end.
8. If action == HUMAN_REVIEW: Specialized LLM summarizes case + context → produce review packet for human queue → end with status: PENDING_REVIEW.

Non-goals (for now): actual DB writes, real authZ, multi-order correlation, refund side-effects.

---
## 1. Architectural Boundaries
Component / Responsibility:
- Temporal Workflow: Orchestrates state machine & branching; holds no external side-effects directly; deterministic logic only.
- Activities: Encapsulate side-effects (mock fetch order, fetch profile) and LLM calls (segmented per purpose for observability & caching potential).
- Rules Module: Pure Python post-processing of LLM structured outputs (validation + guardrails) → unit-testable without Temporal.
- Policy Artifact: Static markdown / text file injected into decision LLM activity (kept under version control for determinism & auditing).
- Tests: (a) Pure rule tests (b) Activity contract tests (monkeypatch LLM adapter) (c) Workflow path tests via Temporal test environment.

---
## 2. Directory Structure (to be created incrementally)
```
orchestration/
	complaint_workflow/
		__init__.py
		policies/
			complaint_policies.md
		models.py
		rules.py
		llm_adapter.py            # Thin wrapper (LiteLLM / OpenAI) – swappable, mocked in tests
		activities.py             # LLM + data fetch activities
		workflow.py               # Temporal workflow definition
		worker.py                 # Worker process
		client_run.py             # Manual trigger / demo script
		config.py                 # Thresholds, timeouts, task queue name
		tests/
			test_rules.py
			test_activity_decision_parsing.py
			test_workflow_valid.py
			test_workflow_needs_more_info.py
			test_workflow_human_review.py
```

---
## 3. Temporal / Tooling Setup
Step 3.1 Install Temporal CLI (developer machine) – one‑time.
Step 3.2 Start dev server: `temporal server start-dev` (PowerShell).
Step 3.3 Add Python dependencies (Temporal SDK, pydantic, httpx, lite-llm or openai). Use project-level `pyproject.toml` or an isolated one (decide based on repo conventions; prefer shared if agent already uses OpenAI client libs).
Step 3.4 Create minimal `workflow.py` + `worker.py` + trivial test workflow returning a constant to validate environment.

---
## 4. Data & Model Contracts
Define (Pydantic):
- ComplaintIn { complaint_id, raw_text, user_id (optional), order_id (optional), order_date (optional), items (optional list[str]), created_at }
- ComplaintClassification { is_complaint: bool, confidence: float, missing_fields: list[str] }
- OrderRecord (mock) { order_id, user_id, items, date }
- UserProfile (mock) { user_id, segment, loyalty_level }
- DecisionOutput { action: enum(VALID, NOT_VALID, HUMAN_REVIEW), reason: str }
- UserMessage { text: str, tone: str }
- ReviewPacket { summary: str, details: dict }
- WorkflowResult { complaint_id, terminal_status, action (nullable), reason (nullable), user_message (nullable), review_packet_id (nullable) }

Enums: Action, TerminalStatus (NEEDS_MORE_INFO, COMPLETED, PENDING_REVIEW).

---
## 5. Iterative Implementation Steps

### Step 1 – Skeleton Workflow
- Implement workflow with single input (ComplaintIn) returning fixed `WorkflowResult`.
- Worker + client run script.
- Add `test_workflow_smoke` using Temporal test environment.

### Step 2 – Classification Activity
- Activity: `classify_complaint(raw_text)` → ComplaintClassification (deterministic mock first). Branch in workflow: if not complaint → result terminal_status=COMPLETED action=None reason="NOT_COMPLAINT".
- Tests: classification rule (unit) + workflow path non-complaint.

### Step 3 – Field Sufficiency Check
- Pure rules function: `determine_required_fields(classification, complaint_input)` → missing list.
- If missing: call activity `craft_clarification_message(missing_fields)` (LLM later; mock now) → terminal_status=NEEDS_MORE_INFO.
- Tests: missing field scenario (user id absent, order locator absent).

### Step 4 – Data Fetch Activities
- `fetch_order(order_id | (date, items))` mock (returns OrderRecord or None – if None escalate to NEEDS_MORE_INFO for now).
- `fetch_user_profile(user_id)` mock.
- Inject results into workflow state object.
- Tests: success path with provided order_id.

### Step 5 – Decision Activity (LLM Stub)
- Policies markdown file added.
- Activity: `decide_action(context_bundle)` returns DecisionOutput (stub mapping: if items contain "damaged" → VALID else HUMAN_REVIEW else NOT_VALID).
- Workflow branches accordingly; set action/reason.
- Tests: VALID branch, HUMAN_REVIEW branch, NOT_VALID branch (simulate with input patterns).

### Step 6 – User Message / Review Packet Activities
- `craft_user_message(action, reason, complaint, order, profile)` (LLM later) – only for VALID / NOT_VALID.
- `craft_review_packet(complaint, order, profile, reason)` – returns ReviewPacket; store packet to temp JSON file (activity) and return id.
- Extend workflow & tests for all branches.

### Step 7 – Replace Stubs with Real LLM Calls
- Introduce `llm_adapter.py` with interface: `async classify(text)`, `async generate(system_prompt, messages, response_schema)`.
- Use structured output (JSON schema) for classification & decision activities.
- Add env toggles: `ORCH_USE_REAL_LLM` (default false for tests).
- Add tests that monkeypatch adapter to deterministic outputs (no network).

### Step 8 – Timeouts & Retries
- Add explicit `schedule_to_close_timeout` and simple RetryPolicy on LLM activities.
- Simulate transient failure in a test (inject raising stub first attempt then success) to ensure retry.

### Step 9 – Observability Hooks
- Add logging in activities with structured key=value (ORCH_PHASE, complaint_id, action).
- (Optional) Add lightweight audit activity writing JSONL under `orchestration/complaint_workflow/.audit/` (excluded from repo via .gitignore if needed).

### Step 10 – Hardening & Student Extensions
- Guardrail: Validate DecisionOutput.action ∈ enum; else coerce to HUMAN_REVIEW.
- Student tasks (document at bottom):
	1. Add SLA timer child workflow to auto-remind after 24h (Temporal sleep) for HUMAN_REVIEW.
	2. Add parallel classification cross-check (two models) → escalate if disagreement.
	3. Add sentiment extraction influencing tone in user message.
	4. Add metrics exporter activity (counts per action) – write to in-memory aggregator.

---
## 6. Testing Strategy Matrix
| Layer | Tools | Focus |
|-------|-------|-------|
| Rules | pytest unit | Deterministic branching & field checks |
| Activities (LLM) | pytest w/ monkeypatch | Schema integrity, fallback behavior |
| Workflow | Temporal test env | Path coverage (NOT_COMPLAINT, NEEDS_MORE_INFO, VALID, NOT_VALID, HUMAN_REVIEW) |
| Retry Logic | Temporal test env + failing stub | Ensure retry policy respected |
| Adapter | Unit | Input → JSON schema parsing resilience |

CI Note: Mark LLM network tests as skipped unless flag set.

---
## 7. Policies Document (Initial Content Outline)
Sections (short): Scope, Definition of Valid Complaint, Exclusions (late beyond X days, already refunded), Auto-Approve Heuristics (low amount, first-time user), Mandatory Escalation (safety, fraud suspicion). Keep deterministic, version with commit hash reference.

---
## 8. Environment & Config
Config variables (added later to central doc if needed):
- ORCH_ENABLE=true
- ORCH_TASK_QUEUE=complaint-orch
- ORCH_USE_REAL_LLM=false
- ORCH_POLICY_FILE=policies/complaint_policies.md

---
## 9. Student Exercise Brief (Condensed)
Implement one feature with tests: SLA timer, dual-model validation, sentiment-based message style, or metrics exporter.

---
## 10. Done Definition (Teacher Reference)
- All five primary branches covered by tests (≥1 assertion each on WorkflowResult fields).
- No network dependency in default test run.
- Policies file present & referenced by decision activity.
- LLM adapter swappable (mock vs real).
- README snippet (or section) on how to run local worker + sample client.

---
## 11. Quick Run (after implementing Steps 1–6)
PowerShell (Temporal dev server already running):
```
python -m orchestration.complaint_workflow.worker
python -m orchestration.complaint_workflow.client_run --complaint-id c123 --text "My order arrived damaged, missing a jar" --user-id u42 --order-id o900
```

---
## 12. Future Enhancements (Roadmap Hooks)
- Persist review packets into core DB + expose API for human dashboard.
- Add refund / rejection side-effect integration to existing agent backend.
- Inject conversation memory to tailor user message tone.
- Temporal search attributes for filtering outstanding HUMAN_REVIEW workflows.

---
End of plan.


# Agents Folder

Purpose: Holds self‑contained agent/service implementations (chat, RAG, tool, workflow, etc.).

Each agent directory should minimally include:
1. `pyproject.toml` (managed with `uv`).
2. `src/` with the FastAPI (or compatible) entrypoint and internal modules.
3. `models/` for Pydantic schemas (if needed).
4. `tests/` with focused unit/integration coverage.
5. A local `README.md` explaining how to run just that agent (port, startup, sample invocation).

Adding a new agent (summary): create folder → add `pyproject.toml` → scaffold `src/main.py` (FastAPI app) → add a minimal test in `tests/` → document run steps in that agent's `README.md`.

# Data Folder

Purpose: Holds raw inputs, transformation scripts, and reproducible derived artifacts for demos and development.

Structure summary:
- `source_json/` – Seed/reference JSON inputs.
- `scripts/` – Transformation & import scripts (run with `uv run python <script.py>` from this directory).
- `processed/` – Generated outputs (embeddings, parquet, taxonomy state). Treat as reproducible cache—regenerate instead of manual editing.
- `images/`, `videos/`, `PDFs/` – Raw media assets (immutable originals).

Folder specifics:
- Keep each transformation step small & explicit; orchestrators (e.g. `import_all.py`) can compose them.
- Do not commit large or sensitive datasets; reference external acquisition steps in `scripts/README.md` if needed.

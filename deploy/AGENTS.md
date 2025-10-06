# Deploy Folder

Purpose: Environment provisioning & runtime orchestration assets.

Structure:
- `local/` – Local Docker Compose development stack (run from inside that directory).
- `azure/` – Cloud deployment references/docs (pair with Terraform code kept elsewhere if added later).
- `kubernetes/` – K8s manifests or references for cluster deployment.

Folder‑specific guidance:
- Keep everything declarative (Compose files, manifests). Avoid one‑off mutable shell scripts here.
- Never commit secrets; rely on environment variables / secret stores.
- Put any special startup or teardown notes in the respective subfolder `README.md` (concise).
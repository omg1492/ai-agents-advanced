# Frontend Folder

Purpose: React + `assistant-ui` user interface for interacting with agents/services.

Folder specifics:
- Install & run with the usual Node workflow (`npm install` then dev server); operational details live in this folder's `README.md`.
- Generate runtime configuration: copy or template `public/config.js.template` → `public/config.js` (never commit secrets).
- Keep UI components small; extract shared logic into local hooks/util utilities.
- All server/agent interaction happens through HTTP or WebSocket calls—no embedding of backend logic.

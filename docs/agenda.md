# Lekce 01 – Business požadavky, architektura & základní chatbot nad dokumenty
- Cíle aplikace, ROI  
- Referenční architektura AI aplikací  
- RAG pipeline (čistý text -> pgvector)  
- Jednoduchý chatbot nad dokumenty

Použité technologie:
- OpenAI API
- PostgreSQL (pgvector)
- Python (FastAPI, Streamlit)
- (LangGraph pro RAG)

# Lekce 02 – Používání nástrojů: Web search, API, MCP
- Vyhledávání na webu  
- Volání externích služeb (REST/GraphQL/MCP)  
- Bezpečnost API/MCP

# Lekce 03 – Vytváření znalostní báze pro AI z dokumentů, obrázků a videí
- PDF/Video ingest → embeddings  
- Základní indexace (vektory, full-text, re-ranking)
- Bezpečnost přístupu k datům (RAG fencing)
- Semantic caching

# Lekce 04 – Deep Research & Knowledge Graph
- Uspořádání informací do grafu  
- Agentic RAG, multi-step search  
- Workflow pro deep research

# Lekce 05 – Multimodalita, paměť & Real Voice Chat
- Speech-to-Text / Text-to-Speech vs. Real Voice Chat
- Personalizační paměť & preference uživatele 

# Lekce 06 – Code Interpreter & Agentic UI
- Python sandbox (výpočty / grafy)  
- Generování HTML/JS infografiky  
- Analytické agentic nástroje

# Lekce 07 – Orchestrace AI workflow
- Robustní orchestrace s Temporal
- Autonomní zpracování událostí
- Model routing, fallback & cost control

Použité technologie:
- Temporal pro orchestraci
- LiteLLM pro model routing

# Lekce 08 – Multi-agent systémy
- Role a vlastnosti agentů a jejich spolupráce
- Implementace v LangGraph a komunikace přes Redis 

Použité technologie:
- LangGraph pro agentic architekturu
- Redis pro komunikaci mezi agenty

# Lekce 09 – Bezpečnost & Evaluace
- Autorizace, red teaming, prompt injection  
- LLM-as-judge, auto-evaluation, feedback loop

Použité technologie:
- PyRIT (bezpečnostní testování)
- Langfuse (evaluace a feedback)

# Lekce 10 – Observabilita & Škálovatelné nasazení
- OpenTelemetry, metriky, logging  
- Škálovatelné nasazení v Kubernetes
- Průběžné nasazování a testování (CI/CD, infra as code)

Použité technologie:
- OpenTelemetry a Langfuse pro observabilitu
- Kubernetes pro nasazení
- CI/CD s GitHub Actions

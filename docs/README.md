# Pokročilý kurz AI aplikací – 10 večerních lekcí

Tento pokročilý kurz vás provede tvorbou **virtuálního farmářského tržiště** a naučí vás navrhovat, implementovat a nasazovat produkční AI služby. Projdeme kompletní workflow – od základního RAG (CSV → embeddings) a nástrojového volání (MCP + function calling), přes ingest dokumentů / obrázků / audia / videí, hybridní vyhledávání a semantický caching, deep research a znalostní graf, multimodalitu, personalizační paměť a dynamicky generované UI, až po integraci do podnikových systémů, autonomní workflow, multi-agentní spolupráci, observabilitu, evaluaci, bezpečnost a škálovatelné nasazení. 

## V čem je tento kurz jiný
- Celý kurz společně budujeme AI aplikaci, která řeší reálný byznys problém. Od jednoduchého minimálního produktu přes komplexní funkce až po zabezpečení, měření a vylepšování kvality, nasazení, škálování a observabilitu.
- V kurzu naživo programujeme řešení s využitím AI-asistovaného vývoje. Díky tomu jsme schopni urazit velký kus cesty a přitom si ponechává maximální flexibilitu code-first přístupu v návrhu a implementaci a nejsme zamčeni v žádné low-code platformě.
- Intenzivní každodenní hands-on formát vám pomůže udržet motivaci a rychle se posunout vpřed.

## Struktura kurzu  
- 10 navazujících lekcí, každý všední den po dobu dvou týdnů.  
- Každá lekce rozšiřuje společný projekt a staví na výstupech z předchozího dne.

Obsah jednotlivých lekcí je v [podrobné agendě](agenda.md)

### Struktura lekce (120 min)  
- 15 min | Teoretický úvod  
- 45 min | Pokročilá ukázka (kompletní řešení)  
- 60 min | Live-coding s GitHub Copilotem  

Obsah lekcí navazuje na agendu (`docs/agenda.md`) a postupně rozvíjí společný projekt.

## Společný projekt – Virtuální farmářské tržiště  
Cílem je vybudovat AI aplikaci, která:  
- Odpovídá na dotazy o původu, kvalitě a dostupnosti produktů.  
- Zpracovává a sjednocuje informace z dokumentů, obrázků, audia i videí do srozumitelných odpovědí.  
- Rychle a přesně vyhledává i v rozsáhlých podkladech a učí se z častých dotazů pro svižnější reakce.  
- Propojuje suroviny, recepty a sezónnost a navrhuje personalizované košíky podle preferencí, diet a alergií.  
- Udržuje dlouhodobou paměť uživatele (obliby, omezení) a tomu přizpůsobuje další doporučení.  
- Umožňuje hands‑free hlasovou interakci.  
- Vizualizuje nutriční a další data a nabízí zdravější alternativy.  
- Pomáhá řešit stížnosti a opakované procesy automatizovanými workflow.  
- Spolupracuje mezi více specializovanými "agenty" (např. farmářský a kuchařský) a dokáže domluvit catering včetně surovin a ceny.  
- Respektuje přístupová oprávnění a chrání citlivější podklady. 

Jaké funkce přidáme do aplikace v jaké lekci je k přečteně v [agendě](agenda.md)

## Použité technologie  
**Core & Backend:**  
- Python (FastAPI)  
- OpenAI GPT / Embeddings (cosine similarity)  
- PostgreSQL + pgvector (vektory) + full‑text  
- Redis (caching, pub/sub)  

**Retrieval & Knowledge:**  
- Hybrid search (keyword + semantic + RRF)  
- Semantic cache  
- MarkItDown (konverze dokumentů)  
- Whisper (STT)  
- ffmpeg (audio/video extrakce)  
- AGE (PostgreSQL extension) – knowledge / graph základy  

**Nástroje & Orchestrace:**  
- MCP servery (interní + web-search, Tavily)  
- Function calling (vlastní nástroje)  
- LangGraph (agentic RAG, orchestrace agentů)  
- Temporal (workflow)  
- LiteLLM (model routing)  

**UI & Interakce:**  
- React (assistant-ui)  
- Real Voice Chat (STT/TTS)  
- Code Interpreter / sandbox (analýza & vizualizace)  

**Security & Observabilita:**  
- Keycloak / OIDC (autentizace, tokeny)  
- OpenTelemetry + Langfuse (telemetrie, evaluace)  
- PyRIT (red teaming)  

**DevOps & Infra:**  
- Docker Compose, Kubernetes  
- GitHub Actions (CI/CD)  
- Terraform (IaC)  

## Vstupní požadavky  
- Praktická znalost Pythonu (funkce, moduly, virtuální prostředí).  
- Zkušenost s vytvořením jednoduchého chatbotu v Pythonu.  
- Základní práce s LLM: tvorba promptů, volání OpenAI API nebo ekvivalentu.  
- Výhodou je orientace v Dockeru a GitHub Actions, není však nutná.  
- Dostupný placený tarif GitHub Copilot ve VS Code / Cursor / Windsurf pro plynulý live-coding s asistencí.  
- Aktivní účet Azure OpenAI nebo OpenAI s dostatečným kreditem na volání modelů využívaných během kurzu.  

## Pro koho je kurz určen  
- Vývojáři a data scientists, kteří již vytvořili první LLM prototypy a chtějí přejít na produkční úroveň.  
- Architekti, kteří se chtějí seznámit s osvědčenými vzory integrace AI, a zároveň jsou schopni prakticky experimentovat v Pythonu.  
- Technické leadery se zkušeností s hands-on prototypováním, kteří potřebují řešit škálování, bezpečnost a observabilitu AI služeb v Pythonu.  

## Pro koho kurz není určen  
- Úplní začátečníci bez zkušeností s tvorbou základní AI aplikace typu chatbot.  
- Účastníci bez znalosti Pythonu – kurz je code-first a nevyužívá low-code platforem.  
- Specialisté s úzkým zaměřením na frontend – UI je v kurzu řešeno jen minimálně a není hlavním tématem.
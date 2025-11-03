# Agenda kurzu

### Platforma
Kurz funguje s **Azure OpenAI** i **OpenAI Platform**:
- **Azure OpenAI**: Doporučeno pro firemní prostředí (compliance, data residency, enterprise podpora)
- **OpenAI Platform**: Plně podporováno pro individuální studium a experimentování
- **Přepínání mezi platformami**: Jednoduchá změna konfigurace v `.env` souboru (`OPENAI_BASE_URL` a API klíč)

---

### Lekce 00 - Přípravné materiály před startem kurzu
Vnímáte u sebe nějaké slabiny a chcete se na kurz lépe připravit? Třeba základní zkušenost s API aplikacemi máte, ale potřebujete se nachytřit v základech Kubernetu? Nebo nasazování a škálování aplikací běžně děláte, ale potřebujete si osvěžit základy používání databází jako je PostgreSQL? Programujete pokročile v Javě, Javscriptu nebo C#, ale v Python se potřebujete trochu pocvičit?

Dostanete seznam doporučených tutoriálů - nejsou podmínkou, ale pokud chcete pro svou připravenost udělat maximum, skvělé!

### Lekce 01 – Business požadavky, architektura & základní chatbot nad dokumenty
Základní chatbot zpřístupní popisy produktů v přirozeném jazyce, aby zákazník rychle zjistil původ, kvalitu i dostupnost zboží. Součástí je jednoduchá data pipeline (CSV → embeddings) a základní RAG nad PostgreSQL s cosinovou podobností a jednoduchým frontendem.  

**Koncepty:**
- RAG
- Embeddings
- Vektorová databáze
- Data pipeline (CSV → embeddings)

**Technologie:**
- OpenAI GPT 5
- PostgreSQL (pgvector)
- FastAPI (Python)
- React (assistant-ui)
- Docker Compose
- Cosine similarity

### Lekce 02 – Používání nástrojů: Web search, API, MCP
Asistent kombinuje interní API, MCP nástroje a web-search (Tavily) pro získání aktuálních zásob, sezónních produktů a receptů. Přidáváme vlastní nástroj přes function calling a (volitelně) MCP gateway.  

**Koncepty:**
- Tool-use
- Function calling
- MCP gateway
- Web-search
- Integrace interního API

**Technologie:**
- MCP servery
- GPT 5 (tool / function calling)
- FastAPI (Python)
- Tavily search

### Lekce 03 – Vytváření znalostní báze pro AI z dokumentů, obrázků a videí
Zpracování PDF, obrázků, audia (Whisper) i krátkých videí (extrakce zvuku / textu) do Markdown a embeddings. Přidání hybridního vyhledávání (keyword + semantic + RRF), full‑text vyhledávání a semantického cachování častých dotazů.  

**Koncepty:**
- Data ingest (PDF, image, audio, video)
- Hybrid search (keyword + semantic + RRF)
- Full‑text search
- Semantic cache

**Technologie:**
- MarkItDown
- Whisper
- ffmpeg
- OpenAI embeddings
- PostgreSQL (pgvector + full‑text)

### Lekce 04 – Agentic Search, Knowledge Graph & RAG Fencing
Implementace agentic (nástrojového) vyhledávání kde LLM rozhoduje o výběru vyhledávacích strategií, základ znalostního grafu v PostgreSQL/AGE pro strukturální podobnost produktů, a VIP fencing pro řízený přístup k prémiovým produktům s autentizací přes Keycloak.

**Koncepty:**
- Agentic search (tool-based, function calling)
- Knowledge graph (producers, products, allergens, certifications)
- RAG fencing (VIP filtering před LLM)
- Autentizace a autorizace (OAuth2/OIDC)
- HyDE (Hypothetical Document Embedding)
- BFS/DFS graph traversal
- Feature flags

**Technologie:**
- AGE (PostgreSQL extension)
- Keycloak (OAuth2/OIDC)
- OpenAI function calling
- FastAPI (backend tools)
- Python
- React (assistant-ui s autentizací)

### Lekce 05 – Multimodalita, paměť & Real Voice Chat
Lekce rozšiřuje asistenta o Real Voice Chat (hands‑free) a dlouhodobou paměť s preferencemi, dietami a alergeny pro vyšší personalizaci a retenci.  

**Koncepty:**
- Multimodality
- Personalizace
- Long-term memory
- Voice chat  

**Technologie:**
- Real Voice Chat (STT/TTS)
- Redis
- Python
- OpenAI API

### Lekce 06 – Analýza dat a vizualizace (Code Interpreter & MCP Vizualizace)
AI analyzuje nutriční a zdravotní data uživatele, vizualizuje je v přehledných grafech a navrhuje zdravější alternativy. Kromě toho dokáže vytvářet interaktivní HTML infografiky pomocí MCP Visualization serveru – moderní kartičky s gradienty, animacemi a responzivním designem. Interaktivní infografiky zvyšují angažovanost a motivují ke koupi doporučených produktů.  

**Byznys hodnota:**
- Zdravotní tracking zákazníků (analýza váhy, nutriční hodnoty)
- Interaktivní infografiky pro zvýšení engagement
- Vizualizace trendů a doporučení produktů

**Koncepty:**
- Code interpreter (Python sandbox pro analýzu dat)
- Data analysis (statistiky, výpočty, grafy)
- Dynamic UI generation (HTML kartičky)
- MCP Visualization server (vzdálené generování vizualizací)
- Sandboxed iframe artifacts (bezpečné zobrazení)
- HTML/CSS infographic generation (moderní design)

**Technologie:**
- Python sandbox (Code Interpreter API - Azure OpenAI nebo OpenAI Platform)
- Matplotlib/Plotly (grafy a vizualizace)
- MCP Visualization Server (FastMCP na Azure Container Apps)
- React UI (assistant-ui s iframe security)
- In-memory artifact storage s TTL (1 hodina)

### Lekce 07 – Orchestrace AI workflow
Automatizované workflow vyhodnotí stížnost, přiložené důkazy a pravidla nároku, aby okamžitě řešilo jasné případy a ostatní eskalovalo. Rychlá reakce zlepšuje NPS a snižuje provozní náklady podpory.  

**Koncepty:**
- Agent orchestration
- Workflow automation
- Durable workflows
- Policy-based decision making

**Technologie:**
- Temporal
- Azure OpenAI (Responses API with structured outputs)
- Python
- Pydantic

### Lekce 08 – Multi-agent systémy
S rostoucí sofistikovaností AI agenta a rozšiřujícím se byznysem virtuálního tržiště vzniká potřeba vyvíjet některé části systému víc nezávisle a soustředit se na specializovaného agenta. Nový obchodní nápad má přivést na tržiště i kuchaře, kteří mohou nabízet služby pro různé oslavy a firemní akce a propojit tak dodavatele farmářských produktů, jejich zákazníky a služeb přípravy jídla. Na základě požadavku uživatele musí vzájemnou interakcí původního agenta (farmářské tržiště) a nového agenta (tržiště kuchařů a služeb) vzniknout dohrada, který kuchař z jakých surovin co by zajistil a jaká je celková cena a tyto varianty nabídnout uživateli.  

**Byznys hodnota:**
- Cross-sell: Zákazník objedná produkty + kuchaře + catering najednou
- Balíčková řešení: Kompletní služba (suroviny + příprava + servírování)
- Diferenciace: Farm-to-table platforma, ne jen marketplace

**Koncepty:**
- Multi-agent systems (specializovaní agenti s vlastními doménami)
- Agent collaboration (komunikace mezi agenty)
- Agent-as-tool pattern (agent exponovaný jako function tool)
- Bounded context separation (nezávislé služby s jasným rozhraním)

**Technologie:**
- Agent-as-tool (HTTP function calling)
- Python (FastAPI pro každého agenta)
- MCP Protocol (Chef Services MCP server)
- HTTP async communication (httpx)

### Lekce 09 – Bezpečnost & Evaluace
Jídlo a zdraví jsou citlivá témata a systém musí být bezpečný a důvěryhodný, jinak je tu reputační riziko. Kromě toho mohou být některá témata kontroverzní a pro některé uživatele nepříjemná (například náboženská omezení ve stravě, intolerance, vegetariánství apod.). Navíc přesnost odpovědí je důležitá, protože chyby v popisu či doporučení produktů mohou vést k nespokojenosti a ztrátě důvěry. Každá změna (verze) systému tak musí být testována a vyhodnocena stejně jako zpětná vazba uživatelů a to jak před nasazením, na základě reakce na hodnocení uživatele tak i průběžně v produkci přes A/B testování a evaluace.  

**Byznys hodnota:**
- Měřitelná kvalita: Objektivní metriky místo subjektivního hodnocení
- Prevence škod: Detekce biasu, toxicity, doporučení konkurence
- CI/CD integrace: Automatické QA při každém deployi
- Compliance: Audit trail pro regulátory (GDPR, AI Act)

**Koncepty:**
- AI security (ochrana proti škodlivým promptům)
- Red teaming (automatizované bezpečnostní testování)
- LLM-as-judge (GPT-5 evaluuje GPT-5)
- Evaluation framework (metriky kvality RAG systémů)
- Hallucination detection (detekce nepravdivých informací)
- Bias testing (genderový, rasový, kulturní bias)

**Technologie:**
- PyRIT (Python Risk Identification Toolkit - Microsoft)
- DeepEval (LLM evaluation framework)
- Azure OpenAI (GPT-5 jako evaluační model)
- AdvBench, HarmBench, Forbidden Questions (bezpečnostní datasety)

### Lekce 10 – Observabilita & Škálovatelné nasazení
Komplexní telemetrie a elastické škálování zajistí stabilní provoz během sezónních špiček a transparentní monitoring nákladů. Provozní tým tak může včas optimalizovat výkon i rozpočet. Lekce pokrývá kompletní produkční nasazení s Infrastructure as Code, CI/CD pipeline a enterprise observability.  

**Byznys hodnota:**
- Škálovatelná infrastruktura pro růst businessu
- Monitoring a alerting pro proaktivní správu
- CI/CD automatizace pro rychlé iterace
- Enterprise-ready deployment s high availability

**Koncepty:**
- Observability (logging, tracing, metrics)
- Scalable deployment (container orchestration)
- CI/CD (continuous integration/deployment)
- Infrastructure as Code (deklarativní infrastruktura)
- Zero-downtime deployment (rolling updates)
- Distributed tracing (sledování requestů napříč službami)

**Technologie:**
- Kubernetes (Azure AKS nebo on-premise)
- Helm charts (orchestration, dreamfarm-agent, chef-agent)
- Terraform (Azure infrastruktura - Container Apps, Service Bus, PostgreSQL Flexible)
- OpenTelemetry (distributed tracing, metrics, logging)
- Grafana Tempo (tracing backend)
- LangFuse (LLM observability - volitelné)
- GitHub Actions (CI/CD pipeline)
- Docker (kontejnerizace aplikací)

---

### Poznámky k materiálům
- **Jazyk**: Některé lekce mají README v angličtině (L05, L08, L09), jiné v češtině - veškeré materiály jsou přístupné v obou jazycích dle potřeby
- **Živé kódování**: Všechny lekce používají GitHub Copilot pro demonstraci tvorby kódu v reálném čase
- **Branch strategie**: Každá lekce má `Lxx-student` (výchozí bod) a `Lxx-teacher` (řešení) branch pro postupnou implementaci


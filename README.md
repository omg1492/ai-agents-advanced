# Pokročilé AI Aplikace - Dream Farm AI Platforma

**Dream Farm** je (téměř) produkční AI platforma demonstrující virtuální farmářské tržiště, které propojuje místní farmáře se zákazníky prostřednictvím inteligentního AI asistenta. Platforma prezentuje pokročilé AI schopnosti včetně RAG (Retrieval-Augmented Generation), multi-agent systémů, grafových databází, hlasové interakce, workflow orchestrace a enterprise observability a deployment.

**Klíčové funkce:** Sémantické vyhledávání produktů, integrace nástrojů (MCP servery, webové vyhledávání, interní API), hybridní retrieval (sémantické + keyword + graf), personalizovaná paměť, hlasový chat, code interpreter s vizualizacemi, multi-agent spolupráce, automatizace workflow, autentizace (Keycloak), OpenTelemetry observability a Red Teaming, nasazení do Kubernetes.

📖 **[Kompletní architektonická dokumentace →](docs/Design.md)**

---

## Kurz: Pokročilé AI Aplikace (10 večerních lekcí)

Tento repozitář je základem pro intenzivní kurz o deseti lekcích, který učí, jak navrhovat, implementovat a nasazovat produkční AI aplikace. Projdeme kompletní workflow – od základního RAG (CSV → embeddings) a nástrojového volání (MCP + function calling), přes ingest dokumentů / obrázků / audia / videí, hybridní vyhledávání a semantický caching, deep research a znalostní graf, multimodalitu, personalizační paměť a dynamicky generované UI, až po integraci do podnikových systémů, autonomní workflow, multi-agentní spolupráci, observabilitu, evaluaci, bezpečnost a škálovatelné nasazení.

### V čem je tento kurz jiný
- **Reálný byznys problém**: Celý kurz společně budujeme AI aplikaci, která řeší praktický problém virtuálního farmářského tržiště. Od jednoduchého minimálního produktu přes komplexní funkce až po zabezpečení, měření a vylepšování kvality, nasazení, škálování a observabilitu.
- **AI-asistovaný vývoj**: V kurzu naživo programujeme řešení s využitím GitHub Copilot. Díky tomu jsme schopni urazit velký kus cesty a přitom si ponechat maximální flexibilitu code-first přístupu v návrhu a implementaci – nejsme zamčeni v žádné low-code platformě.
- **Intenzivní hands-on formát**: 10 navazujících lekcí, každý všední den po dobu dvou týdnů, vám pomůže udržet motivaci a rychle se posunout vpřed.

### Struktura lekce (120 min)
- **15 min** | Teoretický úvod  
- **30 min** | Pokročilá ukázka (kompletní řešení)  
- **45-75 min** | Live-coding s GitHub Copilotem

Kurz sleduje inkrementální, hands-on přístup, kde každá lekce staví na předchozí a vyvíjí se od základního RAG chatbota k sofistikovanému multi-agent systému s enterprise funkcemi.

### Co budeme stavět: Virtuální farmářské tržiště
Cílem je vybudovat AI aplikaci, která:  
- Odpovídá na dotazy o **původu, kvalitě a dostupnosti produktů**
- Zpracovává a sjednocuje informace z **dokumentů, obrázků, audia i videí** do srozumitelných odpovědí
- **Rychle a přesně vyhledává** i v rozsáhlých podkladech a učí se z častých dotazů pro svižnější reakce
- Propojuje **suroviny, recepty a sezónnost** a navrhuje personalizované košíky podle preferencí, diet a alergií
- Udržuje **dlouhodobou paměť uživatele** (obliby, omezení) a tomu přizpůsobuje další doporučení
- Umožňuje **hands-free hlasovou interakci**
- **Vizualizuje nutriční a další data** a nabízí zdravější alternativy
- Pomáhá řešit **stížnosti a opakované procesy** automatizovanými workflow
- Spolupracuje mezi více **specializovanými agenty** (např. farmářský a kuchařský) a dokáže domluvit catering včetně surovin a ceny
- **Respektuje přístupová oprávnění** a chrání citlivější podklady

### Flexibilita platformy
Kurz **podporuje obě platformy**:
- **Azure OpenAI**: Doporučeno pro firemní scénáře (data residency, compliance, enterprise podpora)
- **OpenAI Platform**: Plně podporováno pro individuální studium a experimentování  
- **Přepínání**: Stejná `.env` konfigurace, stačí změnit `OPENAI_BASE_URL` a API klíč

### Vstupní požadavky
- **Praktická znalost Pythonu** (funkce, moduly, virtuální prostředí)
- **Zkušenost s vytvořením jednoduchého chatbotu** v Pythonu
- **Základní práce s LLM**: tvorba promptů, volání OpenAI API nebo ekvivalentu
- **Výhodou** je orientace v Dockeru a GitHub Actions, není však nutná
- **Dostupný placený tarif GitHub Copilot** ve VS Code / Cursor / Windsurf pro plynulý live-coding s asistencí
- **Aktivní účet Azure OpenAI nebo OpenAI** s dostatečným kreditem na volání modelů využívaných během kurzu

### Pro koho je kurz určen
- **Vývojáři a data scientists**, kteří již vytvořili první LLM prototypy a chtějí přejít na produkční úroveň
- **Architekti**, kteří se chtějí seznámit s osvědčenými vzory integrace AI, a zároveň jsou schopni prakticky experimentovat v Pythonu
- **Technické leadery** se zkušeností s hands-on prototypováním, kteří potřebují řešit škálování, bezpečnost a observabilitu AI služeb

### Pro koho kurz není určen
- Úplní začátečníci bez zkušeností s tvorbou základní AI aplikace typu chatbot
- Účastníci bez znalosti Pythonu – kurz je code-first a nevyužívá low-code platforem
- Specialisté s úzkým zaměřením na frontend – UI je v kurzu řešeno jen minimálně a není hlavním tématem

---

## Přehled lekcí

1. **Byznys požadavky a základní RAG chatbot** - Popisy produktů se sémantickým vyhledáváním
2. **Použití nástrojů: Webové vyhledávání, API, MCP** - Integrace MCP serverů, function calling, webové vyhledávání
3. **Znalostní báze z dokumentů, obrázků, videí** - Multimodální ingestace, hybridní vyhledávání, sémantická cache
4. **Agentní vyhledávání, grafová databáze a RAG fencing** - Retrieval na bázi nástrojů, grafové procházení, VIP filtrování, autentizace
5. **Multimodalita, paměť a hlasový chat** - Hlasová interakce, dlouhodobá personalizace
6. **Code interpreter a dynamické UI** - Analýza dat, generování vizualizací, MCP visualization server
7. **AI workflow orchestrace** - Automatizované zpracování stížností s Temporal
8. **Multi-agent systémy** - Spolupráce mezi specializovanými agenty (farmářské tržiště + kuchařské služby)
9. **Bezpečnost a evaluace** - Red teaming, LLM-as-judge, evaluační framework
10. **Observability a škálovatelné nasazení** - OpenTelemetry, Kubernetes, CI/CD, IaC

🎯 **[Detailní agenda lekcí s koncepty a technologiemi →](docs/Agenda.md)**

---

## Repository branches

- **`Lxx-teacher`** - Kompletní implementace pro instruktorskou demonstraci (každá lekce)
- **`Lxx-student`** - Výchozí bod s výzvami pro studenty k implementaci (každá lekce)
- **`main`** - Plná produkční verze se všemi funkcemi, testy a CI/CD

Studenti začínají z branch `Lxx-student` a směřují k řešení ukázanému v branch `Lxx-teacher`.

---

## Jak spustit projekt
Zde popisujeme finální fázi vývoje se všemi implementovanými funkcemi. Postupujte podle instruktora a individuálních lekcí pro více informací, jak postupujeme.

### Strategie branches
- `main`: Aktuální stav (všechny lekce dokončeny)
- `Lxx-teacher`: Řešení pro lekci xx (plně funkční kód)
- `Lxx-student`: Výchozí bod pro lekci xx (s TODO výzvami)

Příklad: Začněte L01 z `L01-student`, porovnejte s `L01-teacher` po dokončení.

### Služby podle lekcí
**Detailní instrukce**: Viz `README.md` každé lekce pro konkrétní kroky nastavení.

### Nasazení na Azure/Kubernetes (finální fáze)

1. Nasaďte infrastrukturu: `cd deploy/azure/infrastructure && terraform apply`
2. Sestavte a nahrajte kontejnery: `cd deploy/azure/docker_build && uv run build_and_push.py`
3. Nasaďte služby: `cd deploy/charts/demo && helm install dreamfarm .`
4. Nakonfigurujte Keycloak: `uv run identity/provision_keycloak.py`
5. Nakonfigurujte databázi: `uv run data/scripts/configure_postgresql.py`
6. Importujte data: `uv run data/scripts/import_all.py`
7. Přístup přes Ingress URL (poskytne `kubectl get ingress`)

---

## Technologický stack

**AI & LLM:** 
- **Platformy**: Azure OpenAI, OpenAI Platform
- **Modely**: GPT-5 (chat & reasoning), text-embedding-3-large (embeddings)
- **API**: Responses API, Realtime API (voice)

**Backend:** 
- **Jazyk**: Python 3.12+
- **Framework**: FastAPI
- **Data Validace**: Pydantic modely
- **ORM**: SQLAlchemy
- **Package Management**: uv (pyproject.toml)

**Databáze:** 
- **Relační**: PostgreSQL (Azure Database for PostgreSQL Flexible Server)
- **Vektorové vyhledávání**: pgvector rozšíření
- **Grafová databáze**: Apache AGE (taxonomie, produktové vztahy)

**Frontend:** 
- **Framework**: React + TypeScript
- **Chat UI**: @assistant-ui/react
- **Styling**: Tailwind CSS
- **Build Tool**: Vite
- **Realtime**: WebSocket pro hlasový režim

**Nástroje a integrace:**
- **MCP Protocol**: Model Context Protocol servery
- **Function Calling**: OpenAI function tools
- **Webové vyhledávání**: Tavily API
- **Stock API**: Vlastní REST endpoint

**Orchestrace:**
- **Workflow Engine**: Temporal (durable workflows)

**Multi-Agent:**
- **MCP Protocol**: Model Context Protocol servery
- **Agent Communication**: HTTP function calling
- **Pattern**: Agent-as-Tool

**Kvalita a bezpečnost:**
- **Evaluace**: DeepEval (LLM-as-judge metriky)
- **Red Teaming**: PyRIT (Microsoft security testing)

**Autentizace:** 
- **Identity Provider**: Keycloak
- **Protokol**: OAuth2/OIDC
- **Integrace**: FastAPI middleware

**Observability:** 
- **Tracing**: OpenTelemetry (distributed tracing)
- **Backend**: Grafana Tempo
- **LLM Observability**: Langfuse (volitelné)

**Deployment:** 
- **Kontejnerizace**: Docker, Docker Compose
- **Orchestrace**: Kubernetes (Azure AKS)
- **Package Management**: Helm charts
- **Infrastructure as Code**: Terraform (azurerm + azapi)
- **CI/CD**: GitHub Actions

---

## Struktura projektu

- `agents/` - AI agenti (DreamFarm, Chef) s FastAPI backendy
- `data/` - Databázová schémata, datové pipeline, import skripty
- `frontend/` - React UI s assistant-ui komponentami
- `tools/` - MCP servery (farmer tools, visualization, stock API)
- `deploy/` - Kubernetes charts, Docker konfigurace, Terraform IaC
- `docs/` - Kompletní architektonická a API dokumentace
- `lessons/` - Materiály a cvičení specifické pro lekce
- `identity/` - Keycloak provisioning skripty
- `orchestration/` - Temporal workflow definice

---

## Dokumentace

- **[Agenda](docs/Agenda.md)**
- **[Design.md](docs/Design.md)** - Přehled architektury a systémový design
- **[APIReference.md](docs/APIReference.md)** - Kompletní REST a WebSocket API specifikace
- **[DataSchemas.md](docs/DataSchemas.md)** - Databázová schémata a indexy
- **[RetrievalArchitecture.md](docs/RetrievalArchitecture.md)** - RAG, hybridní vyhledávání, sémantická cache
- **[ToolSpecifications.md](docs/ToolSpecifications.md)** - Všechny AI nástroje a MCP servery
- **[Observability.md](docs/Observability.md)** - OpenTelemetry tracing a monitoring
- **[CommonErrors.md](docs/CommonErrors.md)** - Průvodce řešením problémů
- **[ConfigurationReference.md](docs/ConfigurationReference.md)** - Reference environmentálních proměnných
- **[ImplementationLog.md](docs/ImplementationLog.md)** - Historie implementačních rozhodnutí 
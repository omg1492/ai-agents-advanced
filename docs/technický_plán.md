# Scénář společného projektu

## Byznys doména  
Virtuální **farmářské tržiště** propojuje malé lokální farmáře se zákazníky a odstraňuje bariéry spojené s logistikou, marketingem a sezónní poptávkou.  
Díky centralizované platformě farmáři získají spravedlivější výkupní ceny, přístup k datům o poptávce a možnost oslovit nové segmenty (restaurace, catering, firemní akce).  
Zákazníci naopak dostanou transparentní informace o původu surovin, čerstvější zboží a doplňkové služby (recepty, personalizovaná doporučení, příprava pokrmů).  

## Využití AI  
- Okamžité a srozumitelné odpovědi na otázky o původu, kvalitě a dostupnosti produktů.  
- Personalizovaná doporučení košíku a receptů podle sezónnosti, diety či alergií.  
- Hands-free hlasová interakce při vaření nebo na cestách.  
- Přehledné grafy a vizualizace nutričních dat s návrhy zdravějších alternativ.  
- Proaktivní řešení stížností a rychlé návrhy náhrad.  
- Sjednání kompletních cateringových balíčků ve spolupráci s kuchaři.

## Použité technologie  
- Retrieval-Augmented Generation nad dokumenty (pgvector, OpenAI embeddings).  
- MCP pro napojení interních API a web-search nástrojů.  
- Hybridní vyhledávání (full-text + vektor) a RAG fencing pro filtrování alergenů.  
- Znalostní graf propojující suroviny, recepty a sezónnost.  
- Real Voice Chat a dlouhodobá personalizační paměť.  
- Python Code Interpreter se sandboxem pro datovou analýzu a vizualizace.  
- Agentní orchestrace a multi-agentní systémy pro komplexní úkoly.  
- Bezpečnostní & evaluační framework, observabilita a škálovatelné nasazení.
- React UI (assistant-ui) pro chat a vizualizace

## Dvě větve projektu  
| Větev | Popis | Použití na hodině |
|-------|-------|------------------|
| **Plná verze** | Kompletní, předem připravená implementace. Více variant modelů, unit-testy, CI/CD. | Lektor demonstruje, sdílí best-practices a časté chyby. |
| **Kódování naživo** | Zjednodušená, inkrementální verze, psaná v lekci s GitHub Copilotem. | Studenti implementují, refaktorují a testují. |

## Inkrementy podle lekcí

### Lekce 01 – Business požadavky, architektura & základní chatbot nad dokumenty

#### Popis vylepšení a business přínos
Základní chatbot zpřístupní popisy produktů z farmy v přirozeném jazyce, takže zákazník ihned zjistí původ, kvalitu i dostupnost zboží.  
Rychlé a přesné odpovědi snižují zátěž podpory a zvyšují míru dokončených objednávek.

#### Technické aspekty plné verze
- CSV ingest → PostgreSQL (pgvector) + embeddings  
- Backend (FastAPI) + RAG  
- UI (React – assistant-ui)
  
#### Technické kroky - kódování naživo
- Backend + UI bez RAG → přidání RAG

#### Použité technologie a nástroje
- OpenAI API  
- PostgreSQL (pgvector)  
- Python (backend, FastAPI)  
- React UI (assistant-ui)  
- LangGraph (RAG)

### Lekce 02 – Používání nástrojů: Web search, API, MCP

#### Popis vylepšení a business přínos
Asistent kombinuje interní API s web-search, aby ukázal aktuální ceny, zásoby a recepty k vybranému produktu.  
Tím pomáhá zákazníkovi lépe plánovat nákup a zvyšuje průměrnou hodnotu košíku i konverzní poměr.

#### Technické aspekty plné verze
- MCP gateway + web-search + interní API jako nástroje  
- Rozšíření back-endu o nástrojové volání

#### Technické kroky – kódování naživo
- Připojení hotových MCP serverů + vytvoření jednoho vlastního

#### Použité technologie a nástroje
- MCP (tool gateway)  
- Web-search API  
- Interní REST/GraphQL API  
- Python (FastAPI)  
- OpenAI API

### Lekce 03 – Vytváření znalostní báze pro AI z dokumentů, obrázků a videí

#### Popis vylepšení a business přínos
Řada farmářů dodává popisy ve formě PDF dokumentů, nutričních tabulek nebo obrázků. Kromě toho existuje řada video recenzí, receptů na vaření a dalších tipů spojených s farmářskými produkty. Ty potřebujeme zpracovat a integrovat do znalostní báze, aby AI mohla lépe odpovídat na dotazy zákazníků. Nicméně, některé dokumenty nejsou určeny pro každého zákazníka, takže potřebujeme zajistit bezpečnost přístupu k nim. Navíc často chceme hledat ne podle významu, ale specificky podle třeba kódu produktu nebo farmy, takže potřebujeme i full-text vyhledávání. Pro často kladené otázky bychom mohli systém zrychlit pro uživatele a ještě ušetřit s využitím cachování.

#### Technické aspekty plné verze
- PDF/obrázky/audio → Markdown → embeddings  
- Hybrid search + tag-based RAG fencing

#### Technické kroky – kódování naživo
- PDF + audio → Markdown → embeddings, čistě sémantické hledání

#### Použité technologie a nástroje
- PyPDF / OCR → Markdown  
- Whisper (audio → text)  
- OpenAI embeddings  
- PostgreSQL (pgvector)

### Lekce 04 – Deep Research & Knowledge Graph

#### Popis vylepšení a business přínos
Znalostní graf propojí suroviny, recepty a sezónnost, takže AI doporučí ideální košík pro konkrétní událost i roční dobu.  
Díky cíleným doporučením se zvyšuje upsell a snižuje plýtvání sezónních produktů.

#### Technické aspekty plné verze
- Knowledge Graph + agentic RAG

#### Technické kroky – kódování naživo
- Základní graf + jednoduchý dotazovací agent

#### Použité technologie a nástroje
- Neo4j / Memgraph (knowledge graph)  
- LangGraph (agentic RAG)  
- Python

### Lekce 05 – Multimodalita, paměť & Real Voice Chat

#### Popis vylepšení a business přínos
Lekce rozšiřuje asistenta o Real Voice Chat, který umožní zákazníkovi ovládat systém hands-free při vaření či na cestách, a zároveň zavádí dlouhodobou personalizační paměť ukládající diety, alergeny či oblíbené recepty. Obě funkce společně zvyšují komfort používání i relevanci doporučení, což podporuje opakované nákupy.

#### Technické aspekty plné verze
- Real Voice Chat + dlouhodobá paměť (Redis)

#### Technické kroky – kódování naživo
- STT/TTS integrace + ukládání preferencí

#### Použité technologie a nástroje
- Real Voice Chat (STT/TTS)  
- Redis (long-term memory)  
- Python  
- OpenAI API

### Lekce 06 – Code Interpreter & Agentic UI

#### Popis vylepšení a business přínos
AI analyzuje nutriční a zdravotní data uživatele, vizualizuje je v přehledných grafech a navrhuje zdravější alternativy.  
Interaktivní infografiky zvyšují angažovanost a motivují ke koupi doporučených produktů.

#### Technické aspekty plné verze
- Python sandbox + automaticky generované UI (React card)

#### Technické kroky – kódování naživo
- Základní sandbox + první vizualizace

#### Použité technologie a nástroje
- Python sandbox (Code Interpreter)  
- Matplotlib / Plotly  
- React UI (assistant-ui)

### Lekce 07 – Orchestrace AI workflow

#### Popis vylepšení a business přínos
Automatizované workflow vyhodnotí stížnost, přiložené důkazy a pravidla nároku, aby okamžitě řešilo jasné případy a ostatní eskalovalo.  
Rychlá reakce zlepšuje NPS a snižuje provozní náklady podpory.

#### Technické aspekty plné verze
- Temporal orchestrace + model-routing (LiteLLM)

#### Technické kroky – kódování naživo
- Jednoduchý workflow pro řešení stížnosti

#### Použité technologie a nástroje
- Temporal  
- LiteLLM (model routing)  
- Python

### Lekce 08 – Multi-agent systémy

#### Popis vylepšení a business přínos
S rostoucí sofistikovaností AI agenta a rozšiřujícím se byznysem virtuálního tržiště vzniká potřeba vyvíjet některé části systému víc nezávisle a soustředit se na specializovaného agenta. Nový obchodní nápad má přivést na tržiště i kuchaře, kteří mohou nabízet služby pro různé oslavy a firemní akce a propojit tak dodavatele farmářských produktů, jejich zákazníků a služeb přípravy jídla. Na základě požadavku uživatele musí vzájemnou interakcí původního agenta (farmářské tržiště) a nového agenta (tržiště kuchařů a služeb) vzniknout dohoda který kuchař z jakých surovin co by zajistil a jaká je celková cena a tyto varianty nabídnout uživateli. 

#### Technické aspekty plné verze
- Více agentů v LangGraph + komunikace přes Redis

#### Technické kroky – kódování naživo
- Původní agent + kuchařský agent → dohoda o cateringu

#### Použité technologie a nástroje
- LangGraph  
- Redis (pub/sub)  
- Python

### Lekce 09 – Bezpečnost & Evaluace

#### Popis vylepšení a business přínos
Jídlo a zdraví jsou citlivá témata a systém musí být bezpečný a důvěryhodný, jinak je tu reputační riziko. Kromě toho mohou být některá témata kontroverzní a pro některé uživatele nepříjemná (například náboženská omezení ve stravě, intolerance, vegetariánství apod.). Navíc přesnost odpovědí je důležitá, protože chyby v popisu či doporučení produktů mohou vést k nespokojenosti a ztrátě důvěry. Každá změna (verze) systému tak musí být testována a vyhodnocena stejně jako zpětná vazba uživatelů a to jak před nasazením, na základě reakce na hodnocení uživatele tak i průběžně v produkci přes A/B testování a evaluace.

#### Technické aspekty plné verze
- PyRIT red-teaming + Langfuse auto-eval + OTel logy

#### Technické kroky – kódování naživo
- První bezpečnostní testy + feedback loop

#### Použité technologie a nástroje
- PyRIT  
- Langfuse  
- OpenTelemetry

### Lekce 10 – Observabilita & Škálovatelné nasazení

#### Popis vylepšení a business přínos
Komplexní telemetry a elastické škálování zajistí stabilní provoz během sezónních špiček a transparentní monitoring nákladů.  
Provozní tým tak může včas optimalizovat výkon i rozpočet.

#### Technické aspekty plné verze
- Kubernetes + GitHub Actions + Terraform + OTel

#### Technické kroky – kódování naživo
- Minimální deployment do K8s + metriky

#### Použité technologie a nástroje
- Kubernetes  
- GitHub Actions (CI/CD)  
- Terraform  
- OpenTelemetry
- OpenTelemetry

### Lekce 10 – Observabilita & Škálovatelné nasazení

#### Popis vylepšení a business přínos
Komplexní telemetry a elastické škálování zajistí stabilní provoz během sezónních špiček a transparentní monitoring nákladů.  
Provozní tým tak může včas optimalizovat výkon i rozpočet.

#### Technické aspekty plné verze
- TBD

#### Technické kroky – kódování naživo
- TBD

#### Použité technologie a nástroje
- Kubernetes  
- GitHub Actions (CI/CD)  
- Terraform  
- OpenTelemetry

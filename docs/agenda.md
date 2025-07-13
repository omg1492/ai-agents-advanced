# Agenda kurzu

### Lekce 01 – Business požadavky, architektura & základní chatbot nad dokumenty
Základní chatbot zpřístupní popisy produktů z farmy v přirozeném jazyce, takže zákazník ihned zjistí původ, kvalitu i dostupnost zboží. Rychlé a přesné odpovědi snižují zátěž podpory a zvyšují míru dokončených objednávek.  

**Koncepty:**
- RAG
- Embeddings
- Vektorová databáze  

**Technologie:**
- OpenAI API
- PostgreSQL (pgvector)
- Python (FastAPI, Streamlit)
- LangGraph

### Lekce 02 – Používání nástrojů: Web search, API, MCP
Asistent kombinuje interní API s web-search, aby ukázal aktuální ceny, zásoby a recepty k vybranému produktu. Tím pomáhá zákazníkovi lépe plánovat nákup a zvyšuje průměrnou hodnotu košíku i konverzní poměr.  

**Koncepty:**
- Tool-use
- API gateway
- Web-search  

**Technologie:**
- MCP
- REST/GraphQL
- Python (FastAPI)
- OpenAI API

### Lekce 03 – Vytváření znalostní báze pro AI z dokumentů, obrázků a videí
Řada farmářů dodává popisy ve formě PDF dokumentů, nutričních tabulek nebo obrázků. Kromě toho existuje řada video recenzí, receptů na vaření a dalších tipů spojených s farmářskými produkty. Ty potřebujeme zpracovat a integrovat do znalostní báze, aby AI mohla lépe odpovídat na dotazy zákazníků. Nicméně, některé dokumenty nejsou určeny pro každého zákazníka, takže potřebujeme zajistit bezpečnost přístupu k nim. Navíc často chceme hledat ne podle významu, ale specificky podle třeba kódu produktu nebo farmy, takže potřebujeme i full-text vyhledávání. Pro často kladené otázky bychom mohli systém zrychlit pro uživatele a ještě ušetřit s využitím cachování.  

**Koncepty:**
- Data ingest
- Hybrid search
- RAG fencing
- Semantic cache  

**Technologie:**
- PyPDF/OCR
- Whisper
- OpenAI embeddings
- PostgreSQL (pgvector)

### Lekce 04 – Deep Research & Knowledge Graph
Znalostní graf propojí suroviny, recepty a sezónnost, takže AI doporučí ideální košík pro konkrétní událost i roční dobu. Díky cíleným doporučením se zvyšuje upsell a snižuje plýtvání sezónních produktů.  

**Koncepty:**
- Knowledge graph
- Agentic RAG
- Deep research  

**Technologie:**
- Neo4j/Memgraph
- LangGraph
- Python

### Lekce 05 – Multimodalita, paměť & Real Voice Chat
Lekce rozšiřuje asistenta o Real Voice Chat, který umožní zákazníkovi ovládat systém hands-free při vaření či na cestách, a zároveň zavádí dlouhodobou personalizační paměť ukládající diety, alergeny či oblíbené recepty. Obě funkce společně zvyšují komfort používání i relevanci doporučení, což podporuje opakované nákupy.  

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

### Lekce 06 – Code Interpreter & Agentic UI
AI analyzuje nutriční a zdravotní data uživatele, vizualizuje je v přehledných grafech a navrhuje zdravější alternativy. Interaktivní infografiky zvyšují angažovanost a motivují ke koupi doporučených produktů.  

**Koncepty:**
- Code interpreter
- Data analysis
- Dynamic UI generation  

**Technologie:**
- Python sandbox
- Matplotlib/Plotly
- React

### Lekce 07 – Orchestrace AI workflow
Automatizované workflow vyhodnotí stížnost, přiložené důkazy a pravidla nároku, aby okamžitě řešilo jasné případy a ostatní eskalovalo. Rychlá reakce zlepšuje NPS a snižuje provozní náklady podpory.  

**Koncepty:**
- Agent orchestration
- Workflow automation
- Model routing  

**Technologie:**
- Temporal
- LiteLLM
- Python

### Lekce 08 – Multi-agent systémy
S rostoucí sofistikovaností AI agenta a rozšiřujícím se byznysem virtuálního tržiště vzniká potřeba vyvíjet některé části systému víc nezávisle a soustředit se na specializovaného agenta. Nový obchodní nápad má přivést na tržiště i kuchaře, kteří mohou nabízet služby pro různé oslavy a firemní akce a propojit tak dodavatele farmářských produktů, jejich zákazníků a služeb přípravy jídla. Na základě požadavku uživatele musí vzájemnou interakcí původního agenta (farmářské tržiště) a nového agenta (tržiště kuchařů a služeb) vzniknout dohoda který kuchař z jakých surovin co by zajistil a jaká je celková cena a tyto varianty nabídnout uživateli.  

**Koncepty:**
- Multi-agent systems
- Agent collaboration  

**Technologie:**
- LangGraph
- Redis (pub/sub)
- Python

### Lekce 09 – Bezpečnost & Evaluace
Jídlo a zdraví jsou citlivá témata a systém musí být bezpečný a důvěryhodný, jinak je tu reputační riziko. Kromě toho mohou být některá témata kontroverzní a pro některé uživatele nepříjemná (například náboženská omezení ve stravě, intolerance, vegetariánství apod.). Navíc přesnost odpovědí je důležitá, protože chyby v popisu či doporučení produktů mohou vést k nespokojenosti a ztrátě důvěry. Každá změna (verze) systému tak musí být testována a vyhodnocena stejně jako zpětná vazba uživatelů a to jak před nasazením, na základě reakce na hodnocení uživatele tak i průběžně v produkci přes A/B testování a evaluace.  

**Koncepty:**
- AI security
- Red teaming
- LLM-as-judge
- Evaluation framework  

**Technologie:**
- PyRIT
- Langfuse
- OpenTelemetry

### Lekce 10 – Observabilita & Škálovatelné nasazení
Komplexní telemetry a elastické škálování zajistí stabilní provoz během sezónních špiček a transparentní monitoring nákladů. Provozní tým tak může včas optimalizovat výkon i rozpočet.  

**Koncepty:**
- Observability
- Scalable deployment
- CI/CD
- IaC  

**Technologie:**
- Kubernetes
- GitHub Actions
- Terraform
- OpenTelemetry

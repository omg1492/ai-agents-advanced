# Lekce

## 1. lekce: Business požadavky, architektura a základní chatbot nad dokumenty

Základní chatbot zpřístupní popisy produktů z farmy v přirozeném jazyce, takže zákazník ihned zjistí původ, kvalitu i dostupnost zboží. Rychlé a přesné odpovědi snižují zátěž podpory a zvyšují míru dokončených objednávek.

- OpenAI backend přes FastAPI a jednoduchý RAG do PostgreSQL  
- Data pipeline: CSV s popisky produktu -> primitivní embeddings do pgvector  
- Základní frontend (React postavený na assistant-ui)

**Praktické cvičení:** 

- Dostanete základní UI, databázi a backend bez RAG  
- Zajistíme vektorizaci (embeddings) dat do pgvector pro sémantické vyhledávání  
- Přidáme RAG do backendu a vyzkoušíme
- Volitelně přidáme do výstupu reference

**Výstupy z lekce:** (Umím…)

- Udělat embeddings a uložit do databáze  
- Sémanticky vyhledávat  

**Použité technologie:**

- OpenAI GPT 5
- PostgreSQL a pgvector
- React frontend
- Docker Compose
- FastAPI pro implementaci backend API v Pythonu
- Embeddings modely a hledání cosinové podobnosti

## 2. lekce: Používání nástrojů: Web search, API, MCP

Asistent kombinuje interní API, MCP nástoje a web-search, aby ukázal aktuální zásoby, sezónní produkty a recepty.  Tím pomáhá zákazníkovi lépe plánovat nákup a zvyšuje průměrnou hodnotu košíku i konverzní poměr.

- Vytvoříme MCP server s nástroji a napojíme do agenta
- Vytvoříme vlastní nástroj (function calling) s přístupem na interní API se skladovými zásobami
- MCP gateway + web-search + interní API jako nástroje    
- Rozšíření backendu o nástrojové volání

**Praktické cvičení:** 

- Připojení hotových MCP serverů + vytvoření jednoho vlastního
- Function calling
- Volitelně nasazení gateway pro konverzi API na MCP a napojení do agenta

**Výstupy z lekce:** (Umím…)

- Přidat různé nástroje k LLM  
- Přidat nástroje pro vyhledávání na Internetu
- Vytvořit a napojit MCP Server
- Použít vlastní nástroje přes function calling

**Použité technologie:**
- MCP servery
- GPT 5 a volání nástrojů: MCP, function calling
- Tavily search MCP server

## 3. lekce: Vytváření znalostní báze pro AI z dokumentů, obrázků a videí

Řada farmářů dodává popisy ve formě PDF dokumentů nebo ani kvalitní popisy nemá a dodá jen obrázek produktu. Kromě toho existuje řada video recenzí, receptů na vaření a dalších tipů spojených s farmářskými produkty. Ty potřebujeme zpracovat a integrovat do znalostní báze, aby AI mohla lépe odpovídat na dotazy zákazníků. Navíc často chceme hledat ne podle významu, ale specificky podle třeba kódu produktu nebo farmy, takže potřebujeme i full-text vyhledávání. Pro často kladené otázky bychom mohli systém zrychlit pro uživatele a ještě ušetřit s využitím cachování.  

- Zpracování PDF dokumentů, obrázků a audia do Markdown a následně embeddings pro sémantické vyhledávání 
- Zpracování video upoutávek a recenzí 
- Hybridní search (keyword search + semantic search + Reciprocal Rank Fusion)
- Semantický caching častých otázek

**Praktické cvičení:** 

- PDF processing  
- Image processing  
- Speech-to-text s Whisper modelem
- Implementace hybridního vyhledávání
- Semantické cachování

**Výstupy z lekce:** (Umím…)

- Zpracovat dokumenty, obrázky, video a audio a přidat do sémantického vyhledávání  
- Srovnat výsledky a výhody keyword vs. semantic search a metody jejich kombinace
- Připravit a používat semantický caching

**Použité technologie:**

- MarkItDown
- OpenAI Whisper
- ffmpeg
- PostgreSQL full-text search

## 4. lekce: Agentic Search, Knowledge Graph & RAG Fencing

Implementace agentic (nástrojového) vyhledávání kde LLM rozhoduje o výběru vyhledávacích strategií, základ znalostního grafu v PostgreSQL/AGE pro strukturální podobnost produktů, a VIP fencing pro řízený přístup k prémiovým produktům s autentizací přes Keycloak.

- Agentic search s function calling (semantic search, keyword search, graph tools)
- VIP fencing - filtrování produktů podle uživatelských oprávnění před promptem
- Keycloak autentizace s demo uživateli (user1, vipuser)
- Knowledge graph v Apache AGE (producenti, produkty, alergeny, certifikace)
- Dva grafové nástroje: BFS taxonomy search a DFS similarity search
- HyDE enhancement pro sémantické vyhledávání

**Praktické cvičení:** 

- Implementace nástrojového vyhledávání (function calling)
- Nastavení Keycloak autentizace a VIP fencing
- Import znalostního grafu do AGE
- Vytvoření BFS/DFS grafových nástrojů
- Testování s různými uživatelskými oprávněními

**Výstupy z lekce:** (Umím…)

- Implementovat agentic search s tool calling
- Nastavit autentizaci a autorizaci s Keycloak
- Vytvořit a využít znalostní graf v PostgreSQL/AGE
- Implementovat VIP fencing pro bezpečný přístup k datům
- Použít grafové traversal algoritmy (BFS/DFS)

**Použité technologie:**

- AGE extension pro PostgreSQL
- Keycloak pro autentizaci
- OpenAI function calling
- FastAPI backend s tool integration
- React frontend s OAuth2 flow

## 5. lekce: Multimodalita, paměť a Real Voice Chat

Lekce rozšiřuje asistenta o Real Voice Chat, který umožní zákazníkovi ovládat systém hands-free při vaření či na cestách, a zároveň zavádí dlouhodobou personalizační paměť ukládající diety, alergeny či oblíbené recepty. Obě funkce společně zvyšují komfort používání i relevanci doporučení, což podporuje opakované nákupy.

- Hlasový chat v reálném čase  
- Implementace chytré paměti (konverzační session paměť, historická paměť, uživatelská paměť)

**Praktické cvičení:** 

- Přidání hlasu na vstup i výstup chatu  
- Implementace základní uživatelské paměti

**Výstupy z lekce:** (Umím…)

- Přidat hlasový interface  
- Implementovat paměť

## 6. lekce: Code Interpreter a Agentic UI (MCP Vizualizace)

AI analyzuje nutriční a zdravotní data uživatele, vizualizuje je v přehledných grafech a navrhuje zdravější alternativy. Kromě toho dokáže vytvářet interaktivní HTML infografiky pomocí MCP Visualization serveru – moderní kartičky s gradienty, animacemi a responzivním designem zobrazované v sandboxovaných iframe. Interaktivní infografiky zvyšují angažovanost a motivují ke koupi doporučených produktů.

- Grafy a výpočty s využitím Python a Code Interpreter sandbox  
- Ad-hoc generované HTML infografiky přes MCP Visualization server
- Bezpečné zobrazení pomocí sandboxovaných iframe (allow-same-origin only)
- In-memory artifact storage s 1hodinovou expirací

**Praktické cvičení:** 

- Code Interpreter: Analýza CSV dat a vytvoření grafů
- MCP Visualization: Vytvoření interaktivních HTML kartiček a infografik
- Integrace obou přístupů pro komplexní vizualizace

**Výstupy z lekce:** (Umím…)

- Využít code interpreter koncept pro zpracování dat, výpočty nebo tvorbu grafů a diagramů  
- Využít MCP server pro generování interaktivních HTML vizualizací
- Bezpečně zobrazit dynamický obsah v sandboxovaných iframe
- Spravovat lifecycle artifacts (storage, expiry, cleanup)

## 7. lekce: Orchestrace AI workflow

Automatizované workflow vyhodnotí stížnost, přiložené důkazy a pravidla nároku, aby okamžitě řešilo jasné případy a ostatní eskalovalo.  Rychlá reakce zlepšuje NPS a snižuje provozní náklady podpory.

- Code-first orchestrační platforma pro byznys workflow (AI agenti s větší autonomií)
- Durable workflows s Temporal pro spolehlivost a audit trail
- Structured outputs (Pydantic) pro type-safe rozhodování
- Policy-based decision making s few-shot examples

**Praktické cvičení:** 

- Vytvoříme workflow pro řešení stížnosti zákazníka s Temporal
- Implementujeme 6-fázový proces: klasifikace → extrakce → profil → rozhodnutí → řešení
- Vyzkoušíme různé scénáře (validní stížnost, eskalace, ne-stížnost)

**Výstupy z lekce:** (Umím…)

- Využít Temporal pro durable AI workflows
- Implementovat policy-based decision making s LLM
- Oddělit workflow logiku od side-effectů (activities)
- Využít structured outputs pro type-safe komunikaci s LLM
- Využít AI na pozadí zpracování workflow, nejen v chatu

## 8. lekce: Multi-agent systémy

S rostoucí sofistikovaností AI agenta a rozšiřujícím se byznysem virtuálního tržiště vzniká potřeba vyvíjet některé části systému víc nezávisle a soustředit se na specializovaného agenta. Nový obchodní nápad má přivést na tržiště i kuchaře, kteří mohou nabízet služby pro různé oslavy a firemní akce a propojit tak dodavatele farmářských produktů, jejich zákazníků a služeb přípravy jídla. Na základě požadavku uživatele musí vzájemnou interakcí původního agenta (farmářské tržiště) a nového agenta (tržiště kuchařů a služeb) vzniknout dohoda který kuchař z jakých surovin co by zajistil a jaká je celková cena a tyto varianty nabídnout uživateli. 

- Framework pro vytvoření spolupracujících agentů a komunikace mezi nimi  
- Škálovatelné řešení - každý agent jako samostatný deployment, ne monolit

**Praktické cvičení:** 

- K původnímu agentovi vytvoříme kuchařského agenta  
- Zajistíme, aby společně našli dohodu o cateringu na základě požadavků zákazníka

**Výstupy z lekce:** (Umím…)

- Použít framework pro vytváření vzájemně komunikujících agentů

## 9. lekce: Bezpečnost a evaluace

Jídlo a zdraví jsou citlivá témata a systém musí být bezpečný a důvěryhodný, jinak je tu reputační riziko. Kromě toho mohou být některá témata kontroverzní a pro některé uživatele nepříjemná (například náboženská omezení ve stravě, intolerance, vegetariánství apod.). Navíc přesnost odpovědí je důležitá, protože chyby v popisu či doporučení produktů mohou vést k nespokojenosti a ztrátě důvěry. Každá změna (verze) systému tak musí být testována a vyhodnocena stejně jako zpětná vazba uživatelů a to jak před nasazením, na základě reakce na hodnocení uživatele tak i průběžně v produkci přes A/B testování a evaluace.

- Red-teaming a testování bezpečnosti agentů (PyRIT)  
- Monitoring a automatizovaná evaluace kvality řešení, LLM-as-judge (LangFuse)

**Praktické cvičení:** 

- Přidáme bezpečnostní testování  
- Přidáme zpětovazební smyčku pro hodnocení kvality

**Výstupy z lekce:** (Umím…)

- Použít red-teaming pro testování bezpečnosti řešení  
- Sbírat a vyhodnocovat telemetrii i kvalitu odpovědí

## 10. lekce: Observabilita a škálovatelné nasazení

Komplexní telemetrie a elastické škálování zajistí stabilní provoz během sezónních špiček a transparentní monitoring nákladů.  Provozní tým tak může včas optimalizovat výkon i rozpočet.

- Nasazení do Kubernetes přes GitOps s ArgoCD  
- Škálování  
- Telemetrie a trasování (OpenTelemetry)

**Praktické cvičení:** 

- Nasazení do Kubernetes clusteru  
- Sběr a vyhodnocení telemetrie

**Výstupy z lekce:** (Umím…)

- Nasadit aplikaci do Kubernetes  
- Použít OpenTelemetry pro observabilitu

POSUN PO LEKCÍCH:

**\> Po 1 týdnu v kurzu:**

* Budete mít AI chatbot s pokročilým využíváním vašich firemních nástrojů a znalostí včetně pokročilých metod a architektur vyhledávání, třídění, zkoumání a to včetně agentic přístupů

**\> Po 2 týdnu v kurzu:**

* Budete mít pokročilou AI aplikaci s multi-modalitou, autonomním workflow a auto-generovanými grafickými výstupy

**\> Po absolvování kurzu:**

* Budete mít pokročilou AI aplikaci včetně multi-agent prvků, kterou máte otestovanou na bezpečnost, průběžně sledujete kvalitu, monitorujete ji a nasazujete škálovatelným způsobem.  
  


# Software checklist \- co by měl klient vědět předem?

1) Na jakém **zařízení** bude lektor pracovat?   
   - Bude stačit počítač/notebook/tablet?  
     počítač  
   - Jsou nějaké HW nároky softwarů v kurzu? (RAM, procesor, grafická karta)  
     ne  
   - Je potřeba nějaké další zařízení?  
     ne  
   - Jsou potřeba dva monitory?  
     ano - na jednom monitoru/zařízení poslouchat a na druhém pracovat  
2) V jakém **operačním prostředí** se bude pracovat?  
- Pracuje lektor ve Windows/Mac/Linux?

  nehraje roli

- Má rozhraní počítače nebo softwaru v jiném než českém jazyce? 

  angličtina

3) Bude se v rámci kurzu pracovat s nějakým **softwarem**?

              viz požadavky

- Kolik konkrétních softwarů a aplikací (včetně plug-inů, presetů) se bude v rámci kurzu používat celkově?  
- V jaké softwarové verzi?   
- Je možné plnohodnotně použít nějakou jinou/starší verzi?  
- Je software placený nebo má free verzi/trial?   
  - Pokud ano:  
    -  Za jakých podmínek a kterou verzi má student pořídit?  
    -  Kdy ji bude potřebovat?  
    -  Na jak dlouho je k dispozici trial verze?  
- Liší se nějak software nebo jeho rozhraní v závislosti na operačním systému?  
- Je software v AJ/ČJ?  
- Na jaký support odkázat klienty? Český prodejce/evropský prodejce?  
4) **Kdy** se bude daný software používat?  
   vždy  
- Je potřeba jej mít stažený a připravený již na první lekci nebo se to bude instalovat spolu s lektorem?   
- Na kdy bude přibližně potřeba případný další software?  
- Je třeba se na to celé nějak dopředu připravit?   
5) Pokud bude v kurzu používán nějaký **dodatečný HW:**  
   **ne**  
- Jaký konkrétní HW to bude? (jakou verzi má lektor? Liší se případně v něčem?)  
- Kdy jej zašleme a na kolikátou lekci je třeba jej mít připravený?  
- Pokud je pořízení HW na klientovi, kde bude pro něj nejlepší jej zakoupit?


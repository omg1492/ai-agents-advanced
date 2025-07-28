# **📍 Cílová skupina kurzu**

* 1\. cílová skupina: **Vývojář** nebo **data scientist**  
  * 3 bolesti:  
    * Tutoriály na AI aplikace končí u základních chatbotů a jednoduchých agentů, to už znám, potřebuji se posunout dál  
    * Chybí mi end-to-end pohled od vývoje a architektury až po monitoring, provoz, škálování a zabezpečení AI aplikací  
    * Nechci se učit spoustu variant a poznávat každý framework, chci se soustředit na konkrétní cestu vytvoření a provozování pokročilé AI aplikace  
  * 3 řešení:  
    * V tomto kurzu půjdeme daleko za rámec základních AI aplikací a prozkoumáme multi-modalitu, agentic search, nástroje i multi-agentní systémy.  
    * V kurzu se soustředíme nejen na aplikační a AI komponenty, ale i bezpečnost, nasazování, škálovatelnost, monitoring i pokročilé datové koncepty.  
    * V tomto kurzu společně budujeme aplikaci a postupně rozšiřujeme její možnosti a plníme byznys požadavky. Účelem není pohrát si s nepřeberným množstvím variant řešení, ale vzít vždy jedno a posouvat aplikace dopředu.   
* 2\. cílová skupina: **Architekt** schopný praktického experimentování  
  * 3 bolesti:  
    * Potřebuji pochopit architektonické a provozní aspekty pokročilé AI aplikace \- agenti, práce s daty, bezpečnost, škálovatelnost  
    * Potřebuji znát limity schopností různých AI přístupů, abych dokázal navrhovat správné řešení pro dané byznys zadání.   
    * Potřebuji nabrat praktickou zkušenost s budováním pokročilé AI aplikace, ale neumím si to sám celé postavit a vyzkoušet.  
  * 3 řešení:  
    * V tomto kurzu půjdeme daleko za rámec základních AI aplikací a nezůstaneme jen u vývoje, ale přijde na řadu i bezpečnost, evaluace, monitoring, nasazení a škálovatelnost.  
    * V kurzu začínáme od základní aplikace a přidáváme komponenty a postupy, abychom plnili další a další požadavky byznysu. Díky tomu uvidíte na co nám stačil základ, kdy jsme museli použít jinou techniku a kdy úplně  jiný přístup.  
    * Kurz využívá AI pro vibe-coding tak, abychom v krátkém čase i bez velmi hlubokých znalostí programování dokázali prožít vznik pokročilé aplikace a naučit se na tom co nejvíc \- chceme poznat architekturu, ale naživo, ne na papíře, a vědět jak věci dělat, ne se nutné zlepšit v psaní samotného kodu.  
* 3\. cílová skupina: **Technologický lídr** schopný prototypování  
  * 3 bolesti:  
    * Chci pochopit možnosti AI aplikací za rámec chatování \- deep research, pokročilá práce s daty, multi-modalita, autonomní agenti, generované UI, trvalé vylepšování a evoluce produktu   
    * Nechci přehled technologií, ale příklad naplňování nějakého byznys scénáře, kde je AI použito, jak a proč  
    * Programovat v Python umím, ale necítím se na to, že sám zvládnu postavit celé řešení end-to-end, abych nabral zkušenosti a dokázal na základě nich určovat technologický směr firmy nebo produktu.  
  * 3 řešení:  
    * Kurz jde za rámec základních AI aplikací a dostane se i k složitějším tématům jako je deep research, agentic search, multi-modalita, autonomní agenti nebo multi-agentní systémy.  
    * V tomto kurzu společně budujeme řešení pro fiktivní byznys, každá lekce přidává funkcionalitu do naší aplikace.  
    * Kurz využívá AI pro vibe-coding tak, abychom v krátkém čase i bez velmi hlubokých znalostí programování dokázali prožít vznik pokročilé aplikace a naučit se na tom co nejvíc \- chceme poznat architekturu, ale naživo, ne na papíře, a vědět jak věci dělat, ne se nutné zlepšit v psaní samotného kodu.

---

# **📖 Doplňující informace**

**Další požadavky na publikum:** 

- Praktická znalost Pythonu (funkce, moduly, virtuální prostředí).    
- Zkušenost s vytvořením jednoduchého chatbotu v Pythonu.    
- Základní práce s LLM: tvorba promptů, volání OpenAI API nebo ekvivalentu.  

**Pro koho kurz NENÍ:** 

- Úplní začátečníci bez zkušeností s tvorbou základní AI aplikace typu chatbot.    
- Účastníci bez znalosti Pythonu – kurz je code-first a nevyužívá low-code platforem.    
- Specialisté s úzkým zaměřením na frontend – UI je v kurzu řešeno jen minimálně a není hlavním tématem.

---

# **⚙️ Technické požadavky**

**Software:**   
IDE’s: 

- Kurz probíhá ve **Visual Studio Code**, nicméně Cursor nebo Windsurf je přípustný

Služby a nástroje: 

- Placené **OpenAI** API přes Azure OpenAI Service (trial Azure bývá k dispozici) nebo OpenAI API ([https://openai.com/api/](https://openai.com/api/)) s modely minimálně gpt-4.1 a o3. Doporučený kredit 20 USD.  
- Kubernetes v cloudu (AKS, EKS, GKE) nebo na lokálním počítači (např. Rancher Desktop)  
- Docker v Windows/Mac/Linux počítači (doporučujeme Rancher Desktop)  
- Kurz předpokladá placenou verzi **GitHub Copilot** (20 USD), nicméně licence Cursor či Windsurf je přípustná

Technologies/Languages: 

- **Python je nutná podmínka**  
- Hodí se základní znalost GitHub, PostgreSQL, React, OpenAI API, OpenTelemetry, Kubernetes a Terraform

*GitHub \- ano/ne \- pokud ano, bude zapotřebí placený pro github actions?*  
Ano, potřebujeme, stačí verze zdarma 

*Označte prosím červeně ty služby, které jsou placené (nejsou pro studenty zdarma).*

**Hardware:**  
Počítač lokální nebo v cloudu (Codespaces, VM) s Window nebo Linux nebo MacOS s možností provozovat Python a VS Code

# **📚 Lekce**

## **1\. lekce: Business požadavky, architektura a základní chatbot nad dokumenty**

Základní chatbot zpřístupní popisy produktů z farmy v přirozeném jazyce, takže zákazník ihned zjistí původ, kvalitu i dostupnost zboží. Rychlé a přesné odpovědi snižují zátěž podpory a zvyšují míru dokončených objednávek.

- OpenAI backend přes FastAPI a jednoduchý RAG do PostgreSQL  
- Data pipeline: CSV s popisky produktu \-\> primitivní embeddings do pgvector  
- Základní frontend (React postavený na assistant-ui)

**Praktické cvičení:** 

- Dostanete základní UI, databázi a backend bez RAG  
- Zajistíme vektorizaci (embeddings) dat do pgvector pro sémantické vyhledávání  
- Přidáme RAG do backendu a vyzkoušíme

**Výstupy z lekce:** (Umím…)

- Udělat embeddings a uložit do databáze  
- Sémanticky vyhledávat  
- Přidat do backendu základní RAG jako nástroj

## **2\. lekce: Používání nástrojů: Web search, API, MCP**

Asistent kombinuje interní API s web-search, aby ukázal aktuální ceny, zásoby a recepty k vybranému produktu.  Tím pomáhá zákazníkovi lépe plánovat nákup a zvyšuje průměrnou hodnotu košíku i konverzní poměr.

- MCP gateway \+ web-search \+ interní API jako nástroje    
- Rozšíření backendu o nástrojové volání

**Praktické cvičení:** 

- Připojení hotových MCP serverů \+ vytvoření jednoho vlastního

**Výstupy z lekce:** (Umím…)

- Přidat různé nástroje k LLM  
- Vytvořit a napojit MCP Server

## **3\. lekce: Vytváření znalostní báze pro AI z dokumentů, obrázků a videí**

Řada farmářů dodává popisy ve formě PDF dokumentů, nutričních tabulek nebo obrázků. Kromě toho existuje řada video recenzí, receptů na vaření a dalších tipů spojených s farmářskými produkty. Ty potřebujeme zpracovat a integrovat do znalostní báze, aby AI mohla lépe odpovídat na dotazy zákazníků. Nicméně, některé dokumenty nejsou určeny pro každého zákazníka, takže potřebujeme zajistit bezpečnost přístupu k nim. Navíc často chceme hledat ne podle významu, ale specificky podle třeba kódu produktu nebo farmy, takže potřebujeme i full-text vyhledávání. Pro často kladené otázky bychom mohli systém zrychlit pro uživatele a ještě ušetřit s využitím cachování.  

- Zpracování PDF dokumentů, obrázků a audia do Markdown a následně embeddings pro sémantické vyhledávání  
- Hybridní search (keyword search \+ semantic search \+ Reciprocal Rank Fusion)

**Praktické cvičení:** 

- PDF processing  
- Image extrakce  
- Speech-to-text

**Výstupy z lekce:** (Umím…)

- Zpracovat dokumenty, obrázky a audio a přidat do sémantického vyhledávání  
- Srovnat výsledky a výhody keyword vs. semantic search a metody jejich kombinace

## **4\. lekce: Deep Research a Knowledge Graph**

Znalostní graf propojí suroviny, recepty a sezónnost, takže AI doporučí ideální košík pro konkrétní událost i roční dobu. Díky cíleným doporučením se zvyšuje upsell a snižuje plýtvání sezónních produktů.

- Hierarchické hledání (depth first vs. breadth first)  
- Uspořádání informací do grafu (Knowledge Graph)  
- Agentic search (iterativní vyhledávání řízené AI)

**Praktické cvičení:** 

- Vytvoření jednoduché hierarchie využitím LLM sumarizací  
- Sestavení základního grafu informací a uložení v databázi  
- Jednoduchý agentic multi-step search

**Výstupy z lekce:** (Umím…)

- Vytvořit a využít hierarchický model dat  
- Vytvořit graf informací a uložit v databázi  
- Vytvořit agentic multi-step search

## **5\. lekce: Multimodalita, paměť a Real Voice Chat**

Lekce rozšiřuje asistenta o Real Voice Chat, který umožní zákazníkovi ovládat systém hands-free při vaření či na cestách, a zároveň zavádí dlouhodobou personalizační paměť ukládající diety, alergeny či oblíbené recepty. Obě funkce společně zvyšují komfort používání i relevanci doporučení, což podporuje opakované nákupy.

- Hlasový chat v reálném čase  
- Implementace chytré paměti (konverzační session paměť, historická paměť, uživatelská paměť)

**Praktické cvičení:** 

- Přidání hlasu na vstup i výstup chatu  
- Implementace základní uživatelské paměti

**Výstupy z lekce:** (Umím…)

- Přidat hlasový interface  
- Implementovat paměť

## **6\. lekce: Code Interpreter a Agentic UI**

AI analyzuje nutriční a zdravotní data uživatele, vizualizuje je v přehledných grafech a navrhuje zdravější alternativy. Interaktivní infografiky zvyšují angažovanost a motivují ke koupi doporučených produktů.

- Grafy a výpočty s využitím Python a Code Interpreter sandbox  
- Ad-hoc generované UI s HTML/CSS nebo React v sandboxu

**Praktické cvičení:** 

- Základní ad-hoc AI vizualizace pro uživatele

**Výstupy z lekce:** (Umím…)

- Využít code interpreter koncept pro zpracování dat, výpočty nebo tvorbu grafů a diagramů  
- Využít kódování HTML/CSS nebo React a bezpečné zobrazení výstupů uživateli

## **7\. lekce: Orchestrace AI workflow**

Automatizované workflow vyhodnotí stížnost, přiložené důkazy a pravidla nároku, aby okamžitě řešilo jasné případy a ostatní eskalovalo.  Rychlá reakce zlepšuje NPS a snižuje provozní náklady podpory.

- Model routing s LiteLLM a problematika latence a nákladů  
- Code-first orchestrační platforma pro byznys workflow (AI agenti s větší autonomií)

**Praktické cvičení:** 

- Vytvoříme workflow pro řešení stížnosti zákazníka

**Výstupy z lekce:** (Umím…)

- Využít AI na pozadí zpracování workflow, nejen v chatu

## **8\. lekce: Multi-agent systémy**

S rostoucí sofistikovaností AI agenta a rozšiřujícím se byznysem virtuálního tržiště vzniká potřeba vyvíjet některé části systému víc nezávisle a soustředit se na specializovaného agenta. Nový obchodní nápad má přivést na tržiště i kuchaře, kteří mohou nabízet služby pro různé oslavy a firemní akce a propojit tak dodavatele farmářských produktů, jejich zákazníků a služeb přípravy jídla. Na základě požadavku uživatele musí vzájemnou interakcí původního agenta (farmářské tržiště) a nového agenta (tržiště kuchařů a služeb) vzniknout dohoda který kuchař z jakých surovin co by zajistil a jaká je celková cena a tyto varianty nabídnout uživateli. 

- Framework pro vytvoření spolupracujících agentů a komunikace mezi nimi  
- Škálovatelné řešení \- každý agent jako samostatný deployment, ne monolit

**Praktické cvičení:** 

- K původnímu agentovi vytvoříme kuchařského agenta  
- Zajistíme, aby společně našli dohodu o cateringu na základě požadavků zákazníka

**Výstupy z lekce:** (Umím…)

- Použít framework pro vytváření vzájemně komunikujících agentů

## **9\. lekce: Bezpečnost a evaluace**

Jídlo a zdraví jsou citlivá témata a systém musí být bezpečný a důvěryhodný, jinak je tu reputační riziko. Kromě toho mohou být některá témata kontroverzní a pro některé uživatele nepříjemná (například náboženská omezení ve stravě, intolerance, vegetariánství apod.). Navíc přesnost odpovědí je důležitá, protože chyby v popisu či doporučení produktů mohou vést k nespokojenosti a ztrátě důvěry. Každá změna (verze) systému tak musí být testována a vyhodnocena stejně jako zpětná vazba uživatelů a to jak před nasazením, na základě reakce na hodnocení uživatele tak i průběžně v produkci přes A/B testování a evaluace.

- Red-teaming a testování bezpečnosti agentů (PyRIT)  
- Monitoring a automatizovaná evaluace kvality řešení, LLM-as-judge (LangFuse)

**Praktické cvičení:** 

- Přidáme bezpečnostní testování  
- Přidáme zpětovazební smyčku pro hodnocení kvality

**Výstupy z lekce:** (Umím…)

- Použít red-teaming pro testování bezpečnosti řešení  
- Sbírat a vyhodnocovat telemetrii i kvalitu odpovědí

## **10\. lekce: Observabilita a škálovatelné nasazení**

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

**POSUN PO LEKCÍCH:**

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
     ano \- na jednom monitoru/zařízení poslouchat a na druhém pracovat  
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


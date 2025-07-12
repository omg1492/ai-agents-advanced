# Scénář společného projektu

## Doména  
Virtuální **farmářské tržiště** propojující malé lokální farmáře se zákazníky.  
Uživatelé řeší:
- výběr čerstvých produktů, ověření původu a kvality
- sledování dodávek & sezónní dostupnosti
- řešení stížností / reklamací (poškozené zboží, neshoda kvality)
- analytické přehledy pro farmáře i provozovatele

> Proč ingestovat video?  
> Influenceři a farmáři natáčejí **video-recenze** (ukázky sklizně, degustace).  
> AI musí z těchto videí získat informace o kvalitě, chutích, tipy na přípravu atd., aby mohla lépe odpovídat dotazům zákazníků.

## Cíl  
Vybudovat **AI asistenta**, který:
1. odpovídá na dotazy z textů, obrázků i videí (RAG)  
2. umí vyhledat externí data (web, firemní API/MCP)  
3. pracuje multimodálně (obrázky, hlas)  
4. provádí výpočty / vizualizace (Code Interpreter)  
5. reaguje na událost **`complaint-raised`** a spustí vyšetřovací workflow  
6. funguje jako multi-agentní systém s pamětí  
7. je bezpečný, monitorovaný a škálovatelný

## Dvě větve projektu  
| Větev | Popis | Použití na hodině |
|-------|-------|------------------|
| **Plná verze** | Kompletní, předem připravená implementace. Více variant modelů, unit-testy, CI/CD. | Lektor demonstruje, sdílí best-practices a časté chyby. |
| **Kódování naživo** | Zjednodušená, inkrementální verze, psaná v lekci s GitHub Copilotem. | Studenti implementují, refaktorují a testují. |

## Inkrementy podle lekcí

### Lekce 01 – Business požadavky, architektura & základní chatbot nad dokumenty

#### Popis vylepšení a business přínos
V této lekci vytvoříme základního chatbota pro zákazníky, který bude schopen odpovídat na dotazy ohledně produktů. Popisky produktů máme od farmářů k dispozici v textové podobě a chatbot v nich bude vyhledávat sémanticky (základní RAG).

#### Technické aspekty plné verze
- Popisky produktů budou v jednom CSV souboru
- CSV se nahraje do PostgreSQL databáze a použije se pgvector a OpenAI embeddingy
- Vznikne jednoduchý backend v Pythonu, který odpovídá na dotazy a využívá RAG jako nástroj pro vyhledávání relevantních informací.
- Základní chatbot UI ve Streamlit
  
#### Technické kroky - kódování naživo
- Dostaneme hotovu a naplněnou databázi
- Vytvoříme jednoduchý backend bez RAG
- Vytvoříme jednoduché UI ve Streamlit, které se dotazuje na backend
- Přidáme RAG do aplikace

### Lekce 02 – Používání nástrojů: Web search, API, MCP

#### Popis vylepšení a business přínos
Chatbot umí získat aktuální ceny a dostupnost produktů z interního API systému, vytáhnout nutriční hodnoty produktů a na webu vyhledávat recepty a uživatelské recenze.

#### Technické aspekty plné verze
- API pro inventory, detaily produktů (nutriční hodnoty, alergeny)
- Napojení API jako nástroje do chatbota
- MCP server jako univerzální brána pro nástroje
- Web-search nástroj pro vyhledávání receptů a recenzí

#### Technické kroky – kódování naživo
- Dostanete hotové MCP servery na většinu nástrojů a ty napojíte do aplikace
- Pro jedno z API vytvoříte MCP server a napojíte ho do aplikace
- Přidáte web-search nástroj do aplikace

### Lekce 03 – Vytváření znalostní báze pro AI z dokumentů, obrázků a videí

#### Popis vylepšení a business přínos
Řada farmářů dodává popisy ve formě PDF dokumentů, nutričních tabulek nebo obrázků. Kromě toho existuje řada video recenzí, receptů na vaření a dalších tipů spojených s farmářskými produkty. Ty potřebujeme zpracovat a integrovat do znalostní báze, aby AI mohla lépe odpovídat na dotazy zákazníků. Nicméně, některé dokumenty nejsou určeny pro každého zákazníka, takže potřebujeme zajistit bezpečnost přístupu k nim. Navíc často chceme hledat ne podle významu, ale specificky podle třeba kódu produktu nebo farmy, takže potřebujeme i full-text vyhledávání. Pro často kladené otázky bychom mohli systém zrychlit pro uživatele a ještě ušetřit s využitím cachování.

#### Technické aspekty plné verze
- PDF a image konverze -> Markdown -> embeddings
- Přepis audia na text + občasné AI popisky snímku videa -> Markdown -> embeddings
- Hybrid search (full-text + vector)
- Implementace tagů a RAG fencing (filtr na alergeny)
- Semantic cache pro často kladené otázky

#### Technické kroky – kódování naživo
- Konverze pouze PDF a transkript audia -> Markdown -> embeddings
- Pouze sémantický search
- RAG fencing (filtr na alergeny)

### Lekce 04 – Deep Research & Knowledge Graph

#### Popis vylepšení a business přínos
AI doporučí ideální sezónní košík na základě vztahů mezi surovinami (alergeny, nutriční hodnoty, chuťové páry, sezónnost, typ kuchyně).

#### Technické aspekty plné verze
- TBD

#### Technické kroky – kódování naživo
- TBD

### Lekce 05 – Multimodalita, paměť & Real Voice Chat

#### Popis vylepšení a business přínos
Systém umožní hands-free plánovat nákup surovin na víkendovou oslavu. Paměť agenta se zaměřuje na preference uživatele a umožní personalizované rady.

#### Technické aspekty plné verze
- Real Voice Chat
- Extrakce intentu pro uložení do paměti nebo vybavení
- Sumarizace a perzistence předešlých konverzací
- Implicitní extrakce zájmů a preferencí uživatele

#### Technické kroky – kódování naživo
- Real Voice Chat
- Extrakce intentu pro uložení do paměti nebo vybavení

### Lekce 06 – Code Interpreter & Agentic UI

#### Popis vylepšení a business přínos
Systém dokáže analyzovat nutriční hodnoty nebo zdravotní dopady (vývoj glukózy či alkoholu v krvi) a vykreslovat grafy pro uživatele. Uživatel má možnost i uploadovat vlastní data se svými hodnotami (vývoj hmotnosti, ktervního tlaku, jídelníček atd.). Systém dále dokáže některé informace prezentovat vizualní interaktivní formou, například infografiku, časové osy, různé interaktivní texty (například karty faktů nebo produktů), kvízy, živé vizualizace dat apod.

#### Technické aspekty plné verze
- Code Interpreter sandbox, zpracování dat v Pythonu a vizualizace do grafů přes Python knihovny
- Generování interaktivní React karty a její zobrazení v UI přes sandbox web server

#### Technické kroky – kódování naživo
- TBD

### Lekce 07 – Orchestrace AI workflow

#### Popis vylepšení a business přínos
Proces autonomního řešení stížnosti uživatele, který poskytne popis problému a fotografie. AI workflow vyhodnotí problém v souvislosti s objednávkou, historií uživatele, směrnicemi a metodickými postupy a u jasných případů provede refundaci a informuje o ní uživatele i dodavatele. V případě složitějších případů se obrátí na lidského operátora, pro kterého připraví příslušné podklady a doporučení.

#### Technické aspekty plné verze
- TBD

#### Technické kroky – kódování naživo
- TBD

### Lekce 08 – Multi-agent systémy

#### Popis vylepšení a business přínos
S rostoucí sofistikovaností AI agenta a rozšiřujícím se byznysem virtuálního tržiště vzniká potřeba vyvíjet některé části systému víc nezávisle a soustředit se na specializovaného agenta. Nový obchodní nápad má přivést na tržiště i kuchaře, kteří mohou nabízet služby pro různé oslavy a firemní akce a propojit tak dodavatele farmářských produktů, jejich zákazníků a služeb přípravy jídla. Na základě požadavku uživatele musí vzájemnou interakcí původního agenta (farmářské tržiště) a nového agenta (tržiště kuchařů a služeb) vzniknout dohoda který kuchař z jakých surovin co by zajistil a jaká je celková cena a tyto varianty nabídnout uživateli. 

#### Technické aspekty plné verze
- TBD

#### Technické kroky – kódování naživo
- TBD

### Lekce 09 – Bezpečnost & Evaluace

#### Popis vylepšení a business přínos
Jídlo a zdraví jsou citlivá témata a systém musí být bezpečný a důvěryhodný, jinak je tu reputační riziko. Kromě toho mohou být některá témata kontroverzní a pro některé uživatele nepříjemná (například náboženská omezení ve stravě, intolerance, vegetariánství apod.). Navíc přesnost odpovědí je důležitá, protože chyby v popisu či doporučení produktů mohou vést k nespokojenosti a ztrátě důvěry. Každá změna (verze) systému tak musí být testována a vyhodnocena stejně jako zpětná vazba uživatelů a to jak před nasazením, na základě reakce na hodnocení uživatele tak i průběžně v produkci přes A/B testování a evaluace.

#### Technické aspekty plné verze
- TBD

#### Technické kroky – kódování naživo
- TBD

### Lekce 10 – Observabilita & Škálovatelné nasazení

#### Popis vylepšení a business přínos
Služba zvládne sezónní špičky, transparentní metriky pro provoz.

#### Technické aspekty plné verze
- TBD

#### Technické kroky – kódování naživo
- TBD

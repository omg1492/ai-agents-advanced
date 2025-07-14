# Pokročilý kurz AI aplikací – 10 večerních lekcí

Tento pokročilý kurz vás provede tvorbou **virtuálního farmářského tržiště** a naučí vás navrhovat, implementovat a nasazovat produkční AI služby. Projdeme kompletní workflow – od práce s dokumenty, deep research a multimodality, přes personalizační paměť a dynamicky generované UI, až po integraci do podnikových systémů, autonomní workflow, multi-agentní spolupráci, observabilitu, evaluaci, bezpečnost a škálovatelné nasazení. 

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
- Zpracovává podklady z dokumentů, obrázků i videí.
- Doporučuje personalizované košíky a recepty s ohledem na dietu či sezónnost.  
- Umožňuje hands-free hlasovou interakci a dlouhodobou uživatelskou paměť.  
- Vizualizuje a počítá nutriční data a nabízí alternativy.  
- Autonomně nebo polo-autonomně řeší stížnosti a další obchodní procesy.
- Sjednává catering mezi farmáři a kuchaři skrze multi-agentní systém. 

Jaké funkce přidáme do aplikace v jaké lekci je k přečteně v [agendě](agenda.md)

## Použité technologie  
- Python ( FastAPI / Streamlit ) + LangGraph pro RAG a agenty  
- OpenAI API, embeddings + PostgreSQL (pgvector)  
- MCP pro napojení interních API a web-search nástrojů  
- Temporal pro orchestraci workflow, LiteLLM pro model routing  
- Redis (pub/sub) pro komunikaci agentů a caching  
- Code Interpreter sandbox pro analýzu & vizualizace  
- Real Voice Chat (Speech-to-Text / Text-to-Speech)  
- OpenTelemetry + Langfuse pro observabilitu a evaluace  
- Kubernetes + GitHub Actions pro škálovatelné nasazení a CI/CD  
- PyRIT pro bezpečnostní testování (red teaming) a evaluaci odolnosti promptů  
- Infrastructure-as-Code (Terraform ) pro automatizované nasazení prostředí  

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
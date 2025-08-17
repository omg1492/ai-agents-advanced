# Lekce 01 – Business požadavky, architektura & základní chatbot nad dokumenty
Dream Farm je virtuální farmářské tržiště, které propojuje malé lokální farmáře se zákazníky.

Základní chatbot zpřístupní popisy produktů z farmy v přirozeném jazyce, takže zákazník ihned zjistí původ, kvalitu i dostupnost zboží. Rychlé a přesné odpovědi snižují zátěž podpory a zvyšují míru dokončených objednávek.  

**Koncepty:**
- RAG
- Embeddings
- Vektorová databáze  

**Technologie:**
- OpenAI API
- PostgreSQL (pgvector)
- Python (backend, FastAPI)
- React UI (assistant-ui)

Frontend je v Reactu v adresáři `frontend` a spustíte ho z něj pomocí příkazu `npm run dev`. V souboru `public/config.js` je BACKEND_URL parametr, který můžete nechat na výchozí hodnotě. Je připraven také `Dockerfile` pro zabalení do kontejneru, který pak můžete pouštět třeba s Docker Compose, ale to není předmětem dnešní lekce.

Backend je v adresáři `agents/dreamfarm-agent/src/`, spuští se příklazem `uv run main.py`.

Databázi PostgreSQL spustíte přes Docker Compose v adresáři `deploy/local` příkazem `docker-compose up -d`. Bude potřeba nainstalovat extensions a vytvořit schéma jednoduché tabulky, což najdete v `data/scripts/sql` buď ručně nebo použijte skript `data/scripts/configurepostgresql.py`.

Spusťte celé řešení - backend i frontend. Chatbot by měl fungovat a reagovat na otázky, ale pokud se zeptáte například `Who is producing vanilla-infused milk` nebude znát správnou odpověď.

Pokud budete dělat změny v kódu, využijte testů pro rychlé ověření funkčnosti - popis je v `agents/dreamfarm-agent/tests/README.md`.

## Příprava dat
Data jsou pro vás už vygenerovaná a uložená v `data/source_json/`. Pokud byste chtěli generovat vlastní data, použijte skript `data/scripts/gen_basic_data.py`, který vytvoří JSON soubory s produkty, producenty a dalšími informacemi.

Vytvořte skript, který pro producenty a jejich produkty vytvoří embeddings přes OpenAI API (nakonfigurujte správně soubor `.env` na základě přiložené šablony) a výsledek uloží jako Parquet soubor `data/processed/simple_products.parquet`. Můžete použít předpřipravený prompt z adresáře `.github/prompts/L01-EmbeddingsSimpleProduct.prompt.md` dohromady s GitHub Copilot nebo jiným asistentem nebo napsat skript ručně. Použijte datové schéma popsané v `data/scripts/sql/01_create_simple_products.sql`.

Naimportujte data do databáze.

## Test RAG
Použijte GitHub Copilot pro vytvoření skriptu nebo si nechte poradit SQL příkazy a použijte extension pro PostgreSQL nebo PSQL CLI a vypiště si prvních pár řádků z tabulky produktů.

Vytvořte testovací skript, který bude vyhledávat top 5 nejpodobnějších záznamů na dotaz `Who is producing vanilla-infused milk`. Skript by měl udělat embedding textu dotazu a použít pgvector syntaxi pro vyhledání podobnosti a následně sežadit výsledky podle míry podobnosti a vzít top 5 a ty vypsat na obrazovku.

Pokud skript funguje, zapněte RAG v připraveném kódu v .env souboru a vyzkoušejte

## Myšlenky navíc, pokud zbývá čas
- Přidejte do chatu informaci kolik dokumentů v rámci své odpovědi systém prozkoumal.
- Změňte prompt tak, aby chat pro jednotlivé části své odpovědi citoval odkud to má - nejprve zkuste jednoduše přidat ID produktu do závorky, pak zkuste přidat jen číslo citace a na konci odpovědi vypsat tabulku citací (například 1 - Butter, product ID xyz).
## Lekce 06 – Ad hoc kódování ### Jak předvést demo

#### Demo 1: Code Interpreter – analýza dat
1. **Příprava dat** – použijte soubor `weight_tracking.csv` (případně si vytvořte vlastní s datem a hodnotou váhy). Nahrajte ho tlačítkem „Upload file" v chatu.
2. **Dotaz na výpočet** – zeptejte se například:
	- „Jaký je průměr mojí váhy za toto období?"
	- „Ve který den byla moje váha nejnižší?"
	Model spustí Python, přečte CSV a odpoví textově.
3. **Dotaz na vizualizaci** – pokračujte otázkou:
	- „Vytvoř prosím čárový graf mojí váhy podle týdenních průměrů."
	Code interpreter vygeneruje graf (PNG). Backend ho uloží a frontend zobrazí přímo v konverzaci jako obrázek.

#### Demo 2: Visualization MCP – interaktivní HTML kartičky
1. **Uvítací kartička** – zeptejte se:
	- „Create a beautiful card displaying 'Welcome to DreamFarm' with a gradient background from blue to green"
	- „Vytvoř krásnou kartičku s textem 'Vítejte na DreamFarm' s barevným přechodem"
	Model zavolá MCP nástroj, vygeneruje HTML a zobrazí interaktivní kartičku s animacemi (hover shimmer efekt).
2. **Informační panel** – pokračujte:
	- „Create an infographic card showing 'Fresh Products: 127 items, Organic: 89%' with icons"
	- „Vytvoř infografiku ukazující statistiky našeho trhu s ikonami a moderním designem"
	MCP server vytvoří responzivní HTML panel s gradienty, ikonami a čistým typografickým stylem.
3. **Produktová prezentace** – zkuste:
	- „Design a product highlight card for 'Organic Honey' with price tag and benefits"
	Model vygeneruje produktovou kartičku, kterou lze použít pro marketing nebo prezentaci v e-shopu.zace (Azure OpenAI Code Interpreter + MCP)

Lekce navazuje na předchozí multimodální a paměťové schopnosti a přidává byznysovou hodnotu: AI dokáže analyzovat nutriční nebo zdravotní data zákazníka, okamžitě spočítá doporučení a vykreslí přehledné grafy, které zvyšují angažovanost i konverze (viz agenda kurzu). Pro DreamFarm marketplace to znamená, že můžeme zákazníkům ukázat trend jejich váhy, navrhnout zdravější alternativy a přímo doporučit produkty, které odpovídají jejich cíli.

Technicky jsme naučili DreamFarm agenta dvě formy ad-hoc generování:
1. **Code Interpreter** – spouští Python v Azure OpenAI sandboxu pro výpočty a analýzy nad nahranými daty (CSV, Excel, JSON…).
2. **Visualization MCP Server** – generuje krásné HTML infografiky a kartičky pomocí vzdáleného MCP nástroje (`generate_infographic`).

Model provede buď Python skript (code interpreter) nebo zavolá MCP nástroj (vizualizace), výsledek uloží do dočasného úložiště a my ho bezpečně zobrazíme v chatu.

### Jak to funguje

#### Code Interpreter (analýza dat)
- Frontend umožní nahrát soubory – posíláme je na Azure OpenAI Files API a dostaneme zpět `file_id`.
- Při dotazu modelu zapneme `code_interpreter` nástroj, předáme `file_ids` a Responses API spustí Python v sandboxu.
- Azure vrací metadata v `annotations` (obsahují `file_id`, `filename`, volitelně `container_id`). Backend je uloží v mapě a k souboru vygeneruje krátkodobý download token.
- Endpoint `/files/{file_id}/content` stáhne výsledek buď z kontejneru (`/containers/{container_id}/files/...`) nebo z fallbacku `/files/{file_id}/content`, takže funguje i když Azure kontejner nepošle.
- Frontend přemapuje `sandbox:/mnt/data/...` na absolutní URL s tokenem (`?token=...`) a pro známé přípony (PNG, JPG, WEBP…) vytvoří Markdown obrázek. Díky tomu se grafy vykreslí přímo v konverzaci, aniž by prohlížeč musel posílat Bearer token.

#### Visualization MCP Server (HTML infografiky)
- Model má k dispozici MCP nástroj `generate_infographic` (server běží na Azure Container Apps).
- Při požadavku na vizualizaci model zavolá tento nástroj s popisem požadované kartičky/infografiky.
- MCP server vygeneruje kompletní HTML s moderním CSS (gradienty, animace, responzivní design) a vrátí ho jako JSON s polem `html`.
- Backend detekuje MCP tool response, extrahuje HTML, vygeneruje UUID a uloží artifact do in-memory registru s 1hodinovou expirací.
- Backend pošle frontendovou událost `DF_META` s typem `visualization.artifact_created` a `artifact_id`.
- Do odpovědi modelu vloží odkaz ve formátu `[View Visualization](/artifacts/{uuid})`.
- Frontend markdown renderer detekuje pattern `/artifacts/`, vyrenderuje `VisualizationArtifact` komponentu se sandboxovaným iframe.
- Iframe načte HTML z veřejného endpointu `/artifacts/{uuid}` (bez autentizace, chráněno UUID + TTL).
- Vizualizace se zobrazí inline v konverzaci jako interaktivní HTML element (hover efekty, animace apod.).

### Jak předvést demo
1. **Příprava dat** – použijte soubor `weight_tracking.csv` (případně si vytvořte vlastní s datem a hodnotou váhy). Nahrajte ho tlačítkem „Upload file“ v chatu.
2. **Dotaz na výpočet** – zeptejte se například:
	- „Jaký je průměr mojí váhy za toto období?“
	- „Ve který den byla moje váha nejnižší?“
	Model spustí Python, přečte CSV a odpoví textově.
3. **Dotaz na vizualizaci** – pokračujte otázkou:
	- „Vytvoř prosím čárový graf mojí váhy podle týdenních průměrů.“
	Code interpreter vygeneruje graf (PNG). Backend ho uloží a frontend zobrazí přímo v konverzaci jako obrázek.

### Shrnutí
- **Code Interpreter**: Uživatelská data putují jen přes Azure OpenAI (sandbox) a náš backend – nikdy se neukládají trvale. Obrázky a další výsledky jsou dostupné přes zabezpečený proxy endpoint s krátkodobým tokenem.
- **Visualization MCP**: MCP server generuje čisté HTML bez závislostí na externích knihovnách. Artifacts jsou chráněné UUID (hard-to-guess) + 1hodinovou expirací. Frontend zobrazuje HTML v sandboxovaném iframe (`sandbox="allow-same-origin"`) bez povolení skriptů z důvodu bezpečnosti.
- Díky live přemapování URL je možné zobrazovat výsledky okamžitě během streamování odpovědi.
- Oba přístupy kombinují sílu AI s vizuální prezentací – code interpreter pro datovou analýzu, MCP pro designové elementy.

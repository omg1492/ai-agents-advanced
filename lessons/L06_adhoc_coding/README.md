## Lekce 06 – Ad hoc kódování (Azure OpenAI Code Interpreter)

Lekce navazuje na předchozí multimodální a paměťové schopnosti a přidává byznysovou hodnotu: AI dokáže analyzovat nutriční nebo zdravotní data zákazníka, okamžitě spočítá doporučení a vykreslí přehledné grafy, které zvyšují angažovanost i konverze (viz agenda kurzu). Pro DreamFarm marketplace to znamená, že můžeme zákazníkům ukázat trend jejich váhy, navrhnout zdravější alternativy a přímo doporučit produkty, které odpovídají jejich cíli.

Technicky jsme naučili DreamFarm agenta spouštět kód přímo v Azure OpenAI Responses API pomocí vestavěného nástroje `code_interpreter`. Uživatel nahraje data (CSV, Excel, JSON…) a během chatu požádá asistenta o výpočty, agregace nebo vizualizace. Model provede Python skript uvnitř sandboxu, výsledek (tabulku, text, graf) uloží do dočasného úložiště a my ho bezpečně zobrazíme v chatu.

### Jak to funguje
- Frontend umožní nahrát soubory – posíláme je na Azure OpenAI Files API a dostaneme zpět `file_id`.
- Při dotazu modelu zapneme `code_interpreter` nástroj, předáme `file_ids` a Responses API spustí Python v sandboxu.
- Azure vrací metadata v `annotations` (obsahují `file_id`, `filename`, volitelně `container_id`). Backend je uloží v mapě a k souboru vygeneruje krátkodobý download token.
- Endpoint `/files/{file_id}/content` stáhne výsledek buď z kontejneru (`/containers/{container_id}/files/...`) nebo z fallbacku `/files/{file_id}/content`, takže funguje i když Azure kontejner nepošle.
- Frontend přemapuje `sandbox:/mnt/data/...` na absolutní URL s tokenem (`?token=...`) a pro známé přípony (PNG, JPG, WEBP…) vytvoří Markdown obrázek. Díky tomu se grafy vykreslí přímo v konverzaci, aniž by prohlížeč musel posílat Bearer token.

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
- Uživatelská data putují jen přes Azure OpenAI (sandbox) a náš backend – nikdy se neukládají trvale.
- Obrázky a další výsledky jsou dostupné přes zabezpečený proxy endpoint s krátkodobým tokenem.
- Díky live přemapování URL je možné zobrazovat výsledky okamžitě během streamování odpovědi.

# Lekce 00 - Příprava
Následující témata jsou technické koncepty, které byste měli znát před zahájením lekcí, stejně jako požadavky na vaše nastavení a přístup ke službám.

## Přístup ke službám
- **Ujistěte se, že máte přístup k `OpenAI` nebo `Azure OpenAI`** API klíčům s dostatečným kreditem (budu používat Azure OpenAI, pro který můžete získat zkušební Azure předplatné zdarma, ale přímé použití OpenAI je také v pořádku, ačkoli není plně otestováno v mém kódu)
- Doporučení je jít s [Azure Trial](https://azure.microsoft.com/en-us/pricing/purchase-options/azure-account) nebo s vaším firemním Azure. Alternativně použijte [OpenAI Platform](https://platform.openai.com/settings/organization/billing/overview) a přidejte nějaký kredit (absolutní většina našeho ukázkového kódu používá nejnovější OpenAI SDK, které funguje stejně mezi Azure a OpenAI variantami pomocí **Responses API**, takže by to mělo fungovat dobře)
- Budete potřebovat AI kódovacího asistenta, budu používat (a doporučuji) **GitHub Copilot** - potřebujete alespoň Pro verzi (nebo Pro+, Business nebo Enterprise), kterou si můžete koupit za 10 USD nebo získat zkušební verzi [zde](https://github.com/features/copilot/plans)

## Koncepty, které je doporučeno znát před zahájením tohoto kurzu
- Naučte se `uv` - Python prostředí a správce balíčků
- Měli byste znát základy `Docker` (vytváření Dockerfile, sestavování images, spouštění kontejnerů) a `Docker Compose` (syntaxe YAML souboru, docker compose up, down, logs atd.)
- Seznamte se s Python koncepty a knihovnami jako `classes`, `Pydantic`, `FastAPI`, `SQLAlchemy`, `pytest` a `Jinja2`
- Základní pochopení, jak spouštět `React` aplikace, používat `npm`, mít ho nainstalovaný na vašem stroji
- Naučte se základy `PostgreSQL` (vytváření databází, tabulek, spouštění dotazů), znalost `pgvector` je plus
- Seznamte se s `GitHub Copilot` (to je to, co budu používat, ale pokud jste uživatel Cursor nebo Windsurf, je to také v pořádku)
- Základy `git` a `GitHub` (klonování repozitářů, vytváření větví, commitování změn, pushování do remote)
  
## Požadavky na váš stroj
Pro lokální stroj se ujistěte, že máte všechna požadovaná oprávnění (věci jako kontejnery, networking, schopnost instalovat software, ...) a nainstalujte následující nástroje:
- Visual Studio Code a přihlaste se pomocí GitHub Copilot
- Mějte `Python` a `npm` nainstalované na vašem stroji
- Nainstalujte `Rancher Desktop` v režimu kompatibility s Docker a otestujte ho - nebo alternativně použijte jakýkoli jiný lokální Linux Docker kompatibilní systém

Alternativně můžete použít **GitHub Codespaces** pro získání cloudového vývojového prostředí.
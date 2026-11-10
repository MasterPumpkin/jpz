# Analýza přijímacích řízení na střední školy (2024–2026)

Interaktivní analytický dashboard vytvořený v Pythonu (Streamlit), který vizualizuje oficiální data z přijímacího řízení a jednotných přijímacích zkoušek (JPZ - Cermat) na střední školy v České republice. Nástroj slouží uchazečům, rodičům i školám k lepšímu pochopení trhu, strategickému plánování priorit přihlášek a analýze výsledků.

**Odkaz na live aplikaci:** [https://jpz-analysis.streamlit.app/](https://jpz-analysis.streamlit.app/)

## Klíčové funkce

Aplikace nabízí ucelený analytický systém ve čtyřech sekcích:

### 1. Celkový přehled trhu
- **Strategická matice (Šance vs. Konkurence)**: Scatter plot srovnávající převis poptávky a úspěšnost přijetí, velikost bublin odpovídá kapacitě a hover obsahuje bodové hranice a percentily.
- **Kompletní analýza priorit**: Přepínač mezi strukturou *Přihlášených* a reálně *Přijatých* žáků podle 1., 2. a 3. priority.
- **Důvody nepřijetí**: Rozpad zamítnutí (nedostačující kapacita, nesplnění podmínek, odliv na prioritnější školu) v absolutních i relativních (%) hodnotách.
- **Chytré kaskádové filtry**: Výběr kraje automaticky omezí nabízená města, kategorie i konkrétní obory.
- **Export do CSV**: Možnost okamžitého stažení vyfiltrované tabulky jedním kliknutím.

### 2. Detail školy
- Podrobný profil konkrétní střední školy.
- **Benchmarking vůči regionu**: Převis i úspěšnost školy porovnaná s průměrem konkurence ve stejném kraji a oborech.
- **Bodové hranice a percentily**: Minimální a průměrný percentil přijatých uchazečů z testů Cermat.
- **Meziroční vývoj oborů**: Indikátory trendu přihlášek (`↑` / `↓` / `Nový obor`).
- **Fulltext vyhledávání**: Rychlé vyhledání školy podle názvu bez nutnosti procházet dlouhé seznamy.

### 3. ⚖️ Srovnávač škol (Head-to-Head)
- Přímé porovnání **2 až 3 škol vedle sebe**.
- Souběžné karty metrik (kapacita, převis, úspěšnost, průměrný percentil, min. body).
- Srovnávací sloupcové grafy priorit uchazečů a důvodů nepřijetí (odliv vs. kapacitní přetlak).
- Přehledná porovnávací tabulka všech oborů vybraných škol.

### 4. 🎯 Kalkulačka šancí & Strategický rádce
- **Prediktor šancí podle bodů**:
  - Přepočet bodů z ČJL (0–50) a MAT (0–50) na národní percentil z testů Cermat.
  - Okamžité vyhodnocení šancí na všech školách:
    - 🟢 *Vysoká šance (Bezpečné)*
    - 🟡 *Reálná šance (Na hraně)*
    - 🔴 *Rizikové (Nízká šance)*
- **Strategický rádce pro 3 přihlášky**:
  - Vyhodnocení kombinace 3 zvolených škol (1. Sen, 2. Realita, 3. Jistota).
  - Kontrola logiky priorit – varování před tzv. *mrtvou přihláškou* (kdy je 3. priorita náročnější než 1. priorita).
  - Kontrola přítomnosti bezpečné záchranné sítě.

## Architektura a optimalizace

- **Bleskový SQLite backend (`cermat.db`)**: S WAL žurnálem, optimalizovanou paměťovou cache a B-tree indexy (dotazy do 10 ms).
- **Žádná závislost na velkých CSV za běhu**: Všechna historická i procesní data jsou konsolidována v databázi. Původní soubor je bezpečně archivován v `archive/data.csv`.
- **Modulární architektura**:
  - `src/jpz/db.py`: Databázové dotazy, cachování a vyhodnocovací funkce.
  - `src/jpz/views/market.py`: Přehled trhu a trendy.
  - `src/jpz/views/school_detail.py`: Detail školy.
  - `src/jpz/views/compare.py`: Srovnávač škol.
  - `src/jpz/views/calculator.py`: Kalkulačka šancí a strategický rádce.
  - `app.py`: Hlavní Streamlit aplikace.

## Spuštění aplikace

Pomocí `uv` (přímo přes definovaný CLI skript):
```bash
uv run jpz
```
Nebo klasicky přes streamlit:
```bash
uv run streamlit run app.py
```
*(nebo přes virtuální prostředí: `.venv/bin/streamlit run app.py`)*

---
*Vytvořeno pro lepší orientaci a úspěch v přijímacím řízení na střední školy.*

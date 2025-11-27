# Analýza přijímacích řízení na střední školy (2024–2025)

Interaktivní analytický dashboard vytvořený v Pythonu (Streamlit), který vizualizuje data z přijímacího řízení na střední školy v České republice. Nástroj slouží uchazečům, rodičům i školám k lepšímu pochopení trhu, identifikaci "bezpečných" škol a analýze meziročních trendů.

## Klíčové funkce

Aplikace nabízí komplexní pohled na data v několika sekcích:

### 1. Celkový přehled trhu
- **Strategická matice (Šance vs. Konkurence)**: Scatter plot zobrazující školy podle převisu poptávky a úspěšnosti přijetí. Pomáhá identifikovat "Jistoty" (vysoká šance, malá konkurence) a "Masakry" (velký převis).
- **Analýza priorit**: Graf ukazující, kolik uchazečů mělo danou školu jako 1., 2. nebo 3. prioritu. Odhaluje, zda je škola "vysněnou volbou" nebo "záchrannou sítí".
- **Důvody nepřijetí**: Rozbor důvodů zamítnutí (nedostačující kapacita, nesplnění podmínek, přijetí na prioritní školu).
- **Oborová analýza**: Žebříček oborů s největším převisem poptávky.

### 2. Meziroční srovnání trendů (2024 vs 2025)
- **Skokani roku**: Obory s největším absolutním nárůstem zájmu.
- **Pokles zájmu**: Obory, kde zájem opadl.
- **Změna priorit**: Dumbbell chart vizualizující posun v tom, jak moc je obor pro uchazeče první volbou.

### 3. Detail školy
- Podrobný profil vybrané školy.
- **Benchmarking**: Srovnání úspěšnosti a převisu školy vůči průměru trhu (regionu/oboru).
- **Meziroční změny po oborech**: Detailní tabulka s indikátory růstu/poklesu přihlášek.

## Použité technologie

- **[Streamlit](https://streamlit.io/)**: Frontend a interaktivní rozhraní.
- **[Pandas](https://pandas.pydata.org/)**: Zpracování a čištění dat (ETL).
- **[Plotly](https://plotly.com/python/)**: Interaktivní vizualizace a grafy.

## Jak spustit aplikaci lokálně

1. **Naklonujte repozitář:**
   ```bash
   git clone https://github.com/vase-uzivatelske-jmeno/nazev-repozitare.git
   cd nazev-repozitare
   ```

2. **Vytvořte virtuální prostředí (doporučeno):**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Nainstalujte závislosti:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Spusťte aplikaci:**
   ```bash
   streamlit run app.py
   ```

## Struktura dat

Aplikace očekává soubor `data.csv` v kořenovém adresáři. Tento soubor by měl obsahovat exportovaná data z Cermatu/MŠMT s následujícími sloupci (nebo ekvivalenty, které aplikace přemapuje):
- `Škola`, `Obor`, `Město`, `Kraj`, `Rok`
- Metriky: `Kapacita`, `Počet přihlášek`, `Počet přijatých`, `Priority 1-3`, `Důvody nepřijetí`

---
*Vytvořeno pro lepší orientaci v džungli přijímaček.* 🎓

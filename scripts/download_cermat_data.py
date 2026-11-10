#!/usr/bin/env python3
"""
Automatický stahovač a aktualizátor dat přímo z oficiálního portálu Cermat
(https://data.cermat.gov.cz).

Stahuje kompletní oficiální XLSX soubory s výsledky (kolo 1 i kolo 2)
pro roky 2024, 2025 a 2026 a aktualizuje SQLite databázi cermat.db.
"""

import os
import sys
import argparse
import urllib.request
import sqlite3
from pathlib import Path
import pandas as pd

BASE_URL = "https://data.cermat.gov.cz/files/files/JPZ/agregovana_data_skoly"
DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "downloads"
DB_PATH = Path(__file__).resolve().parent.parent / "cermat.db"

def download_file(url: str, dest_path: Path):
    """Stáhne soubor z URL a uloží jej do dest_path, pokud již neexistuje."""
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        print(f"  [CACHE] Používám již stažený soubor: {dest_path.name}")
        return dest_path

    print(f"  [DOWNLOAD] Stahuji: {url}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out:
        out.write(resp.read())
    print(f"  [OK] Uloženo ({dest_path.stat().st_size // 1024} KB): {dest_path.name}")
    return dest_path

def process_year(year: int):
    """Stáhne a zpracuje výsledky pro daný rok za kolo 1 i kolo 2."""
    print(f"\n================ ZPRACOVÁVÁM ROK {year} ================")
    f1_name = f"PZ{year}_kolo1_skolobory_vysledky.xlsx"
    f2_name = f"PZ{year}_kolo2_skolobory_vysledky.xlsx"

    url1 = f"{BASE_URL}/{f1_name}"
    url2 = f"{BASE_URL}/{f2_name}"

    p1 = DOWNLOAD_DIR / f1_name
    p2 = DOWNLOAD_DIR / f2_name

    download_file(url1, p1)
    
    has_kolo2 = True
    try:
        download_file(url2, p2)
    except Exception as e:
        print(f"  [INFO] Kolo 2 pro rok {year} není k dispozici nebo selhalo stažení: {e}")
        has_kolo2 = False

    print("  Načítám Excel soubor pro 1. kolo...")
    df1 = pd.read_excel(p1)
    df1['KOLO'] = 1

    if has_kolo2 and p2.exists():
        print("  Načítám Excel soubor pro 2. kolo...")
        try:
            df2 = pd.read_excel(p2)
            df2['KOLO'] = 2
            df_all = pd.concat([df1, df2], ignore_index=True)
        except Exception as e:
            print(f"  Varování při čtení 2. kola: {e}")
            df_all = df1
    else:
        df_all = df1

    # Normalizace REDIZO
    df_all = df_all.dropna(subset=['REDIZO', 'KKOV']).copy()
    df_all['REDIZO'] = df_all['REDIZO'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df_all['ROK'] = year

    return df_all

def to_int(val, default=0):
    if pd.isna(val):
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

def update_database(all_dfs):
    """Aktualizuje tabulky skoly, obory, prihlasky_rocni a skoly_historie v cermat.db."""
    print("\n================ AKTUALIZACE DATABÁZE ================")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    df_combined = pd.concat(all_dfs, ignore_index=True)

    # 1. Číselník škol
    print("Aktualizuji číselník škol (skoly)...")
    cur.execute("PRAGMA table_info(skoly)")
    existing_cols = [c[1] for c in cur.fetchall()]
    if "ulice" not in existing_cols:
        cur.execute("ALTER TABLE skoly ADD COLUMN ulice TEXT;")
    if "display_name" not in existing_cols:
        cur.execute("ALTER TABLE skoly ADD COLUMN display_name TEXT;")

    schools_grouped = df_combined.groupby('REDIZO').first().reset_index()

    # Zjistit duplicitní kombinace (nazev_skoly, mesto)
    dup_counts = df_combined.groupby(['NÁZEV ŠKOLY', 'OBEC'])['REDIZO'].nunique()
    dup_pairs = set(dup_counts[dup_counts > 1].index)

    for _, row in schools_grouped.iterrows():
        redizo = str(row['REDIZO'])
        skola = str(row.get('NÁZEV ŠKOLY', '')).strip()
        kraj = str(row.get('KRAJ - NÁZEV', row.get('KRAJ', ''))).strip()
        mesto = str(row.get('OBEC', '')).strip()
        okres = str(row.get('OKRES - NÁZEV', row.get('OKRES', ''))).strip()
        zriz = str(row.get('ZŘIZOVATEL - NÁZEV', row.get('ZŘIZOVATEL', ''))).strip()
        ulice = str(row.get('ULICE', '')).strip() if pd.notna(row.get('ULICE')) else ''

        if (skola, mesto) in dup_pairs:
            if ulice:
                disp = f"{skola}, {mesto} ({ulice})"
            else:
                disp = f"{skola}, {mesto} [{redizo}]"
        else:
            if mesto:
                disp = f"{skola}, {mesto}"
            else:
                disp = skola

        cur.execute("""
            INSERT INTO skoly (redizo, nazev_skoly, kraj, mesto, zrizovatel, okres, ulice, display_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(redizo) DO UPDATE SET
                nazev_skoly = COALESCE(excluded.nazev_skoly, skoly.nazev_skoly),
                kraj = COALESCE(excluded.kraj, skoly.kraj),
                mesto = COALESCE(excluded.mesto, skoly.mesto),
                zrizovatel = COALESCE(excluded.zrizovatel, skoly.zrizovatel),
                okres = COALESCE(excluded.okres, skoly.okres),
                ulice = COALESCE(excluded.ulice, skoly.ulice),
                display_name = COALESCE(excluded.display_name, skoly.display_name)
        """, (redizo, skola, kraj, mesto, zriz, okres, ulice, disp))

    cur.execute("CREATE INDEX IF NOT EXISTS idx_skoly_display_name ON skoly(display_name);")

    # 2. Číselník oborů
    print("Aktualizuji číselník oborů (obory)...")
    obory_grouped = df_combined.groupby('KKOV').first().reset_index()
    for _, row in obory_grouped.iterrows():
        kkov = str(row['KKOV']).strip()
        nazev_oboru = str(row.get('OBOR - NÁZEV', '')).strip()
        typ = str(row.get('TYP ŠKOLY - NÁZEV', 'Ostatní')).strip()

        # Mapování typu na čistou kategorii
        kat = "Ostatní"
        if "Gymnázi" in typ:
            if "8" in typ:
                kat = "Gymnázium (8leté)"
            elif "6" in typ:
                kat = "Gymnázium (6leté)"
            else:
                kat = "Gymnázium (4leté)"
        elif "Lyce" in typ:
            kat = "Lyceum"
        elif "SOŠ" in typ:
            kat = "SOŠ"
        elif "SOU" in typ:
            kat = "SOU"
        elif "Konzervat" in typ:
            kat = "Konzervatoř"

        cur.execute("""
            INSERT INTO obory (kod_oboru, nazev_oboru, kategorie_oboru)
            VALUES (?, ?, ?)
            ON CONFLICT(kod_oboru) DO UPDATE SET
                nazev_oboru = COALESCE(excluded.nazev_oboru, obory.nazev_oboru),
                kategorie_oboru = COALESCE(excluded.kategorie_oboru, obory.kategorie_oboru)
        """, (kkov, nazev_oboru, kat))

    # 3. Roční agregace (prihlasky_rocni)
    print("Počítám roční agregace (prihlasky_rocni)...")
    cur.execute("DELETE FROM prihlasky_rocni")

    for year in df_combined['ROK'].unique():
        year_int = int(year)
        df_y = df_combined[df_combined['ROK'] == year]
        
        # Kapacita pouze z 1. kola
        df_cap = df_y[df_y['KOLO'] == 1].groupby(['REDIZO', 'KKOV'])['KAPACITA'].sum().reset_index()

        # Sumy přihlášek a přijetí přes obě kola
        metrics_sum = df_y.groupby(['REDIZO', 'KKOV']).agg({
            'PŘIHLÁŠKY CELKEM': 'sum',
            'PŘIJATÍ': 'sum',
            'PŘIHLÁŠKY - PRIORITA 1': 'sum',
            'PŘIHLÁŠKY - PRIORITA 2': 'sum',
            'PŘIHLÁŠKY - PRIORITA 3': 'sum',
            'PŘIJATÍ - PRIORITA 1': 'sum',
            'PŘIJATÍ - PRIORITA 2': 'sum',
            'PŘIJATÍ - PRIORITA 3': 'sum',
            'NEPŘIJATI - NEDOSTATEČNÁ KAPACITA': 'sum',
            'NEPŘIJATI - NESPLNĚNÍ PODMÍNEK': 'sum',
            'NEPŘIJATI - PŘIJAT NA VYŠŠÍ PRIORITU': 'sum',
            'ZŘIZOVATEL - NÁZEV': 'first',
            'OKRES - NÁZEV': 'first'
        }).reset_index()

        df_merged = pd.merge(df_cap, metrics_sum, on=['REDIZO', 'KKOV'], how='outer').fillna(0)

        for _, r in df_merged.iterrows():
            redizo = str(r['REDIZO'])
            kkov = str(r['KKOV'])
            cap = to_int(r.get('KAPACITA'))
            prihl = to_int(r.get('PŘIHLÁŠKY CELKEM'))
            prij = to_int(r.get('PŘIJATÍ'))
            p1 = to_int(r.get('PŘIHLÁŠKY - PRIORITA 1'))
            p2 = to_int(r.get('PŘIHLÁŠKY - PRIORITA 2'))
            p3 = to_int(r.get('PŘIHLÁŠKY - PRIORITA 3'))
            pr1 = to_int(r.get('PŘIJATÍ - PRIORITA 1'))
            pr2 = to_int(r.get('PŘIJATÍ - PRIORITA 2'))
            pr3 = to_int(r.get('PŘIJATÍ - PRIORITA 3'))
            d_kap = to_int(r.get('NEPŘIJATI - NEDOSTATEČNÁ KAPACITA'))
            d_podm = to_int(r.get('NEPŘIJATI - NESPLNĚNÍ PODMÍNEK'))
            d_vyss = to_int(r.get('NEPŘIJATI - PŘIJAT NA VYŠŠÍ PRIORITU'))
            zriz = str(r.get('ZŘIZOVATEL - NÁZEV', ''))
            okres = str(r.get('OKRES - NÁZEV', ''))

            cur.execute("""
                INSERT INTO prihlasky_rocni (
                    redizo, kod_oboru, rok, kapacita, prihlaseni, prijati,
                    prihlaseni_p1, prihlaseni_p2, prihlaseni_p3,
                    prijati_p1, prijati_p2, prijati_p3,
                    duvod_kapacita, duvod_podminky, duvod_vyssi_priorita,
                    zrizovatel, okres
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(redizo, kod_oboru, rok) DO UPDATE SET
                    kapacita = excluded.kapacita,
                    prihlaseni = excluded.prihlaseni,
                    prijati = excluded.prijati,
                    prihlaseni_p1 = excluded.prihlaseni_p1,
                    prihlaseni_p2 = excluded.prihlaseni_p2,
                    prihlaseni_p3 = excluded.prihlaseni_p3,
                    prijati_p1 = excluded.prijati_p1,
                    prijati_p2 = excluded.prijati_p2,
                    prijati_p3 = excluded.prijati_p3,
                    duvod_kapacita = excluded.duvod_kapacita,
                    duvod_podminky = excluded.duvod_podminky,
                    duvod_vyssi_priorita = excluded.duvod_vyssi_priorita,
                    zrizovatel = excluded.zrizovatel,
                    okres = excluded.okres
            """, (redizo, kkov, year_int, cap, prihl, prij, p1, p2, p3, pr1, pr2, pr3, d_kap, d_podm, d_vyss, zriz, okres))

        # 4. Aktualizace skoly_historie (percentily přijatých)
        print(f"Aktualizuji skoly_historie pro rok {year_int}...")
        df_hist = df_y[df_y['KOLO'] == 1].groupby(['REDIZO', 'KKOV']).agg({
            'KAPACITA': 'first',
            'PŘIHLÁŠKY - PRIORITA 1': 'first',
            'ČJ+MA - PERCENTIL - MIN (PŘIJATI)': 'first',
            'ČJ+MA - PERCENTIL - PRŮMĚR (PŘIJATI)': 'first',
            'ČJ+MA - % SKÓR - MIN (PŘIJATI)': 'first'
        }).reset_index()

        for _, hr in df_hist.iterrows():
            redizo = str(hr['REDIZO'])
            kkov = str(hr['KKOV'])
            cap = to_int(hr.get('KAPACITA'))
            p1 = to_int(hr.get('PŘIHLÁŠKY - PRIORITA 1'))
            previs = round(p1 / cap, 2) if cap > 0 else 0.0

            min_pct = hr.get('ČJ+MA - PERCENTIL - MIN (PŘIJATI)')
            avg_pct = hr.get('ČJ+MA - PERCENTIL - PRŮMĚR (PŘIJATI)')
            min_score = hr.get('ČJ+MA - % SKÓR - MIN (PŘIJATI)')

            min_pct_val = float(min_pct) if pd.notna(min_pct) else 0.0
            avg_pct_val = float(avg_pct) if pd.notna(avg_pct) else 0.0
            min_body_val = float(min_score) if pd.notna(min_score) else 0.0

            cur.execute("""
                INSERT INTO skoly_historie (
                    redizo, kod_oboru, rok, kapacita, prihlasky_p1, index_pretlaku,
                    min_body, min_percentil, avg_percentil
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(redizo, kod_oboru, rok) DO UPDATE SET
                    kapacita = excluded.kapacita,
                    prihlasky_p1 = excluded.prihlasky_p1,
                    index_pretlaku = excluded.index_pretlaku,
                    min_body = CASE WHEN excluded.min_body > 0 THEN excluded.min_body ELSE skoly_historie.min_body END,
                    min_percentil = CASE WHEN excluded.min_percentil > 0 THEN excluded.min_percentil ELSE skoly_historie.min_percentil END,
                    avg_percentil = CASE WHEN excluded.avg_percentil > 0 THEN excluded.avg_percentil ELSE skoly_historie.avg_percentil END
            """, (redizo, kkov, year_int, cap, p1, previs, min_body_val, min_pct_val, avg_pct_val))

    conn.commit()
    conn.close()
    print("Databáze úspěšně aktualizována všemi oficiálními daty!")

def main():
    parser = argparse.ArgumentParser(description="Stáhne a importuje data z Cermatu do cermat.db")
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2026], help="Roky ke stažení (např. 2024 2025 2026)")
    args = parser.parse_args()

    all_dfs = []
    for y in args.years:
        df = process_year(y)
        all_dfs.append(df)

    update_database(all_dfs)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Migrační skript pro import dat z data.csv do cermat.db
a vytvoření optimalizovaných tabulek a indexů pro Streamlit dashboard.
"""

import sqlite3
import csv
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "cermat.db"
CSV_PATH = Path(__file__).resolve().parent.parent / "archive" / "data.csv"
if not CSV_PATH.exists():
    CSV_PATH = Path(__file__).resolve().parent.parent / "data.csv"

def run_migration():
    if not DB_PATH.exists():
        print(f"Chyba: Databáze {DB_PATH} nebyla nalezena.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print(f"Otevírám databázi: {DB_PATH}")

    # 1. Rozšíření tabulky skoly o zrizovatel a okres, pokud chybí
    cols = [c[1] for c in cur.execute("PRAGMA table_info(skoly)").fetchall()]
    if "zrizovatel" not in cols:
        cur.execute("ALTER TABLE skoly ADD COLUMN zrizovatel TEXT")
    if "okres" not in cols:
        cur.execute("ALTER TABLE skoly ADD COLUMN okres TEXT")

    # 2. Načtení dat z CSV (pokud existuje)
    if CSV_PATH.exists():
        print(f"Importuji data z: {CSV_PATH}")
        schools_info = {}
        raw_details = []

        with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                redizo_val = row.get("Součet hodnot: REDIZO")
                if not redizo_val:
                    continue
                redizo = str(int(float(redizo_val)))
                skola = row["Škola"]
                kraj = row["Kraj"]
                mesto = row["Město"]
                okres = row["Okres"]
                zrizovatel = row["Zřizovatel"]
                kkov = row["KKOV"]
                rok = int(row["Rok"])
                kolo = int(row["Kolo"])
                zamereni = row.get("Zaměření", "")

                def to_int(k):
                    val = row.get(k, 0)
                    return int(float(val)) if val else 0

                cap = to_int("Součet hodnot: Kapacita")
                prihlaseni = to_int("Součet hodnot: Přihlášeni")
                prijati = to_int("Součet hodnot: Přijati")
                prihlaseni_p1 = to_int("Součet hodnot: Přihlášeni - priorita 1")
                prihlaseni_p2 = to_int("Součet hodnot: Přihlášeni - priorita 2")
                prihlaseni_p3 = to_int("Součet hodnot: Přihlášeni - priorita 3")
                prijati_p1 = to_int("Součet hodnot: Přijati - priorita 1")
                prijati_p2 = to_int("Součet hodnot: Přijati - priorita 2")
                prijati_p3 = to_int("Součet hodnot: Přijati - priorita 3")
                duvod_kap = to_int("Součet hodnot: Nepřijati - nedostačující kapacita")
                duvod_podm = to_int("Součet hodnot: Nepřijati - nesplnění podmínek")
                duvod_vyssi = to_int("Součet hodnot: Nepřijati - přijati na vyšší prioritu")

                if redizo not in schools_info:
                    schools_info[redizo] = (skola, kraj, mesto, zrizovatel, okres)

                raw_details.append((
                    redizo, kkov, rok, kolo, zamereni, cap, prihlaseni, prijati,
                    prihlaseni_p1, prihlaseni_p2, prihlaseni_p3,
                    prijati_p1, prijati_p2, prijati_p3,
                    duvod_kap, duvod_podm, duvod_vyssi,
                    zrizovatel, okres
                ))

        # Doplnění škol do tabulky skoly
        for redizo, (skola, kraj, mesto, zrizovatel, okres) in schools_info.items():
            cur.execute("""
                INSERT INTO skoly (redizo, nazev_skoly, kraj, mesto, zrizovatel, okres)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(redizo) DO UPDATE SET
                    zrizovatel = COALESCE(excluded.zrizovatel, skoly.zrizovatel),
                    okres = COALESCE(excluded.okres, skoly.okres)
            """, (redizo, skola, kraj, mesto, zrizovatel, okres))

        # Vytvoření detailní tabulky
        cur.execute("DROP TABLE IF EXISTS prihlasky_detail")
        cur.execute("""
        CREATE TABLE prihlasky_detail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            redizo TEXT NOT NULL,
            kod_oboru TEXT NOT NULL,
            rok INTEGER NOT NULL,
            kolo INTEGER NOT NULL,
            zamereni TEXT,
            kapacita INTEGER NOT NULL DEFAULT 0,
            prihlaseni INTEGER NOT NULL DEFAULT 0,
            prijati INTEGER NOT NULL DEFAULT 0,
            prihlaseni_p1 INTEGER NOT NULL DEFAULT 0,
            prihlaseni_p2 INTEGER NOT NULL DEFAULT 0,
            prihlaseni_p3 INTEGER NOT NULL DEFAULT 0,
            prijati_p1 INTEGER NOT NULL DEFAULT 0,
            prijati_p2 INTEGER NOT NULL DEFAULT 0,
            prijati_p3 INTEGER NOT NULL DEFAULT 0,
            duvod_kapacita INTEGER NOT NULL DEFAULT 0,
            duvod_podminky INTEGER NOT NULL DEFAULT 0,
            duvod_vyssi_priorita INTEGER NOT NULL DEFAULT 0,
            zrizovatel TEXT,
            okres TEXT
        )
        """)

        cur.executemany("""
        INSERT INTO prihlasky_detail (
            redizo, kod_oboru, rok, kolo, zamereni, kapacita, prihlaseni, prijati,
            prihlaseni_p1, prihlaseni_p2, prihlaseni_p3,
            prijati_p1, prijati_p2, prijati_p3,
            duvod_kapacita, duvod_podminky, duvod_vyssi_priorita,
            zrizovatel, okres
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, raw_details)

        # Vytvoření agregované tabulky prihlasky_rocni
        cur.execute("DROP TABLE IF EXISTS prihlasky_rocni")
        cur.execute("""
        CREATE TABLE prihlasky_rocni (
            redizo TEXT NOT NULL,
            kod_oboru TEXT NOT NULL,
            rok INTEGER NOT NULL,
            kapacita INTEGER NOT NULL DEFAULT 0,
            prihlaseni INTEGER NOT NULL DEFAULT 0,
            prijati INTEGER NOT NULL DEFAULT 0,
            prihlaseni_p1 INTEGER NOT NULL DEFAULT 0,
            prihlaseni_p2 INTEGER NOT NULL DEFAULT 0,
            prihlaseni_p3 INTEGER NOT NULL DEFAULT 0,
            prijati_p1 INTEGER NOT NULL DEFAULT 0,
            prijati_p2 INTEGER NOT NULL DEFAULT 0,
            prijati_p3 INTEGER NOT NULL DEFAULT 0,
            duvod_kapacita INTEGER NOT NULL DEFAULT 0,
            duvod_podminky INTEGER NOT NULL DEFAULT 0,
            duvod_vyssi_priorita INTEGER NOT NULL DEFAULT 0,
            zrizovatel TEXT,
            okres TEXT,
            PRIMARY KEY (redizo, kod_oboru, rok)
        )
        """)

        cur.execute("""
        INSERT INTO prihlasky_rocni (
            redizo, kod_oboru, rok, kapacita, prihlaseni, prijati,
            prihlaseni_p1, prihlaseni_p2, prihlaseni_p3,
            prijati_p1, prijati_p2, prijati_p3,
            duvod_kapacita, duvod_podminky, duvod_vyssi_priorita,
            zrizovatel, okres
        )
        SELECT 
            m.redizo,
            m.kod_oboru,
            m.rok,
            COALESCE(c.kapacita, 0) as kapacita,
            m.prihlaseni,
            m.prijati,
            m.prihlaseni_p1,
            m.prihlaseni_p2,
            m.prihlaseni_p3,
            m.prijati_p1,
            m.prijati_p2,
            m.prijati_p3,
            m.duvod_kapacita,
            m.duvod_podminky,
            m.duvod_vyssi_priorita,
            m.zrizovatel,
            m.okres
        FROM (
            SELECT 
                redizo, kod_oboru, rok,
                SUM(prihlaseni) as prihlaseni,
                SUM(prijati) as prijati,
                SUM(prihlaseni_p1) as prihlaseni_p1,
                SUM(prihlaseni_p2) as prihlaseni_p2,
                SUM(prihlaseni_p3) as prihlaseni_p3,
                SUM(prijati_p1) as prijati_p1,
                SUM(prijati_p2) as prijati_p2,
                SUM(prijati_p3) as prijati_p3,
                SUM(duvod_kapacita) as duvod_kapacita,
                SUM(duvod_podminky) as duvod_podminky,
                SUM(duvod_vyssi_priorita) as duvod_vyssi_priorita,
                MAX(zrizovatel) as zrizovatel,
                MAX(okres) as okres
            FROM prihlasky_detail
            GROUP BY redizo, kod_oboru, rok
        ) m
        LEFT JOIN (
            SELECT redizo, kod_oboru, rok, SUM(kapacita) as kapacita
            FROM prihlasky_detail
            WHERE kolo = 1
            GROUP BY redizo, kod_oboru, rok
        ) c ON m.redizo = c.redizo AND m.kod_oboru = c.kod_oboru AND m.rok = c.rok
        """)

    # 3. Doplnění záznamů pro rok 2026 ze skoly_historie
    cur.execute("""
    INSERT OR IGNORE INTO prihlasky_rocni (
        redizo, kod_oboru, rok, kapacita, prihlaseni, prijati,
        prihlaseni_p1, prihlaseni_p2, prihlaseni_p3,
        prijati_p1, prijati_p2, prijati_p3,
        duvod_kapacita, duvod_podminky, duvod_vyssi_priorita,
        zrizovatel, okres
    )
    SELECT 
        h.redizo,
        h.kod_oboru,
        h.rok,
        h.kapacita,
        h.prihlasky_p1 as prihlaseni,
        h.kapacita as prijati,
        h.prihlasky_p1 as prihlaseni_p1,
        0, 0,
        h.prihlasky_p1 as prijati_p1,
        0, 0,
        0, 0, 0,
        s.zrizovatel,
        s.okres
    FROM skoly_historie h
    LEFT JOIN skoly s ON h.redizo = s.redizo
    WHERE h.rok = 2026
    """)

    # 4. Vytvoření rychlých indexů
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skoly_kraj ON skoly(kraj)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skoly_mesto ON skoly(mesto)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skoly_zrizovatel ON skoly(zrizovatel)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_obory_kategorie ON obory(kategorie_oboru)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skoly_hist_lookup ON skoly_historie(redizo, kod_oboru, rok)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_prihlasky_rocni_rok ON prihlasky_rocni(rok)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_prihlasky_rocni_lookup ON prihlasky_rocni(redizo, kod_oboru, rok)")

    conn.commit()
    conn.close()
    print("Migrace úspěšně dokončena!")

if __name__ == "__main__":
    run_migration()


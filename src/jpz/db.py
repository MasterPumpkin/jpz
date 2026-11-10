"""
Modul pro práci s SQLite databází cermat.db.
Zajišťuje rychlé SQL dotazy, cachování přes Streamlit, podporu kalkulačky šancí
a kaskádové filtrování.
"""

import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent.parent / "cermat.db"

def get_connection():
    """Vrací optimalizované připojení do SQLite databáze s WAL režimem."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -64000;")  # 64 MB cache
    return conn

@st.cache_data(ttl=3600)
def get_filter_options():
    """Vrací základní možnosti pro filtry v aplikaci."""
    conn = get_connection()
    try:
        years = [r[0] for r in conn.execute("SELECT DISTINCT rok FROM prihlasky_rocni ORDER BY rok DESC").fetchall()]
        kraje = [r[0] for r in conn.execute("SELECT DISTINCT kraj FROM skoly WHERE kraj IS NOT NULL AND kraj != '' ORDER BY kraj").fetchall()]
        return {
            "years": years,
            "kraje": kraje
        }
    finally:
        conn.close()

@st.cache_data(ttl=1800)
def get_cascading_filter_options(kraje=None, mesta=None, kategorie=None):
    """
    Chytré kaskádové filtry: vrací města, kategorie oborů a konkrétní obory
    pouze pro aktuálně zvolený region a nadřazené filtry.
    """
    conn = get_connection()
    try:
        # 1. Města pro vybrané kraje
        query_mesta = "SELECT DISTINCT s.mesto FROM skoly s WHERE s.mesto IS NOT NULL AND s.mesto != ''"
        params_m = []
        if kraje:
            query_mesta += f" AND s.kraj IN ({','.join('?' for _ in kraje)})"
            params_m.extend(kraje)
        query_mesta += " ORDER BY s.mesto"
        available_cities = [r[0] for r in conn.execute(query_mesta, params_m).fetchall()]

        # 2. Kategorie a obory pro vybrané kraje a města
        query_obory = """
        SELECT DISTINCT o.kategorie_oboru, o.nazev_oboru
        FROM prihlasky_rocni p
        JOIN skoly s ON p.redizo = s.redizo
        JOIN obory o ON p.kod_oboru = o.kod_oboru
        WHERE 1=1
        """
        params_o = []
        if kraje:
            query_obory += f" AND s.kraj IN ({','.join('?' for _ in kraje)})"
            params_o.extend(kraje)
        if mesta:
            query_obory += f" AND s.mesto IN ({','.join('?' for _ in mesta)})"
            params_o.extend(mesta)
        if kategorie:
            query_obory += f" AND o.kategorie_oboru IN ({','.join('?' for _ in kategorie)})"
            params_o.extend(kategorie)

        rows = conn.execute(query_obory, params_o).fetchall()
        available_kategorie = sorted(list(set(r[0] for r in rows if r[0])))
        available_obory = sorted(list(set(r[1] for r in rows if r[1])))

        return {
            "mesta": available_cities,
            "kategorie": available_kategorie,
            "obory": available_obory
        }
    finally:
        conn.close()

@st.cache_data(ttl=1800)
def load_market_data(rok, kraje=None, mesta=None, kategorie=None, obory=None):
    """
    Rychle načte agregovaná data pro vybraný rok a aplikované filtry přímo z SQLite.
    Zahrnuje kompletní priority (P1, P2, P3 pro přihlášené i přijaté) a důvody odmítnutí.
    """
    conn = get_connection()
    try:
        query = """
        SELECT 
            p.redizo,
            s.nazev_skoly AS Škola,
            s.kraj AS Kraj,
            s.mesto AS Město,
            s.okres AS Okres,
            COALESCE(s.zrizovatel, 'veřejné / státní') AS Zřizovatel,
            p.kod_oboru AS KKOV,
            o.nazev_oboru AS Obor,
            COALESCE(o.kategorie_oboru, 'Ostatní') AS Kategorie_Oboru,
            (s.nazev_skoly || ', ' || s.mesto || ' (' || o.nazev_oboru || ')') AS Skola_Obor,
            p.rok AS Rok,
            p.kapacita AS Kapacita,
            p.prihlaseni AS Prihlaseni,
            p.prijati AS Prijati,
            p.prihlaseni_p1 AS Prihlaseni_P1,
            p.prihlaseni_p2 AS Prihlaseni_P2,
            p.prihlaseni_p3 AS Prihlaseni_P3,
            p.prijati_p1 AS Prijati_P1,
            p.prijati_p2 AS Prijati_P2,
            p.prijati_p3 AS Prijati_P3,
            p.duvod_kapacita AS Duvod_Kapacita,
            p.duvod_podminky AS Duvod_Podminky,
            p.duvod_vyssi_priorita AS Duvod_Vyssi_Priorita,
            h.min_body AS Min_Body,
            h.min_percentil AS Min_Percentil,
            h.avg_percentil AS Avg_Percentil,
            ROUND(p.prihlaseni * 1.0 / NULLIF(p.kapacita, 0), 2) AS Previs_Poptavky,
            ROUND(p.prijati * 100.0 / NULLIF(p.prihlaseni, 0), 1) AS Uspesnost_Pct,
            ROUND(p.prijati_p1 * 100.0 / NULLIF(p.prihlaseni_p1, 0), 1) AS Uspesnost_P1_Pct,
            ROUND(p.duvod_vyssi_priorita * 100.0 / NULLIF(p.prihlaseni, 0), 1) AS Index_Odlivu
        FROM prihlasky_rocni p
        JOIN skoly s ON p.redizo = s.redizo
        JOIN obory o ON p.kod_oboru = o.kod_oboru
        LEFT JOIN skoly_historie h ON p.redizo = h.redizo AND p.kod_oboru = h.kod_oboru AND p.rok = h.rok
        WHERE p.rok = ? AND p.kapacita > 0
        """
        params = [rok]

        if kraje:
            placeholders = ",".join("?" for _ in kraje)
            query += f" AND s.kraj IN ({placeholders})"
            params.extend(kraje)
        if mesta:
            placeholders = ",".join("?" for _ in mesta)
            query += f" AND s.mesto IN ({placeholders})"
            params.extend(mesta)
        if kategorie:
            placeholders = ",".join("?" for _ in kategorie)
            query += f" AND o.kategorie_oboru IN ({placeholders})"
            params.extend(kategorie)
        if obory:
            placeholders = ",".join("?" for _ in obory)
            query += f" AND o.nazev_oboru IN ({placeholders})"
            params.extend(obory)

        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        conn.close()

@st.cache_data(ttl=1800)
def load_all_schools_list(rok=None, kraje=None, mesta=None):
    """Vrací seznam unikátních názvů škol pro výběr detailu a srovnávač."""
    conn = get_connection()
    try:
        query = "SELECT DISTINCT s.nazev_skoly FROM prihlasky_rocni p JOIN skoly s ON p.redizo = s.redizo WHERE 1=1"
        params = []
        if rok:
            query += " AND p.rok = ?"
            params.append(rok)
        if kraje:
            query += f" AND s.kraj IN ({','.join('?' for _ in kraje)})"
            params.extend(kraje)
        if mesta:
            query += f" AND s.mesto IN ({','.join('?' for _ in mesta)})"
            params.extend(mesta)
        query += " ORDER BY s.nazev_skoly"
        return [r[0] for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()

@st.cache_data(ttl=1800)
def load_school_detail_data(nazev_skoly, rok):
    """
    Načte detailní data pro vybranou školu a daný rok,
    včetně benchmarku trhu a dat z předchozího roku pro trendy.
    """
    conn = get_connection()
    try:
        query_current = """
        SELECT 
            p.redizo,
            s.nazev_skoly AS Škola,
            s.kraj AS Kraj,
            s.mesto AS Město,
            s.okres AS Okres,
            s.zrizovatel AS Zřizovatel,
            p.kod_oboru AS KKOV,
            o.nazev_oboru AS Obor,
            o.kategorie_oboru AS Kategorie_Oboru,
            (s.nazev_skoly || ', ' || s.mesto || ' (' || o.nazev_oboru || ')') AS Skola_Obor,
            p.rok AS Rok,
            p.kapacita AS Kapacita,
            p.prihlaseni AS Prihlaseni,
            p.prijati AS Prijati,
            p.prihlaseni_p1 AS Prihlaseni_P1,
            p.prihlaseni_p2 AS Prihlaseni_P2,
            p.prihlaseni_p3 AS Prihlaseni_P3,
            p.prijati_p1 AS Prijati_P1,
            p.prijati_p2 AS Prijati_P2,
            p.prijati_p3 AS Prijati_P3,
            p.duvod_kapacita AS Duvod_Kapacita,
            p.duvod_podminky AS Duvod_Podminky,
            p.duvod_vyssi_priorita AS Duvod_Vyssi_Priorita,
            h.min_body AS Min_Body,
            h.min_percentil AS Min_Percentil,
            h.avg_percentil AS Avg_Percentil,
            ROUND(p.prihlaseni * 1.0 / NULLIF(p.kapacita, 0), 2) AS Previs_Poptavky,
            ROUND(p.prijati * 100.0 / NULLIF(p.prihlaseni, 0), 1) AS Uspesnost_Pct
        FROM prihlasky_rocni p
        JOIN skoly s ON p.redizo = s.redizo
        JOIN obory o ON p.kod_oboru = o.kod_oboru
        LEFT JOIN skoly_historie h ON p.redizo = h.redizo AND p.kod_oboru = h.kod_oboru AND p.rok = h.rok
        WHERE s.nazev_skoly = ? AND p.rok = ?
        ORDER BY p.prihlaseni DESC
        """
        df_school = pd.read_sql_query(query_current, conn, params=[nazev_skoly, rok])
        if df_school.empty:
            return df_school, None, None

        kraj = df_school["Kraj"].iloc[0]
        kkov_list = df_school["KKOV"].unique().tolist()

        # Benchmark konkurence ve stejném kraji a oborech
        query_bm = f"""
        SELECT 
            SUM(p.kapacita) as bm_kapacita,
            SUM(p.prihlaseni) as bm_prihlaseni,
            SUM(p.prijati) as bm_prijati
        FROM prihlasky_rocni p
        JOIN skoly s ON p.redizo = s.redizo
        WHERE p.rok = ? AND s.kraj = ? AND s.nazev_skoly != ?
          AND p.kod_oboru IN ({','.join('?' for _ in kkov_list)})
        """
        bm_res = conn.execute(query_bm, [rok, kraj, nazev_skoly] + kkov_list).fetchone()
        benchmark = {
            "kapacita": bm_res["bm_kapacita"] or 0,
            "prihlaseni": bm_res["bm_prihlaseni"] or 0,
            "prijati": bm_res["bm_prijati"] or 0,
            "avg_previs": round((bm_res["bm_prihlaseni"] or 0) / (bm_res["bm_kapacita"] or 1), 2),
            "avg_uspesnost": round((bm_res["bm_prijati"] or 0) * 100.0 / (bm_res["bm_prihlaseni"] or 1), 1)
        }

        # Data z předchozího roku pro trendy
        prev_year = rok - 1
        query_prev = """
        SELECT 
            p.kod_oboru AS KKOV,
            p.prihlaseni AS Prihlaseni_Prev,
            h.min_body AS Min_Body_Prev,
            h.min_percentil AS Min_Percentil_Prev
        FROM prihlasky_rocni p
        JOIN skoly s ON p.redizo = s.redizo
        LEFT JOIN skoly_historie h ON p.redizo = h.redizo AND p.kod_oboru = h.kod_oboru AND p.rok = h.rok
        WHERE s.nazev_skoly = ? AND p.rok = ?
        """
        df_prev = pd.read_sql_query(query_prev, conn, params=[nazev_skoly, prev_year])

        if not df_prev.empty:
            df_school = pd.merge(df_school, df_prev, on="KKOV", how="left")
            df_school["Zmena_Abs"] = (df_school["Prihlaseni"] - df_school["Prihlaseni_Prev"]).fillna(0)
            df_school["Zmena_Pct"] = ((df_school["Prihlaseni"] - df_school["Prihlaseni_Prev"]) / df_school["Prihlaseni_Prev"].replace(0, pd.NA) * 100).fillna(0)
        else:
            df_school["Prihlaseni_Prev"] = None
            df_school["Zmena_Abs"] = None
            df_school["Zmena_Pct"] = None

        return df_school, benchmark, prev_year
    finally:
        conn.close()

@st.cache_data(ttl=1800)
def load_comparison_data(school_names, rok):
    """Načte data pro srovnání vybraných škol vedle sebe."""
    if not school_names:
        return pd.DataFrame()
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in school_names)
        query = f"""
        SELECT 
            s.nazev_skoly AS Škola,
            s.mesto AS Město,
            s.kraj AS Kraj,
            s.zrizovatel AS Zřizovatel,
            o.nazev_oboru AS Obor,
            o.kategorie_oboru AS Kategorie,
            p.kapacita AS Kapacita,
            p.prihlaseni AS Prihlaseni,
            p.prijati AS Prijati,
            p.prihlaseni_p1 AS Prihlaseni_P1,
            p.prihlaseni_p2 AS Prihlaseni_P2,
            p.prihlaseni_p3 AS Prihlaseni_P3,
            p.prijati_p1 AS Prijati_P1,
            p.prijati_p2 AS Prijati_P2,
            p.prijati_p3 AS Prijati_P3,
            p.duvod_kapacita AS Duvod_Kapacita,
            p.duvod_podminky AS Duvod_Podminky,
            p.duvod_vyssi_priorita AS Duvod_Vyssi_Priorita,
            h.min_body AS Min_Body,
            h.min_percentil AS Min_Percentil,
            h.avg_percentil AS Avg_Percentil,
            ROUND(p.prihlaseni * 1.0 / NULLIF(p.kapacita, 0), 2) AS Previs_Poptavky,
            ROUND(p.prijati * 100.0 / NULLIF(p.prihlaseni, 0), 1) AS Uspesnost_Pct
        FROM prihlasky_rocni p
        JOIN skoly s ON p.redizo = s.redizo
        JOIN obory o ON p.kod_oboru = o.kod_oboru
        LEFT JOIN skoly_historie h ON p.redizo = h.redizo AND p.kod_oboru = h.kod_oboru AND p.rok = h.rok
        WHERE s.nazev_skoly IN ({placeholders}) AND p.rok = ?
        ORDER BY s.nazev_skoly, p.prihlaseni DESC
        """
        params = list(school_names) + [rok]
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

@st.cache_data(ttl=1800)
def load_yoy_data(kraje=None, mesta=None, kategorie=None, obory=None):
    """Načte data pro meziroční srovnání přes všechny roky."""
    conn = get_connection()
    try:
        query = """
        SELECT 
            o.nazev_oboru AS Obor,
            p.rok AS Rok,
            SUM(p.prihlaseni) AS Prihlaseni,
            SUM(p.prihlaseni_p1) AS Prihlaseni_P1
        FROM prihlasky_rocni p
        JOIN skoly s ON p.redizo = s.redizo
        JOIN obory o ON p.kod_oboru = o.kod_oboru
        WHERE 1=1
        """
        params = []
        if kraje:
            query += f" AND s.kraj IN ({','.join('?' for _ in kraje)})"
            params.extend(kraje)
        if mesta:
            query += f" AND s.mesto IN ({','.join('?' for _ in mesta)})"
            params.extend(mesta)
        if kategorie:
            query += f" AND o.kategorie_oboru IN ({','.join('?' for _ in kategorie)})"
            params.extend(kategorie)
        if obory:
            query += f" AND o.nazev_oboru IN ({','.join('?' for _ in obory)})"
            params.extend(obory)

        query += " GROUP BY o.nazev_oboru, p.rok"
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

@st.cache_data(ttl=3600)
def calculate_chances(rok, body_cjl, body_mat, kraj=None, kategorie=None, query_search=None):
    """
    Vypočte šanci uchazeče na základě zadaných bodů z ČJL a MAT
    pomocí distribučních tabulek percentilů v percentily_historie a skoly_historie.
    """
    conn = get_connection()
    try:
        r_cjl = conn.execute("SELECT percentil FROM percentily_historie WHERE rok = ? AND predmet = 'cjl' AND body = ?", (rok, body_cjl)).fetchone()
        r_mat = conn.execute("SELECT percentil FROM percentily_historie WHERE rok = ? AND predmet = 'mat' AND body = ?", (rok, body_mat)).fetchone()

        pct_cjl = r_cjl["percentil"] if r_cjl else 0.0
        pct_mat = r_mat["percentil"] if r_mat else 0.0
        avg_pct = round((pct_cjl + pct_mat) / 2.0, 1)
        total_points = body_cjl + body_mat

        query = """
        SELECT 
            s.nazev_skoly AS Škola,
            s.mesto AS Město,
            s.kraj AS Kraj,
            s.okres AS Okres,
            COALESCE(s.zrizovatel, 'veřejné / státní') AS Zřizovatel,
            o.nazev_oboru AS Obor,
            COALESCE(o.kategorie_oboru, 'Ostatní') AS Kategorie,
            h.kapacita AS Kapacita,
            h.prihlasky_p1 AS Prihlaseni_P1,
            h.index_pretlaku AS Převis_P1,
            h.min_body AS Min_Body,
            h.min_percentil AS Min_Percentil,
            h.avg_percentil AS Avg_Percentil,
            CASE 
                WHEN ? >= h.avg_percentil THEN '🟢 Vysoká šance (Bezpečné)'
                WHEN ? >= h.min_percentil THEN '🟡 Reálná šance (Na hraně)'
                ELSE '🔴 Rizikové (Nízká šance)'
            END AS Sance
        FROM skoly_historie h
        JOIN skoly s ON h.redizo = s.redizo
        JOIN obory o ON h.kod_oboru = o.kod_oboru
        WHERE h.rok = ? AND h.min_percentil > 0
        """
        params = [avg_pct, avg_pct, rok]

        if kraj:
            query += " AND s.kraj = ?"
            params.append(kraj)
        if kategorie:
            query += " AND o.kategorie_oboru = ?"
            params.append(kategorie)
        if query_search:
            query += " AND (s.nazev_skoly LIKE ? OR o.nazev_oboru LIKE ? OR s.mesto LIKE ?)"
            wildcard = f"%{query_search}%"
            params.extend([wildcard, wildcard, wildcard])

        query += " ORDER BY h.avg_percentil DESC"
        df_results = pd.read_sql_query(query, conn, params=params)

        return {
            "pct_cjl": pct_cjl,
            "pct_mat": pct_mat,
            "avg_pct": avg_pct,
            "total_points": total_points,
            "results": df_results
        }
    finally:
        conn.close()

@st.cache_data(ttl=3600)
def evaluate_three_priorities(rok, choice1, choice2, choice3, avg_percentil):
    """
    Analyzuje strategii 3 zadaných přihlášek (Škola + Obor).
    Kontroluje, zda posloupnost priorit dává smysl a dává doporučení.
    """
    conn = get_connection()
    try:
        choices = [choice1, choice2, choice3]
        results = []
        for idx, ch in enumerate(choices, 1):
            if not ch:
                continue
            # ch is (nazev_skoly, nazev_oboru)
            skola, obor = ch
            query = """
            SELECT 
                s.nazev_skoly,
                o.nazev_oboru,
                o.kategorie_oboru,
                h.min_percentil,
                h.avg_percentil,
                h.min_body,
                h.index_pretlaku
            FROM skoly_historie h
            JOIN skoly s ON h.redizo = s.redizo
            JOIN obory o ON h.kod_oboru = o.kod_oboru
            WHERE s.nazev_skoly = ? AND o.nazev_oboru = ? AND h.rok = ?
            """
            r = conn.execute(query, (skola, obor, rok)).fetchone()
            if r:
                results.append({
                    "priorita": idx,
                    "skola": r["nazev_skoly"],
                    "obor": r["nazev_oboru"],
                    "kategorie": r["kategorie_oboru"],
                    "min_pct": r["min_percentil"],
                    "avg_pct": r["avg_percentil"],
                    "min_body": r["min_body"],
                    "previs": r["index_pretlaku"],
                    "stav": (
                        "🟢 Bezpečná" if avg_percentil >= r["avg_percentil"]
                        else "🟡 Reálná" if avg_percentil >= r["min_percentil"]
                        else "🔴 Náročná / Sen"
                    )
                })
        return results
    finally:
        conn.close()

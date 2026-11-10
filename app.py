"""
Analýza přijímacích řízení na střední školy (2024–2026).
Hlavní Streamlit aplikace napojená přímo na SQLite databázi cermat.db.
"""

import sys
from pathlib import Path
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.jpz.db import get_filter_options, get_cascading_filter_options, load_market_data
from src.jpz.views.market import render_market_view
from src.jpz.views.school_detail import render_school_detail_view
from src.jpz.views.compare import render_compare_view
from src.jpz.views.calculator import render_calculator_view

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(
    page_title="Analýza přijímacích řízení na SŠ",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Analýza přijímacích řízení na střední školy (2024–2026)")
st.markdown("""
Tento dashboard analyzuje oficiální data z přijímacího řízení a jednotných přijímacích zkoušek (Cermat):
* **Bleskově rychlý SQLite backend**: Žádné zdlouhavé načítání velkých CSV souborů za běhu.
* **Kompletní data**: Všechny priority (1., 2., 3. přihláška) i důvody nepřijetí (nedostatek kapacity, nesplnění podmínek, odliv).
* **Kategorie oborů**: Čisté rozlišení (Gymnázia 4/6/8letá, Lycea, SOŠ, SOU).
* **Výsledky JPZ**: Bodové hranice a percentily přijatých žáků z testů Cermat.
""")

# --- NAČTENÍ ZÁKLADNÍCH MOŽNOSTÍ FILTRŮ ---
base_filter_opts = get_filter_options()

# --- SIDEBAR: NAVIGACE ---
st.sidebar.header("Navigace")
page = st.sidebar.radio(
    "Přejít na sekci:",
    [
        "Celkový přehled trhu",
        "Detail školy",
        "⚖️ Srovnávač škol",
        "🎯 Kalkulačka & Strategie"
    ]
)

st.sidebar.divider()

# --- SIDEBAR: GLOBÁLNÍ FILTRY (pro přehled trhu a detail školy) ---
if page in ["Celkový přehled trhu", "Detail školy"]:
    st.sidebar.header("Filtry")

    # Výchozí je nejnovější rok (2026)
    selected_year = st.sidebar.selectbox(
        "Vyberte rok",
        base_filter_opts["years"],
        index=0
    )

    selected_kraj = st.sidebar.multiselect("Vyberte kraj", base_filter_opts["kraje"])

    # Chytré kaskádové načítání měst a kategorií podle vybraných krajů
    cascading_opts_step1 = get_cascading_filter_options(kraje=selected_kraj if selected_kraj else None)
    selected_mesto = st.sidebar.multiselect("Vyberte město", cascading_opts_step1["mesta"])

    selected_kategorie = st.sidebar.multiselect("Vyberte kategorii školy", cascading_opts_step1["kategorie"])

    # Chytré kaskádové načítání oborů a škol podle kraje, města a kategorie
    cascading_opts_step2 = get_cascading_filter_options(
        kraje=selected_kraj if selected_kraj else None,
        mesta=selected_mesto if selected_mesto else None,
        kategorie=selected_kategorie if selected_kategorie else None
    )
    selected_obor = st.sidebar.multiselect("Vyberte konkrétní obor", cascading_opts_step2["obory"])
    selected_skola = st.sidebar.multiselect(
        "Vyberte školu (název a město)",
        cascading_opts_step2.get("skoly", []),
        placeholder="Všechny školy nebo vyberte..."
    )

    # Načtení dat trhu pro aktuální výběr
    df_market = load_market_data(
        rok=selected_year,
        kraje=selected_kraj if selected_kraj else None,
        mesta=selected_mesto if selected_mesto else None,
        kategorie=selected_kategorie if selected_kategorie else None,
        obory=selected_obor if selected_obor else None,
        skoly=selected_skola if selected_skola else None
    )
else:
    selected_year = 2025
    selected_kraj = None
    selected_mesto = None
    selected_kategorie = None
    selected_obor = None
    selected_skola = None
    df_market = None

# --- ZOBRAZENÍ JEDNOTLIVÝCH POHLEDŮ ---
if page == "Celkový přehled trhu":
    render_market_view(
        df_final=df_market,
        selected_year=selected_year,
        selected_kraj=selected_kraj,
        selected_mesto=selected_mesto,
        selected_kategorie=selected_kategorie,
        selected_obor=selected_obor,
        selected_skola=selected_skola
    )

    with st.expander("🔍 Zobrazit surová data aktuálního výběru"):
        st.dataframe(df_market, hide_index=True)

elif page == "Detail školy":
    render_school_detail_view(
        selected_year=selected_year,
        selected_kraj=selected_kraj,
        selected_mesto=selected_mesto
    )

elif page == "⚖️ Srovnávač škol":
    render_compare_view()

elif page == "🎯 Kalkulačka & Strategie":
    render_calculator_view()

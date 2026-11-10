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
st.caption("Oficiální agregovaná data Cermat z jednotných přijímacích zkoušek (JPZ) • Optimalizovaný SQLite backend")

with st.expander("ℹ️ O aplikaci, metodice a datech Cermat", expanded=False):
    st.markdown("""
    Tento interaktivní dashboard analyzuje oficiální výsledky přijímacích řízení a JPZ:
    * **Kompletní priority (1., 2. a 3. přihláška)**: Sledování skutečných preferencí uchazečů i reálné úspěšnosti.
    * **Důvody nepřijetí**: Rozpad na nedostatek kapacity, nesplnění podmínek a odliv na preferovanější školu.
    * **Kategorie oborů**: Čisté rozlišení (Gymnázia 4/6/8letá, Lycea, SOŠ, SOU a další).
    * **Výsledkové percentily**: Bodové hranice a percentily přijatých žáků z testů z českého jazyka a matematiky.
    * **Jednoznačná identifikace**: Školy jsou rozlišeny názvem, městem a sídelní adresou.
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

# Reset filtrů logika
def reset_filters():
    for k in ["market_kraj", "market_mesto", "market_kat", "market_obor", "market_skola", "detail_kraj", "detail_mesto"]:
        if k in st.session_state:
            st.session_state[k] = []

# --- SIDEBAR: GLOBÁLNÍ FILTRY ---
if page == "Celkový přehled trhu":
    st.sidebar.header("Filtry trhu")

    selected_year = st.sidebar.selectbox(
        "Vyberte rok",
        base_filter_opts["years"],
        index=0,
        key="market_year"
    )

    selected_kraj = st.sidebar.multiselect("Vyberte kraj", base_filter_opts["kraje"], key="market_kraj")

    # Kaskádové načítání měst a kategorií
    cascading_opts_step1 = get_cascading_filter_options(kraje=selected_kraj if selected_kraj else None)
    selected_mesto = st.sidebar.multiselect("Vyberte město", cascading_opts_step1["mesta"], key="market_mesto")
    selected_kategorie = st.sidebar.multiselect("Vyberte kategorii školy", cascading_opts_step1["kategorie"], key="market_kat")

    # Kaskádové načítání oborů a škol
    cascading_opts_step2 = get_cascading_filter_options(
        kraje=selected_kraj if selected_kraj else None,
        mesta=selected_mesto if selected_mesto else None,
        kategorie=selected_kategorie if selected_kategorie else None
    )
    selected_obor = st.sidebar.multiselect("Vyberte konkrétní obor", cascading_opts_step2["obory"], key="market_obor")
    selected_skola = st.sidebar.multiselect(
        "Vyberte školu (název a město)",
        cascading_opts_step2.get("skoly", []),
        placeholder="Všechny školy nebo vyberte...",
        key="market_skola"
    )

    # Tlačítko resetovat filtry, pokud je nějaký aktivní
    has_active_filter = any([selected_kraj, selected_mesto, selected_kategorie, selected_obor, selected_skola])
    if has_active_filter:
        st.sidebar.button("🔄 Resetovat filtry", on_click=reset_filters, use_container_width=True)

    # Načtení dat trhu pro aktuální výběr
    df_market = load_market_data(
        rok=selected_year,
        kraje=selected_kraj if selected_kraj else None,
        mesta=selected_mesto if selected_mesto else None,
        kategorie=selected_kategorie if selected_kategorie else None,
        obory=selected_obor if selected_obor else None,
        skoly=selected_skola if selected_skola else None
    )

elif page == "Detail školy":
    st.sidebar.header("Zúžení výběru školy")
    selected_year = st.sidebar.selectbox(
        "Vyberte rok",
        base_filter_opts["years"],
        index=0,
        key="detail_year"
    )
    selected_kraj = st.sidebar.multiselect("Filtrovat dle kraje", base_filter_opts["kraje"], key="detail_kraj")
    cascading_opts_detail = get_cascading_filter_options(kraje=selected_kraj if selected_kraj else None)
    selected_mesto = st.sidebar.multiselect("Filtrovat dle města", cascading_opts_detail["mesta"], key="detail_mesto")

    if selected_kraj or selected_mesto:
        st.sidebar.button("🔄 Resetovat filtry", on_click=reset_filters, use_container_width=True)

    selected_kategorie = None
    selected_obor = None
    selected_skola = None
    df_market = None
else:
    selected_year = 2026
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

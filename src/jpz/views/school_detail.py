"""
Pohled: Detail vybrané školy, benchmarking vůči trhu a bodové hranice.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from src.jpz.db import load_school_detail_data, load_all_schools_list

def render_school_detail_view(selected_year, selected_kraj, selected_mesto):
    st.header("🏫 Detail vybrané školy")

    # Získání seznamu škol odpovídajícího filtrům
    all_schools = load_all_schools_list(
        rok=selected_year,
        kraje=selected_kraj if selected_kraj else None,
        mesta=selected_mesto if selected_mesto else None
    )

    if not all_schools:
        st.warning("Pro zadané filtry nebyla nalezena žádná škola. Upravte výběr v levém panelu.")
        return

    # Rychlý full-text filtr pro výběr školy
    search_query = st.text_input("🔍 Rychlé vyhledání školy podle názvu nebo města:", placeholder="např. Kepler, Smíchovská, Kladno, Zatlanka, Plzeň...")
    if search_query.strip():
        filtered_schools = [s for s in all_schools if search_query.strip().lower() in s.lower()]
        if not filtered_schools:
            st.info(f"Žádná škola neodpovídá textu '{search_query}'. Zobrazuji všechny školy.")
            filtered_schools = all_schools
    else:
        filtered_schools = all_schools

    # Persistence vybrané školy v session_state
    if "last_selected_school" not in st.session_state or st.session_state.last_selected_school not in filtered_schools:
        st.session_state.last_selected_school = filtered_schools[0]

    default_index = 0
    if st.session_state.last_selected_school in filtered_schools:
        default_index = filtered_schools.index(st.session_state.last_selected_school)

    def on_school_change():
        st.session_state.last_selected_school = st.session_state.school_selector

    detail_school = st.selectbox(
        "Vyberte školu pro detailní analýzu:",
        filtered_schools,
        index=default_index,
        key="school_selector",
        on_change=on_school_change
    )
    st.session_state.last_selected_school = detail_school

    if not detail_school:
        return

    df_school, benchmark, prev_year = load_school_detail_data(detail_school, selected_year)

    if df_school.empty:
        st.info(f"Pro školu '{detail_school}' nejsou pro rok {selected_year} k dispozici záznamy.")
        return

    # Tlačítko pro export profilu školy
    c_btn1, c_btn2 = st.columns([3, 1])
    with c_btn2:
        csv_school = df_school.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Exportovat profil školy (CSV)",
            data=csv_school,
            file_name=f"{detail_school}_{selected_year}.csv",
            mime="text/csv"
        )

    # --- KPI METRIKY ---
    total_capacity = df_school['Kapacita'].sum()
    total_applicants = df_school['Prihlaseni'].sum()
    total_accepted = df_school['Prijati'].sum()

    school_previs = total_applicants / total_capacity if total_capacity > 0 else 0
    school_uspesnost = total_accepted / total_applicants * 100 if total_applicants > 0 else 0

    valid_avg_pct = df_school['Avg_Percentil'].dropna()
    school_avg_pct = valid_avg_pct.mean() if not valid_avg_pct.empty else None

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Celková kapacita", f"{int(total_capacity)} míst")

    avg_bm_previs = benchmark["avg_previs"] if benchmark else 0
    col2.metric(
        "Přihlášky (Převis)",
        f"{int(total_applicants)} ({school_previs:.2f}x)",
        delta=f"{school_previs - avg_bm_previs:.2f} vs region" if benchmark else None,
        delta_color="normal"
    )

    avg_bm_usp = benchmark["avg_uspesnost"] if benchmark else 0
    col3.metric(
        "Úspěšnost přijetí",
        f"{school_uspesnost:.1f} %",
        delta=f"{school_uspesnost - avg_bm_usp:.1f} % vs region" if benchmark else None,
        delta_color="inverse"
    )

    col4.metric(
        "Průměrný percentil školy",
        f"{school_avg_pct:.1f} %" if school_avg_pct is not None else "N/A",
        help="Průměrný percentil přijatých studentů z testů Cermat v JPZ."
    )

    if benchmark and benchmark["prihlaseni"] > 0:
        st.caption(f"📌 **Benchmark regionu:** Průměr konkurence ve stejném kraji a oborech: Převis **{avg_bm_previs:.2f}x**, Úspěšnost **{avg_bm_usp:.1f} %**.")

    # --- TABULKA OBORŮ ---
    st.divider()
    st.markdown("#### Nabízené obory a jejich statistiky")

    def format_change(row):
        if pd.isna(row.get('Prihlaseni_Prev')):
            return "Nový obor"
        diff = int(row['Zmena_Abs'])
        pct = row['Zmena_Pct']
        if diff > 0:
            return f"↑ {diff} (+{pct:.1f}%)"
        elif diff < 0:
            return f"↓ {diff} ({pct:.1f}%)"
        else:
            return "0 (0.0%)"

    if 'Prihlaseni_Prev' in df_school.columns:
        df_school['Meziroční trend'] = df_school.apply(format_change, axis=1)

    display_cols = [
        'Obor', 'Kategorie_Oboru', 'Kapacita', 'Prihlaseni', 'Meziroční trend',
        'Prijati', 'Previs_Poptavky', 'Uspesnost_Pct', 'Min_Percentil', 'Avg_Percentil', 'Min_Body'
    ]
    active_cols = [c for c in display_cols if c in df_school.columns]
    df_display = df_school[active_cols].copy()

    rename_map = {
        'Kategorie_Oboru': 'Kategorie',
        'Previs_Poptavky': 'Převis',
        'Uspesnost_Pct': 'Úspěšnost (%)',
        'Min_Percentil': 'Min. percentil',
        'Avg_Percentil': 'Prům. percentil',
        'Min_Body': 'Min. body'
    }
    df_display = df_display.rename(columns=rename_map)

    def color_trend(val):
        if isinstance(val, str):
            if "↑" in val:
                return 'color: #2ca02c; font-weight: bold;'
            elif "↓" in val:
                return 'color: #d62728; font-weight: bold;'
        return ''

    format_dict = {
        'Kapacita': '{:.0f}',
        'Prihlaseni': '{:.0f}',
        'Prijati': '{:.0f}',
        'Převis': '{:.2f}x',
        'Úspěšnost (%)': '{:.1f} %',
        'Min. percentil': lambda x: f"{x:.1f} %" if pd.notna(x) else "—",
        'Prům. percentil': lambda x: f"{x:.1f} %" if pd.notna(x) else "—",
        'Min. body': lambda x: f"{x:.0f}" if pd.notna(x) else "—"
    }

    styler = df_display.style.format({k: v for k, v in format_dict.items() if k in df_display.columns})
    if 'Meziroční trend' in df_display.columns:
        styler = styler.map(color_trend, subset=['Meziroční trend'])

    st.dataframe(styler, hide_index=True)

    # --- DETAILNÍ GRAFY PRO ŠKOLU ---
    st.divider()
    st.markdown("#### Rozpad priorit a důvodů nepřijetí po oborech")

    prio_type = st.radio(
        "Vyberte typ zobrazení priorit:",
        ["Přihlášení dle 1., 2. a 3. priority", "Přijatí žáci dle priority"],
        horizontal=True,
        key="school_prio_type"
    )

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        if prio_type == "Přihlášení dle 1., 2. a 3. priority":
            prio_vars = ['Prihlaseni_P1', 'Prihlaseni_P2', 'Prihlaseni_P3']
            prio_labels = {'Prihlaseni_P1': '1. Priorita', 'Prihlaseni_P2': '2. Priorita', 'Prihlaseni_P3': '3. Priorita'}
            chart_title = "Přihlášení dle preferencí"
        else:
            prio_vars = ['Prijati_P1', 'Prijati_P2', 'Prijati_P3']
            prio_labels = {'Prijati_P1': 'Z 1. priority', 'Prijati_P2': 'Z 2. priority', 'Prijati_P3': 'Z 3. priority'}
            chart_title = "Z jaké priority byli žáci přijati"

        has_prio = sum(df_school[c].sum() for c in prio_vars if c in df_school.columns) > 0

        if has_prio:
            df_school_prio = df_school.melt(
                id_vars=['Obor'],
                value_vars=[c for c in prio_vars if c in df_school.columns],
                var_name='Priorita', value_name='Pocet'
            )
            df_school_prio['Priorita'] = df_school_prio['Priorita'].map(prio_labels)

            fig_prio = px.bar(
                df_school_prio,
                x='Pocet',
                y='Obor',
                color='Priorita',
                orientation='h',
                title=chart_title,
                text_auto=True,
                color_discrete_map={
                    '1. Priorita': '#2ca02c', '2. Priorita': '#ff7f0e', '3. Priorita': '#1f77b4',
                    'Z 1. priority': '#2ca02c', 'Z 2. priority': '#ff7f0e', 'Z 3. priority': '#1f77b4'
                }
            )
            fig_prio.update_layout(yaxis={'categoryorder': 'total ascending'}, height=360, margin=dict(l=10, r=10, t=35, b=10))
            st.plotly_chart(fig_prio, width="stretch")
        else:
            st.info(f"Prioritní data pro rok {selected_year} nejsou k dispozici.")

    with col_g2:
        has_reject = (df_school['Duvod_Kapacita'].sum() + df_school['Duvod_Podminky'].sum() + df_school['Duvod_Vyssi_Priorita'].sum()) > 0
        if has_reject:
            df_school_reject = df_school.melt(
                id_vars=['Obor'],
                value_vars=['Duvod_Kapacita', 'Duvod_Podminky', 'Duvod_Vyssi_Priorita'],
                var_name='Duvod', value_name='Pocet'
            )
            reject_map = {
                'Duvod_Kapacita': 'Nedostačující kapacita',
                'Duvod_Podminky': 'Nesplnění podmínek',
                'Duvod_Vyssi_Priorita': 'Přijat na vyšší prioritu (Odliv)'
            }
            df_school_reject['Duvod'] = df_school_reject['Duvod'].map(reject_map)

            fig_reject = px.bar(
                df_school_reject,
                x='Pocet',
                y='Obor',
                color='Duvod',
                orientation='h',
                title="Důvody nepřijetí dle oborů",
                text_auto=True,
                color_discrete_map={'Nedostačující kapacita': '#d62728', 'Nesplnění podmínek': '#7f7f7f', 'Přijat na vyšší prioritu (Odliv)': '#9467bd'}
            )
            fig_reject.update_layout(yaxis={'categoryorder': 'total ascending'}, height=360, margin=dict(l=10, r=10, t=35, b=10))
            st.plotly_chart(fig_reject, width="stretch")
        else:
            st.info(f"Důvody nepřijetí nejsou pro rok {selected_year} evidovány.")

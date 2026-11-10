"""
Pohled: Srovnávač 2–3 škol vedle sebe (Head-to-Head).
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from src.jpz.db import load_comparison_data, load_all_schools_list, get_filter_options

def render_compare_view():
    st.header("⚖️ Srovnávač škol (Head-to-Head)")
    st.markdown("""
    Vyberte **2 až 3 střední školy**, které zvažujete. 
    Aplikace vám přehledně srovná jejich náročnost, převis poptávky, bodové hranice a chování uchazečů.
    """)

    filter_opts = get_filter_options()
    all_schools = load_all_schools_list()

    c1, c2 = st.columns([1, 3])
    with c1:
        cmp_year = st.selectbox("Vyberte rok pro srovnání", filter_opts["years"], index=0, key="cmp_year")

    with c2:
        default_selection = []
        for default_name in ["Gymnázium Jana Keplera", "Gymnázium prof. Jana Patočky"]:
            matches = [s for s in all_schools if default_name in s]
            if matches:
                default_selection.append(matches[0])

        selected_schools = st.multiselect(
            "Vyberte 2 až 3 školy ke srovnání:",
            all_schools,
            default=default_selection,
            max_selections=3
        )

    if len(selected_schools) < 2:
        st.info("💡 Vyberte alespoň **2 školy**, aby se zobrazilo porovnání.")
        return

    df_cmp = load_comparison_data(selected_schools, cmp_year)

    if df_cmp.empty:
        st.warning(f"Pro vybrané školy nejsou v roce {cmp_year} k dispozici data.")
        return

    # --- SOUHRNNÉ KARTY PRO JEDNOTLIVÉ ŠKOLY ---
    st.subheader("1. Celkové srovnání parametrů")

    cols = st.columns(len(selected_schools))

    for idx, school in enumerate(selected_schools):
        df_s = df_cmp[df_cmp['Škola'] == school]
        with cols[idx]:
            st.markdown(f"### 🏫 {school}")
            if not df_s.empty:
                cap = df_s['Kapacita'].sum()
                apps = df_s['Prihlaseni'].sum()
                acc = df_s['Prijati'].sum()
                previs = apps / cap if cap > 0 else 0
                uspesnost = acc / apps * 100 if apps > 0 else 0
                valid_avg = df_s['Avg_Percentil'].dropna()
                avg_pct = valid_avg.mean() if not valid_avg.empty else None
                valid_min = df_s['Min_Percentil'].dropna()
                min_pct = valid_min.min() if not valid_min.empty else None

                st.metric("Celková kapacita", f"{int(cap)} míst")
                st.metric("Převis poptávky", f"{previs:.2f}x ({int(apps)} přihlášek)")
                st.metric("Úspěšnost přijetí", f"{uspesnost:.1f} %")
                st.metric(
                    "Průměrný percentil přijatých",
                    f"{avg_pct:.1f} %" if avg_pct is not None else "N/A",
                    help="Průměrný percentil studentů z testů JPZ."
                )
                st.metric(
                    "Minimální percentil",
                    f"{min_pct:.1f} %" if min_pct is not None else "N/A",
                    help="Nejnižší percentil, se kterým byl žák na školu přijat."
                )
            else:
                st.info("Žádné záznamy.")

    # --- SROVNÁVACÍ GRAFY ---
    st.divider()
    st.subheader("2. Vizualizace rozdílů")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        # Srovnání přihlášek podle priority
        prio_data = []
        for school in selected_schools:
            df_s = df_cmp[df_cmp['Škola'] == school]
            prio_data.append({
                'Škola': school,
                '1. Priorita': df_s['Prihlaseni_P1'].sum(),
                '2. Priorita': df_s['Prihlaseni_P2'].sum(),
                '3. Priorita': df_s['Prihlaseni_P3'].sum(),
            })
        df_prio_plot = pd.DataFrame(prio_data).melt(id_vars=['Škola'], var_name='Priorita', value_name='Počet')

        fig_prio = px.bar(
            df_prio_plot,
            x='Škola',
            y='Počet',
            color='Priorita',
            barmode='group',
            title="Přihlášky dle 1., 2. a 3. priority",
            text_auto=True,
            color_discrete_map={'1. Priorita': '#2ca02c', '2. Priorita': '#ff7f0e', '3. Priorita': '#1f77b4'}
        )
        fig_prio.update_layout(height=400)
        st.plotly_chart(fig_prio, width="stretch")

    with col_chart2:
        # Srovnání důvodů nepřijetí (odliv vs kapacita)
        rej_data = []
        for school in selected_schools:
            df_s = df_cmp[df_cmp['Škola'] == school]
            rej_data.append({
                'Škola': school,
                'Nedostačující kapacita': df_s['Duvod_Kapacita'].sum(),
                'Nesplnění podmínek': df_s['Duvod_Podminky'].sum(),
                'Odliv na vyšší prioritu': df_s['Duvod_Vyssi_Priorita'].sum(),
            })
        df_rej_plot = pd.DataFrame(rej_data).melt(id_vars=['Škola'], var_name='Důvod', value_name='Počet')

        fig_rej = px.bar(
            df_rej_plot,
            x='Škola',
            y='Počet',
            color='Důvod',
            barmode='stack',
            title="Důvody nepřijetí (Absolutní počty)",
            text_auto=True,
            color_discrete_map={'Nedostačující kapacita': '#d62728', 'Nesplnění podmínek': '#7f7f7f', 'Odliv na vyšší prioritu': '#9467bd'}
        )
        fig_rej.update_layout(height=400)
        st.plotly_chart(fig_rej, width="stretch")

    # --- DETAILNÍ TABULKA OBORŮ ---
    st.divider()
    st.subheader("3. Srovnání oborů a bodových hranic")

    cols_show = [
        'Škola', 'Obor', 'Kategorie', 'Kapacita', 'Prihlaseni', 'Prijati',
        'Previs_Poptavky', 'Uspesnost_Pct', 'Min_Percentil', 'Avg_Percentil', 'Min_Body'
    ]
    df_table = df_cmp[cols_show].rename(columns={
        'Previs_Poptavky': 'Převis',
        'Uspesnost_Pct': 'Úspěšnost (%)',
        'Min_Percentil': 'Min. percentil',
        'Avg_Percentil': 'Prům. percentil',
        'Min_Body': 'Min. body'
    })

    st.dataframe(df_table, hide_index=True)


"""
Pohled: Celkový přehled trhu a meziroční trendy.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.jpz.db import load_yoy_data

def render_market_view(df_final, selected_year, selected_kraj, selected_mesto, selected_kategorie, selected_obor, selected_skola=None):
    st.header("📊 Celkový přehled trhu")

    if df_final.empty:
        st.warning("Pro zadanou kombinaci filtrů nebyla nalezena žádná data. Zkuste rozšířit výběr.")
        return

    # Tlačítko pro export
    c_head1, c_head2 = st.columns([3, 1])
    with c_head2:
        csv_data = df_final.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Stáhnout data (CSV)",
            data=csv_data,
            file_name=f"prijimacky_prehled_{selected_year}.csv",
            mime="text/csv",
            help="Stáhne aktuálně vyfiltrovanou tabulku do CSV (otevřitelné v Excelu)"
        )

    # --- SOUHRNNÉ METRIKY TRHU ---
    tot_capacity = int(df_final['Kapacita'].sum())
    tot_applicants = int(df_final['Prihlaseni'].sum())
    tot_accepted = int(df_final['Prijati'].sum())
    avg_previs = tot_applicants / tot_capacity if tot_capacity > 0 else 0
    avg_uspesnost = (tot_accepted / tot_applicants * 100) if tot_applicants > 0 else 0

    tot_odliv = df_final['Duvod_Vyssi_Priorita'].sum() if 'Duvod_Vyssi_Priorita' in df_final.columns else 0
    odliv_pct = (tot_odliv / tot_applicants * 100) if tot_applicants > 0 else 0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Celková kapacita", f"{tot_capacity:,} míst".replace(",", " "))
    kpi2.metric(
        "Podané přihlášky",
        f"{tot_applicants:,}".replace(",", " "),
        delta=f"{avg_previs:.2f}x převis",
        delta_color="off"
    )
    kpi3.metric(
        "Průměrná úspěšnost",
        f"{avg_uspesnost:.1f} %",
        help="Podíl přijatých žáků vůči všem podaným přihláškám."
    )
    kpi4.metric(
        "Míra odlivu uchazečů",
        f"{odliv_pct:.1f} %",
        help="Podíl uchazečů, kteří splnili kritéria, ale byli přijati na školu s vyšší prioritou."
    )

    st.divider()

    # --- 1. SCATTER PLOT: Šance vs. Konkurence ---
    st.subheader("1. Strategická matice: Šance vs. Konkurence")
    st.info("💡 **Vlevo nahoře:** Vysoká šance, malá konkurence (Jistota). **Vpravo dole:** Velká konkurence, malá šance (Masakr). Bubliny jsou škálované dle kapacity.")

    col1, col2 = st.columns([3, 1])

    with col1:
        hover_cols = {
            "Kapacita": True,
            "Prihlaseni": True,
            "Prijati": True,
            "Previs_Poptavky": ":.2f",
            "Uspesnost_Pct": ":.1f%",
            "Min_Percentil": True,
            "Avg_Percentil": True
        }
        fig_scatter = px.scatter(
            df_final,
            x="Previs_Poptavky",
            y="Uspesnost_Pct",
            size="Kapacita",
            color="Kategorie_Oboru" if "Kategorie_Oboru" in df_final.columns else "Zřizovatel",
            hover_name="Skola_Obor",
            hover_data=hover_cols,
            labels={
                "Previs_Poptavky": "Převis (Počet uchazečů na 1 místo)",
                "Uspesnost_Pct": "Úspěšnost (%)",
                "Kategorie_Oboru": "Kategorie",
                "Zřizovatel": "Zřizovatel"
            },
            title=f"Mapa škol a oborů ({selected_year})"
        )
        fig_scatter.add_vline(x=1, line_dash="dash", line_color="green", annotation_text="Kapacita = Poptávka")
        fig_scatter.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50% Šance")
        fig_scatter.update_layout(height=520, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_scatter, width="stretch")

    with col2:
        st.markdown("### Top 'Jistoty'")
        top_picks = df_final[(df_final['Previs_Poptavky'] < 1.2) & (df_final['Uspesnost_Pct'] > 80)]
        display_jistoty = top_picks[['Skola_Obor', 'Uspesnost_Pct', 'Previs_Poptavky']].sort_values('Uspesnost_Pct', ascending=False).head(10).copy()
        display_jistoty = display_jistoty.rename(columns={
            'Skola_Obor': 'Škola a obor',
            'Uspesnost_Pct': 'Úspěšnost',
            'Previs_Poptavky': 'Převis'
        })
        st.dataframe(
            display_jistoty.style.format({
                'Úspěšnost': '{:.1f} %',
                'Převis': '{:.2f}x'
            }),
            hide_index=True
        )

    # --- 2. ANALÝZA PRIORIT ---
    st.divider()
    st.subheader("2. Analýza priorit: Jsme první volba nebo záložní plán?")

    selected_schools = st.multiselect(
        "Vyber školy pro detailní srovnání priorit",
        df_final['Skola_Obor'].unique(),
        max_selections=15
    )

    if selected_schools:
        df_priorities = df_final[df_final['Skola_Obor'].isin(selected_schools)].copy()
    else:
        df_priorities = df_final.sort_values('Prihlaseni', ascending=False).head(10)
        st.caption("Zobrazuji TOP 10 škol/oborů dle počtu přihlášek (konkrétní vyberte výše).")

    prio_view_type = st.radio(
        "Zobrazit prioritu u:",
        ["Přihlášených uchazečů", "Přijatých žáků"],
        horizontal=True
    )

    if prio_view_type == "Přihlášených uchazečů":
        val_vars = ['Prihlaseni_P1', 'Prihlaseni_P2', 'Prihlaseni_P3']
        prio_map = {'Prihlaseni_P1': '1. Priorita', 'Prihlaseni_P2': '2. Priorita', 'Prihlaseni_P3': '3. Priorita'}
        chart_title = "Struktura přihlášek podle 1., 2. a 3. priority"
    else:
        val_vars = ['Prijati_P1', 'Prijati_P2', 'Prijati_P3']
        prio_map = {'Prijati_P1': 'Přijati z 1. priority', 'Prijati_P2': 'Přijati z 2. priority', 'Prijati_P3': 'Přijati z 3. priority'}
        chart_title = "Z jaké priority se reálně dostali přijatí žáci"

    total_prio_sum = sum(df_priorities[c].sum() for c in val_vars if c in df_priorities.columns)

    if total_prio_sum > 0:
        df_melted_prio = df_priorities.melt(
            id_vars=['Skola_Obor'],
            value_vars=[c for c in val_vars if c in df_priorities.columns],
            var_name='Priorita', value_name='Pocet'
        )
        df_melted_prio['Priorita'] = df_melted_prio['Priorita'].map(prio_map)

        color_map = {
            '1. Priorita': '#2ca02c', '2. Priorita': '#ff7f0e', '3. Priorita': '#1f77b4',
            'Přijati z 1. priority': '#2ca02c', 'Přijati z 2. priority': '#ff7f0e', 'Přijati z 3. priority': '#1f77b4'
        }

        fig_bar = px.bar(
            df_melted_prio,
            x='Pocet',
            y='Skola_Obor',
            color='Priorita',
            orientation='h',
            title=chart_title,
            text_auto=True,
            color_discrete_map=color_map
        )
        fig_bar.update_layout(yaxis={'categoryorder': 'total ascending'}, height=420)
        st.plotly_chart(fig_bar, width="stretch")
    else:
        st.info(f"Pro rok {selected_year} nejsou k dispozici detailní data pro tuto metriku.")

    # --- 3. DŮVODY ZAMÍTNUTÍ ---
    st.divider()
    st.subheader("3. Proč to nevyšlo? (Důvody nepřijetí)")

    has_reject_data = (df_priorities['Duvod_Kapacita'].sum() + df_priorities['Duvod_Podminky'].sum() + df_priorities['Duvod_Vyssi_Priorita'].sum()) > 0

    if has_reject_data:
        df_melted_reject = df_priorities.melt(
            id_vars=['Skola_Obor'],
            value_vars=['Duvod_Kapacita', 'Duvod_Podminky', 'Duvod_Vyssi_Priorita'],
            var_name='Duvod', value_name='Pocet'
        )
        reject_map = {
            'Duvod_Kapacita': 'Nedostačující kapacita',
            'Duvod_Podminky': 'Nesplnění podmínek',
            'Duvod_Vyssi_Priorita': 'Přijat na vyšší prioritu (Odliv)'
        }
        df_melted_reject['Duvod'] = df_melted_reject['Duvod'].map(reject_map)

        show_relative = st.checkbox("Zobrazit jako % (Relativní rozložení důvodů)", value=False)

        if show_relative:
            df_reject_pct = df_melted_reject.copy()
            df_totals = df_reject_pct.groupby('Skola_Obor')['Pocet'].transform('sum')
            df_reject_pct['Pocet_Pct'] = (df_reject_pct['Pocet'] / df_totals * 100).fillna(0)

            fig_reject = px.bar(
                df_reject_pct,
                x='Pocet_Pct',
                y='Skola_Obor',
                color='Duvod',
                orientation='h',
                title="Struktura důvodů zamítnutí (%)",
                labels={'Pocet_Pct': 'Podíl (%)'},
                text_auto='.1f',
                color_discrete_map={'Nedostačující kapacita': '#d62728', 'Nesplnění podmínek': '#7f7f7f', 'Přijat na vyšší prioritu (Odliv)': '#9467bd'}
            )
            fig_reject.update_layout(yaxis={'categoryorder': 'total ascending'}, height=420)
            st.plotly_chart(fig_reject, width="stretch")
            st.caption("💡 **Interpretace:** Pokud dominuje fialová (Odliv), škola je často 'záložní volbou'. Pokud červená (Kapacita), je o školu reálný převis.")
        else:
            fig_reject = px.bar(
                df_melted_reject,
                x='Pocet',
                y='Skola_Obor',
                color='Duvod',
                orientation='h',
                title="Analýza zamítnutých uchazečů (Absolutní počty)",
                text_auto=True,
                color_discrete_map={'Nedostačující kapacita': '#d62728', 'Nesplnění podmínek': '#7f7f7f', 'Přijat na vyšší prioritu (Odliv)': '#9467bd'}
            )
            fig_reject.update_layout(yaxis={'categoryorder': 'total ascending'}, height=420)
            st.plotly_chart(fig_reject, width="stretch")
    else:
        st.info("Pro zadaný výběr nejsou evidovány detailní důvody nepřijetí (kapacita, podmínky, odliv).")

    # --- 4. OBOROVÁ ANALÝZA ---
    st.divider()
    st.subheader("4. Oborová analýza: Kde je největší nával?")

    df_obory = df_final.groupby(['Obor', 'Kategorie_Oboru'])[['Kapacita', 'Prihlaseni', 'Prijati']].sum().reset_index()
    df_obory['Previs'] = (df_obory['Prihlaseni'] / df_obory['Kapacita']).fillna(0)
    df_obory = df_obory[df_obory['Kapacita'] > 0]

    fig_obory = px.bar(
        df_obory.sort_values('Previs', ascending=False).head(15),
        x='Previs',
        y='Obor',
        color='Kategorie_Oboru',
        orientation='h',
        title="Top 15 oborů s největším převisem poptávky",
        labels={'Previs': 'Převis (Počet přihlášek na 1 místo)', 'Kategorie_Oboru': 'Kategorie'},
        text='Previs'
    )
    fig_obory.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    fig_obory.update_layout(yaxis={'categoryorder': 'total ascending'}, height=450)
    st.plotly_chart(fig_obory, width="stretch")

    # --- 5. MEZIROČNÍ SROVNÁNÍ TRENDŮ ---
    st.divider()
    st.subheader("5. Meziroční srovnání trendů")

    df_yoy_base = load_yoy_data(
        kraje=selected_kraj if selected_kraj else None,
        mesta=selected_mesto if selected_mesto else None,
        kategorie=selected_kategorie if selected_kategorie else None,
        obory=selected_obor if selected_obor else None
    )

    if not df_yoy_base.empty and len(df_yoy_base['Rok'].unique()) >= 2:
        available_years = sorted(df_yoy_base['Rok'].unique(), reverse=True)
        col_y1, col_y2 = st.columns(2)
        with col_y1:
            base_year = st.selectbox("Srovnávaný (novější) rok", available_years, index=0, key="yoy_base_year")
        with col_y2:
            comp_years = [y for y in available_years if y != base_year]
            comp_year = st.selectbox("Referenční (starší) rok", comp_years, index=0 if comp_years else 0, key="yoy_comp_year")

        df_pivot = df_yoy_base.pivot(index='Obor', columns='Rok', values='Prihlaseni').fillna(0)
        df_pivot.columns = [str(c) for c in df_pivot.columns]
        s_base_year = str(base_year)
        s_comp_year = str(comp_year)

        if s_base_year in df_pivot.columns and s_comp_year in df_pivot.columns:
            df_pivot['Zmena_Abs'] = df_pivot[s_base_year] - df_pivot[s_comp_year]
            df_pivot['Zmena_Pct'] = ((df_pivot[s_base_year] - df_pivot[s_comp_year]) / df_pivot[s_comp_year].replace(0, pd.NA) * 100).fillna(0)

            top_growers = df_pivot[df_pivot['Zmena_Abs'] > 0].sort_values('Zmena_Abs', ascending=False).head(5)
            top_losers = df_pivot[df_pivot['Zmena_Abs'] < 0].sort_values('Zmena_Abs', ascending=True).head(5)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"#### 🚀 Skokani ({comp_year} ➔ {base_year})")
                st.dataframe(top_growers[[s_comp_year, s_base_year, 'Zmena_Abs', 'Zmena_Pct']].style.format({
                    s_comp_year: "{:.0f}",
                    s_base_year: "{:.0f}",
                    'Zmena_Abs': "{:+.0f}",
                    'Zmena_Pct': "{:+.1f}%"
                }))
            with c2:
                st.markdown(f"#### 📉 Pokles zájmu ({comp_year} ➔ {base_year})")
                st.dataframe(top_losers[[s_comp_year, s_base_year, 'Zmena_Abs', 'Zmena_Pct']].style.format({
                    s_comp_year: "{:.0f}",
                    s_base_year: "{:.0f}",
                    'Zmena_Abs': "{:+.0f}",
                    'Zmena_Pct': "{:+.1f}%"
                }))

            st.markdown(f"#### Posun v preferencích uchazečů (Podíl 1. priorit)")
            df_prio_yoy = df_yoy_base.copy()
            df_prio_yoy['Podil_P1'] = (df_prio_yoy['Prihlaseni_P1'] / df_prio_yoy['Prihlaseni'].replace(0, pd.NA) * 100).fillna(0)
            df_prio_pivot = df_prio_yoy.pivot(index='Obor', columns='Rok', values='Podil_P1').dropna()

            total_apps = df_yoy_base[df_yoy_base['Rok'] == base_year].groupby('Obor')['Prihlaseni'].sum()
            top_obory_idx = total_apps.sort_values(ascending=False).head(15).index
            df_plot = df_prio_pivot.loc[df_prio_pivot.index.intersection(top_obory_idx)].copy()

            if not df_plot.empty and base_year in df_plot.columns and comp_year in df_plot.columns:
                df_plot = df_plot.sort_values(by=base_year, ascending=True)
                fig_dumbbell = go.Figure()

                for obor, row in df_plot.iterrows():
                    color = "#2ca02c" if row[base_year] >= row[comp_year] else "#d62728"
                    fig_dumbbell.add_trace(go.Scatter(
                        x=[row[comp_year], row[base_year]],
                        y=[obor, obor],
                        mode="lines",
                        line=dict(color=color, width=2.5),
                        showlegend=False,
                        hoverinfo="skip"
                    ))

                fig_dumbbell.add_trace(go.Scatter(
                    x=df_plot[comp_year],
                    y=df_plot.index,
                    mode="markers",
                    name=str(comp_year),
                    marker=dict(color="#7f7f7f", size=9),
                    hovertemplate=f"{comp_year}: %{{x:.1f}}%<extra></extra>"
                ))

                fig_dumbbell.add_trace(go.Scatter(
                    x=df_plot[base_year],
                    y=df_plot.index,
                    mode="markers",
                    name=str(base_year),
                    marker=dict(color="#1f77b4", size=11),
                    hovertemplate=f"{base_year}: %{{x:.1f}}%<extra></extra>"
                ))

                fig_dumbbell.update_layout(
                    title=f"Posun podílu 1. priorit ({comp_year} vs {base_year})",
                    xaxis_title="Podíl 1. priorit (%)",
                    yaxis_title="Obor",
                    height=500,
                    margin=dict(l=0, r=0, t=40, b=10)
                )
                st.plotly_chart(fig_dumbbell, width="stretch")
    else:
        st.info("Pro meziroční srovnání je potřeba mít k dispozici data pro alespoň dva různé roky.")

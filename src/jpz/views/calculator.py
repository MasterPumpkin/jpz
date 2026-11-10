"""
Pohled: Kalkulačka šancí a strategický rádce pro 3 přihlášky.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from src.jpz.db import calculate_chances, get_filter_options, load_all_schools_list, evaluate_three_priorities, get_connection

def render_calculator_view():
    st.header("🎯 Kalkulačka šancí & Strategie přihlášek")

    tab1, tab2 = st.tabs(["🎯 Prediktor šancí podle bodů", "📋 Strategický rádce pro 3 přihlášky"])

    filter_opts = get_filter_options()

    # =========================================================================
    # ZÁLOŽKA 1: PREDIKTOR ŠANCÍ
    # =========================================================================
    with tab1:
        st.markdown("""
        Zadejte své body z **Českého jazyka** (0–50) a **Matematiky** (0–50).
        Aplikace přepočte body na národní percentil z testů Cermat a vyhodnotí vaši šanci na přijetí na všechny střední školy v ČR.
        """)

        st.subheader("1. Zadejte své body a filtry")

        c1, c2, c3 = st.columns(3)
        with c1:
            points_cjl = st.slider("Český jazyk (0–50 bodů)", min_value=0.0, max_value=50.0, value=35.0, step=1.0, key="calc_cjl")
        with c2:
            points_mat = st.slider("Matematika (0–50 bodů)", min_value=0.0, max_value=50.0, value=30.0, step=1.0, key="calc_mat")
        with c3:
            calc_year = st.selectbox("Srovnat s rokem", filter_opts["years"], index=0, key="calc_year")

        f1, f2, f3 = st.columns(3)
        with f1:
            calc_kraj = st.selectbox("Kraj", ["Všechny kraje"] + filter_opts["kraje"], index=0, key="calc_kraj")
        with f2:
            # Kategorie z databáze
            conn = get_connection()
            kat_list = [r[0] for r in conn.execute("SELECT DISTINCT kategorie_oboru FROM obory WHERE kategorie_oboru IS NOT NULL ORDER BY kategorie_oboru").fetchall()]
            conn.close()
            calc_kat = st.selectbox("Kategorie školy", ["Všechny kategorie"] + kat_list, index=0, key="calc_kat")
        with f3:
            calc_search = st.text_input("Hledat školu nebo obor", placeholder="např. Kepler, Gymnázium, IT...", key="calc_search")

        kraj_param = None if calc_kraj == "Všechny kraje" else calc_kraj
        kat_param = None if calc_kat == "Všechny kategorie" else calc_kat
        search_param = calc_search.strip() if calc_search.strip() else None

        result = calculate_chances(
            rok=calc_year,
            body_cjl=points_cjl,
            body_mat=points_mat,
            kraj=kraj_param,
            kategorie=kat_param,
            query_search=search_param
        )

        pct_cjl = result["pct_cjl"]
        pct_mat = result["pct_mat"]
        avg_pct = result["avg_pct"]
        total_pts = result["total_points"]
        df_res = result["results"]

        st.divider()
        st.subheader("2. Váš vypočtený percentil")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Celkem bodů", f"{total_pts:.0f} / 100")
        m2.metric("Percentil ČJL", f"{pct_cjl:.1f} %")
        m3.metric("Percentil MAT", f"{pct_mat:.1f} %")
        m4.metric("🏆 Průměrný percentil", f"{avg_pct:.1f} %")

        if not df_res.empty:
            safe_count = len(df_res[df_res['Sance'].str.contains('Vysoká')])
            edge_count = len(df_res[df_res['Sance'].str.contains('Reálná')])
            risky_count = len(df_res[df_res['Sance'].str.contains('Rizikové')])

            st.markdown(f"""
            Podle dat z roku **{calc_year}** máte pro vybraná kritéria:
            * 🟢 **Vysoká šance (Bezpečné):** **{safe_count}** oborů (Váš percentil je vyšší než průměr přijatých)
            * 🟡 **Reálná šance (Na hraně):** **{edge_count}** oborů (Váš percentil je mezi minimem a průměrem přijatých)
            * 🔴 **Rizikové (Nízká šance):** **{risky_count}** oborů (Váš percentil byl pod minimální hranicí přijetí)
            """)

            col_flt, col_exp = st.columns([3, 1])
            with col_flt:
                filter_sance = st.multiselect(
                    "Filtrovat zobrazené školy podle míry šance:",
                    ["🟢 Vysoká šance (Bezpečné)", "🟡 Reálná šance (Na hraně)", "🔴 Rizikové (Nízká šance)"],
                    default=["🟢 Vysoká šance (Bezpečné)", "🟡 Reálná šance (Na hraně)"],
                    key="flt_sance"
                )
            with col_exp:
                csv_calc = df_res.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Stáhnout výsledky (CSV)",
                    data=csv_calc,
                    file_name=f"vysledky_sance_{total_pts:.0f}b_{calc_year}.csv",
                    mime="text/csv"
                )

            df_filtered = df_res[df_res['Sance'].isin(filter_sance)] if filter_sance else df_res

            st.markdown("#### Porovnání vaší pozice vůči náročnosti škol")
            fig_hist = px.histogram(
                df_res,
                x="Avg_Percentil",
                color="Kategorie",
                nbins=30,
                title="Distribuce náročnosti oborů (Průměrný percentil přijatých)",
                labels={"Avg_Percentil": "Průměrný percentil přijatých", "count": "Počet oborů"}
            )
            fig_hist.add_vline(
                x=avg_pct,
                line_dash="dash",
                line_color="gold",
                line_width=3,
                annotation_text=f"Váš výsledek ({avg_pct:.1f} %)",
                annotation_position="top left"
            )
            fig_hist.update_layout(height=360, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_hist, width="stretch")

            st.markdown("#### Seznam škol a oborů s vyhodnocením")
            cols_to_show = [
                'Sance', 'Škola', 'Obor', 'Kategorie', 'Město', 'Kraj',
                'Min_Percentil', 'Avg_Percentil', 'Min_Body', 'Převis_P1', 'Kapacita'
            ]
            df_show = df_filtered[cols_to_show].rename(columns={
                'Sance': 'Vyhodnocení',
                'Min_Percentil': 'Min. percentil',
                'Avg_Percentil': 'Prům. percentil',
                'Min_Body': 'Min. body',
                'Převis_P1': 'Přetlak (P1/místo)'
            })

            st.dataframe(df_show, hide_index=True)
        else:
            st.warning("Pro zadaná kritéria nebyly nalezeny žádné školy. Zkuste upravit filtry.")

    # =========================================================================
    # ZÁLOŽKA 2: STRATEGICKÝ RÁDCE PRO 3 PŘIHLÁŠKY
    # =========================================================================
    with tab2:
        st.subheader("📋 Analýza a strategie vašich 3 přihlášek")
        st.markdown("""
        Při podávání přihlášek na střední školy je klíčové pořadí priorit:
        * **1. priorita (Sen):** Vaše vysněná škola, i když je náročnější.
        * **2. priorita (Realita):** Škola odpovídající vašim reálným schopnostem.
        * **3. priorita (Jistota / Záchranná síť):** Bezpečná volba, kde máte vysokou šanci na přijetí.

        > ⚠️ **Častá chyba:** Dát jako 3. prioritu školu, která je těžší než 1. nebo 2. priorita. Pokud neuspějete na 1. škole, na 3. škole nemáte šanci, a přihláška tak propadne.
        """)

        conn = get_connection()
        school_obor_pairs = conn.execute("""
            SELECT DISTINCT 
                s.redizo,
                COALESCE(s.display_name, s.nazev_skoly || ', ' || s.mesto, s.nazev_skoly) AS skola_disp,
                o.nazev_oboru 
            FROM skoly_historie h 
            JOIN skoly s ON h.redizo = s.redizo 
            JOIN obory o ON h.kod_oboru = o.kod_oboru
            WHERE h.min_percentil > 0
            ORDER BY skola_disp, o.nazev_oboru
        """).fetchall()
        conn.close()

        options_map = {f"{r['skola_disp']} – {r['nazev_oboru']}": (r['redizo'], r['nazev_oboru']) for r in school_obor_pairs}
        options_list = list(options_map.keys())

        c_opt1, c_opt2 = st.columns([1, 1])
        with c_opt1:
            strat_pts_cjl = st.number_input("Očekávané body z ČJL (0–50)", min_value=0.0, max_value=50.0, value=35.0, step=1.0, key="strat_cjl")
        with c_opt2:
            strat_pts_mat = st.number_input("Očekávané body z MAT (0–50)", min_value=0.0, max_value=50.0, value=30.0, step=1.0, key="strat_mat")

        strat_year = st.selectbox("Srovnat s rokem:", filter_opts["years"], index=0, key="strat_year")

        # Spočtení percentilu
        temp_calc = calculate_chances(strat_year, strat_pts_cjl, strat_pts_mat)
        user_percentile = temp_calc["avg_pct"]
        st.info(f"Váš předpokládaný průměrný percentil je **{user_percentile:.1f} %** ({strat_pts_cjl + strat_pts_mat:.0f} bodů).")

        col_p1, col_p2, col_p3 = st.columns(3)

        with col_p1:
            st.markdown("#### 🥇 1. Priorita (Vysněná)")
            sel1 = st.selectbox("1. Volba", options_list, index=0 if len(options_list) > 0 else None, key="sel_p1")
        with col_p2:
            st.markdown("#### 🥈 2. Priorita (Realistická)")
            sel2 = st.selectbox("2. Volba", options_list, index=1 if len(options_list) > 1 else None, key="sel_p2")
        with col_p3:
            st.markdown("#### 🥉 3. Priorita (Jistota)")
            sel3 = st.selectbox("3. Volba", options_list, index=2 if len(options_list) > 2 else None, key="sel_p3")

        ch1 = options_map.get(sel1)
        ch2 = options_map.get(sel2)
        ch3 = options_map.get(sel3)

        strat_res = evaluate_three_priorities(strat_year, ch1, ch2, ch3, user_percentile)

        if strat_res:
            st.divider()
            st.markdown("### Vyhodnocení vaší přihláškové strategie")

            cards = st.columns(len(strat_res))
            for i, item in enumerate(strat_res):
                with cards[i]:
                    st.markdown(f"**{item['priorita']}. priorita:** {item['stav']}")
                    st.write(f"**{item['skola']}**")
                    st.caption(f"{item['obor']} ({item['kategorie']})")
                    st.metric("Minimální percentil", f"{item['min_pct']:.1f} %")
                    st.metric("Průměrný percentil", f"{item['avg_pct']:.1f} %")
                    st.metric("Přetlak (P1/místo)", f"{item['previs']:.2f}x")

            # Analýza hierarchie a logiky
            pcts = [item['min_pct'] for item in strat_res]
            is_descending = all(pcts[i] >= pcts[i+1] for i in range(len(pcts)-1))

            st.markdown("#### 💡 Doporučení:")
            if len(pcts) >= 2 and pcts[-1] > pcts[0]:
                st.error("🚨 **Kritická chyba v prioritách:** Vaše 3. priorita vyžaduje vyšší percentil než 1. priorita! Pokud neuspějete na 1. škole, na 3. škole se téměř jistě neumístíte. Prohoďte pořadí priorit nebo zvolte bezpečnější 3. školu.")
            elif not is_descending:
                st.warning("⚠️ **Pozor na pořadí obtížnosti:** Pořadí vašich voleb neklesá podle náročnosti. Doporučujeme řadit školy od nejnáročnější po nejbezpečnější.")
            else:
                st.success("✅ **Výborná posloupnost priorit:** Školy máte seřazené od nejnáročnější po nejbezpečnější.")

            # Kontrola záchranné sítě
            has_safety = any(user_percentile >= item['avg_pct'] for item in strat_res)
            if not has_safety:
                st.warning("⚠️ **Chybí vám bezpečná pojistka:** U žádné ze 3 škol nemáte percentil vyšší než průměr přijatých žáků. Zvažte zařazení jedné 'jistoty' na 3. prioritu, abyste minimalizovali riziko, že se nedostanete nikam.")
            else:
                st.info("🛡️ **Máte záchrannou síť:** Alespoň jedna z vašich škol má průměrný percentil přijatých pod vaší bodovou úrovní.")

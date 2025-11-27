import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="Analýza přijímacích řízení", layout="wide")

st.title("📊 Analýza přijímacích řízení na střední školy (2024–2025)")
st.markdown("""
Tento dashboard řeší specifika dat:
* **Kapacita** se pro rok 2025 počítá pouze z 1. kola (aby se nedublovala).
* **Přihlášky a přijetí** se sčítají za obě kola.
* **Granularita**: Data jsou zobrazena pro každou kombinaci Škola + Obor.
""")

# --- 1. NAČTENÍ A PŘÍPRAVA DAT ---
@st.cache_data
def load_data():
    # Načtení CSV
    df = pd.read_csv('data.csv')
    
    # Přejmenování sloupců pro snazší práci
    col_map = {
        'Součet hodnot: Kapacita': 'Kapacita',
        'Součet hodnot: Přihlášeni': 'Prihlaseni',
        'Součet hodnot: Přijati': 'Prijati',
        'Součet hodnot: Přihlášeni - priorita 1': 'Prihlaseni_P1',
        'Součet hodnot: Přihlášeni - priorita 2': 'Prihlaseni_P2',
        'Součet hodnot: Přihlášeni - priorita 3': 'Prihlaseni_P3',
        'Součet hodnot: Přijati - priorita 1': 'Prijati_P1',
        'Součet hodnot: Nepřijati - nedostačující kapacita': 'Duvod_Kapacita',
        'Součet hodnot: Nepřijati - nesplnění podmínek': 'Duvod_Podminky',
        'Součet hodnot: Nepřijati - přijati na vyšší prioritu': 'Duvod_Vyssi_Priorita',
        'Součet hodnot: REDIZO': 'REDIZO'
    }
    df = df.rename(columns=col_map)
    
    # Vytvoření unikátního ID (Škola + Obor + Město)
    # Přidáváme město pro lepší rozlišení a informovanost
    df['Skola_Obor'] = df['Škola'] + ", " + df['Město'] + " (" + df['Obor'] + ")"

    # Normalizace názvů oborů (sjednocení pomlček a mezer)
    # Nahradíme en-dash (–) za hyphen (-) a odstraníme vícenásobné mezery
    df['Obor'] = df['Obor'].str.replace('–', '-', regex=False).str.replace(r'\s+', ' ', regex=True).str.strip()

    # --- Normalizace názvů škol podle REDIZO ---
    # Cíl: Aby měla škola v roce 2024 i 2025 stejný název (pro grouping a persistenci)
    if 'REDIZO' in df.columns:
        # Vytvoříme mapování REDIZO -> Kanonický název
        # Strategie: Vezmeme název z nejnovějšího roku (2025), pokud existuje, jinak jakýkoliv.
        # Nebo jednodušeji: vezmeme nejkratší název (často bez adresy).
        
        # Získáme unikátní páry REDIZO, Škola, Rok
        school_names = df[['REDIZO', 'Škola', 'Rok']].drop_duplicates()
        
        # Seřadíme podle roku sestupně (2025 první) a pak podle délky názvu
        school_names['NameLength'] = school_names['Škola'].str.len()
        school_names = school_names.sort_values(['REDIZO', 'Rok', 'NameLength'], ascending=[True, False, True])
        
        # Pro každé REDIZO vezmeme první (nejnovější/nejkratší) název
        canonical_names = school_names.groupby('REDIZO')['Škola'].first()
        
        # Aplikujeme mapování na hlavní dataframe
        df['Škola'] = df['REDIZO'].map(canonical_names).fillna(df['Škola'])

    return df

df_raw = load_data()

# --- 2. FILTRY (SIDEBAR) ---
st.sidebar.header("Filtry")
selected_year = st.sidebar.selectbox("Vyber rok", sorted(df_raw['Rok'].unique(), reverse=True))
selected_kraj = st.sidebar.multiselect("Vyber kraj", sorted(df_raw['Kraj'].unique()))

# Dynamický filtr měst (zobrazí jen města ve vybraných krajích)
if selected_kraj:
    available_cities = df_raw[df_raw['Kraj'].isin(selected_kraj)]['Město'].unique()
else:
    available_cities = df_raw['Město'].unique()

selected_mesto = st.sidebar.multiselect("Vyber město", sorted(available_cities))
selected_obor = st.sidebar.multiselect("Vyber obor", sorted(df_raw['Obor'].unique()))

# Aplikace základních filtrů
df_filtered = df_raw[df_raw['Rok'] == selected_year]
if selected_kraj:
    df_filtered = df_filtered[df_filtered['Kraj'].isin(selected_kraj)]
if selected_mesto:
    df_filtered = df_filtered[df_filtered['Město'].isin(selected_mesto)]
if selected_obor:
    df_filtered = df_filtered[df_filtered['Obor'].isin(selected_obor)]

# --- 3. AGREGACE DAT (LOGIKA 1. A 2. KOLA) ---
# Tady je to kouzlo: Kapacitu bereme jen kde Kolo=1, ostatní sumujeme
# Abychom to mohli spojit, seskupíme data podle unikátních klíčů

group_cols = ['Skola_Obor', 'Škola', 'Obor', 'Zřizovatel', 'Okres']

# A) Kapacita (pouze 1. kolo)
df_cap = df_filtered[df_filtered['Kolo'] == 1].groupby(group_cols)['Kapacita'].sum().reset_index()

# B) Ostatní metriky (suma přes všechna kola)
metric_cols = ['Prihlaseni', 'Prijati', 'Prihlaseni_P1', 'Prihlaseni_P2', 'Prihlaseni_P3', 
               'Prijati_P1', 'Duvod_Kapacita', 'Duvod_Podminky', 'Duvod_Vyssi_Priorita']
df_metrics = df_filtered.groupby(group_cols)[metric_cols].sum().reset_index()

# Spojení tabulek (Merge)
df_final = pd.merge(df_cap, df_metrics, on=group_cols, how='inner')

# --- 4. VÝPOČET METRIK ---
df_final['Uspesnost_Pct'] = (df_final['Prijati'] / df_final['Prihlaseni'] * 100).fillna(0)
df_final['Previs_Poptavky'] = (df_final['Prihlaseni'] / df_final['Kapacita']).fillna(0)
df_final['Uspesnost_P1_Pct'] = (df_final['Prijati_P1'] / df_final['Prihlaseni_P1'] * 100).fillna(0)
# Index odlivu (kolik % přihlášených uteklo na lepší školu)
df_final['Index_Odlivu'] = (df_final['Duvod_Vyssi_Priorita'] / df_final['Prihlaseni'] * 100).fillna(0)

# Filtr pro odstranění chyb (např. nulová kapacita)
df_final = df_final[df_final['Kapacita'] > 0]

# --- 5. NAVIGACE A VIZUALIZACE ---
page = st.sidebar.radio("Přejít na", ["Celkový přehled trhu", "Detail školy"])

if page == "Celkový přehled trhu":
    st.header("Celkový přehled trhu")
    
    # --- A) SCATTER PLOT: Šance vs. Konkurence ---
    st.subheader("1. Strategická matice: Šance vs. Konkurence")
    st.info("💡 **Vlevo nahoře:** Vysoká šance, malá konkurence (Jistota). **Vpravo dole:** Velká konkurence, malá šance (Masakr).")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        fig_scatter = px.scatter(
            df_final,
            x="Previs_Poptavky",
            y="Uspesnost_Pct",
            size="Kapacita",
            color="Zřizovatel",
            hover_name="Skola_Obor",
            hover_data={"Kapacita": True, "Prihlaseni": True, "Prijati": True},
            labels={"Previs_Poptavky": "Převis (Počet uchazečů na 1 místo)", "Uspesnost_Pct": "Úspěšnost (%)"},
            title=f"Mapa škol ({selected_year})"
        )
        # Přidání linek pro orientaci
        fig_scatter.add_vline(x=1, line_dash="dash", line_color="green", annotation_text="Kapacita = Poptávka")
        fig_scatter.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50% Šance")
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    with col2:
        st.markdown("### Top 'Jistoty'")
        # Školy s převisem < 1.2 a úspěšností > 80%
        top_picks = df_final[(df_final['Previs_Poptavky'] < 1.2) & (df_final['Uspesnost_Pct'] > 80)]
        st.dataframe(top_picks[['Skola_Obor', 'Uspesnost_Pct']].sort_values('Uspesnost_Pct', ascending=False).head(10), hide_index=True)
    
    # --- B) PRIORITY: Jak nás berou uchazeči ---
    st.divider()
    st.subheader("2. Analýza Priorit: Jsme první volba nebo záložní plán?")
    
    # Uživatel si může vybrat konkrétní školy pro detail
    selected_schools = st.multiselect("Vyber školy pro detailní srovnání priorit", df_final['Skola_Obor'].unique(), max_selections=10)
    
    if selected_schools:
        df_priorities = df_final[df_final['Skola_Obor'].isin(selected_schools)].copy()
    else:
        # Defaultně top 10 škol podle počtu přihlášek
        df_priorities = df_final.sort_values('Prihlaseni', ascending=False).head(10)
        st.caption("Zobrazuji TOP 10 škol dle počtu přihlášek (vyberte konkrétní výše).")
    
    # Transformace dat pro Stacked Bar Chart
    df_melted_prio = df_priorities.melt(
        id_vars=['Skola_Obor'], 
        value_vars=['Prihlaseni_P1', 'Prihlaseni_P2', 'Prihlaseni_P3'],
        var_name='Priorita', value_name='Pocet'
    )
    # Přejmenování pro legendu
    prio_map = {'Prihlaseni_P1': '1. Priorita', 'Prihlaseni_P2': '2. Priorita', 'Prihlaseni_P3': '3. Priorita'}
    df_melted_prio['Priorita'] = df_melted_prio['Priorita'].map(prio_map)
    
    fig_bar = px.bar(
        df_melted_prio, 
        x='Pocet', 
        y='Skola_Obor', 
        color='Priorita', 
        orientation='h',
        title="Struktura přihlášek podle priority",
        text_auto=True,
        color_discrete_map={'1. Priorita': '#2ca02c', '2. Priorita': '#ff7f0e', '3. Priorita': '#1f77b4'}
    )
    st.plotly_chart(fig_bar, use_container_width=True)
    
    # --- C) DŮVODY ZAMÍTNUTÍ ---
    st.divider()
    st.subheader("3. Proč to nevyšlo? (Důvody nepřijetí)")
    
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
    
    # Přepínač pro relativní zobrazení (100% Stacked Bar)
    show_relative = st.checkbox("Zobrazit jako % (Relativní rozložení důvodů)", value=False)
    
    if show_relative:
        # Přepočet na procenta
        df_reject_pct = df_melted_reject.copy()
        # Celkový počet odmítnutých pro každou školu
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
        st.plotly_chart(fig_reject, use_container_width=True)
        st.caption("💡 **Interpretace:** Pokud dominuje fialová (Odliv), škola je často 'záložní volbou'. Pokud červená (Kapacita), je o školu reálný zájem.")
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
        st.plotly_chart(fig_reject, use_container_width=True)
    
    # --- D) OBOROVÁ ANALÝZA ---
    st.divider()
    st.subheader("4. Oborová analýza: Kde je největší nával?")
    
    # Agregace dle oborů (z df_final, který už respektuje filtry)
    df_obory = df_final.groupby('Obor')[['Kapacita', 'Prihlaseni', 'Prijati']].sum().reset_index()
    df_obory['Previs'] = (df_obory['Prihlaseni'] / df_obory['Kapacita']).fillna(0)
    df_obory = df_obory[df_obory['Kapacita'] > 0] # Ošetření dělení nulou
    
    fig_obory = px.bar(
        df_obory.sort_values('Previs', ascending=False).head(15),
        x='Previs',
        y='Obor',
        orientation='h',
        title="Top 15 oborů s největším převisem poptávky",
        labels={'Previs': 'Převis (Počet přihlášek na 1 místo)'},
        text='Previs',
        color='Previs',
        color_continuous_scale='RdYlGn_r'
    )
    fig_obory.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    st.plotly_chart(fig_obory, use_container_width=True)

    # --- F) MEZIROČNÍ SROVNÁNÍ ---
    st.divider()
    st.subheader("5. Meziroční srovnání trendů (2024 vs 2025)")
    
    # Příprava dat pro srovnání (ignorujeme filtry roku, ale respektujeme kraj/město/obor)
    # Potřebujeme data za všechny roky, ale filtrovaná podle ostatních kritérií
    df_yoy_base = df_raw.copy()
    if selected_kraj:
        df_yoy_base = df_yoy_base[df_yoy_base['Kraj'].isin(selected_kraj)]
    if selected_mesto:
        df_yoy_base = df_yoy_base[df_yoy_base['Město'].isin(selected_mesto)]
    if selected_obor:
        df_yoy_base = df_yoy_base[df_yoy_base['Obor'].isin(selected_obor)]
    
    # Agregace po oborech a letech
    df_yoy = df_yoy_base.groupby(['Obor', 'Rok'])[['Prihlaseni', 'Prihlaseni_P1']].sum().reset_index()
    
    # Pivot pro snadné srovnání
    df_pivot = df_yoy.pivot(index='Obor', columns='Rok', values='Prihlaseni').fillna(0)
    
    # Zkontrolujeme, zda máme data pro oba roky 2024 a 2025
    if 2024 in df_pivot.columns and 2025 in df_pivot.columns:
        df_pivot['Zmena_Abs'] = df_pivot[2025] - df_pivot[2024]
        df_pivot['Zmena_Pct'] = ((df_pivot[2025] - df_pivot[2024]) / df_pivot[2024] * 100).fillna(0)
        
        # Top skokani (absolutní nárůst) - pouze kladné
        top_growers = df_pivot[df_pivot['Zmena_Abs'] > 0].sort_values('Zmena_Abs', ascending=False).head(5)
        # Top propadáky - pouze záporné
        top_losers = df_pivot[df_pivot['Zmena_Abs'] < 0].sort_values('Zmena_Abs', ascending=True).head(5)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🚀 Skokani roku (Absolutní nárůst zájmu)")
            st.dataframe(top_growers[[2024, 2025, 'Zmena_Abs', 'Zmena_Pct']].style.format({
                2024: "{:.0f}",
                2025: "{:.0f}",
                'Zmena_Abs': "{:+.0f}",
                'Zmena_Pct': "{:+.1f}%"
            }))
            
        with col2:
            st.markdown("#### 📉 Pokles zájmu")
            st.dataframe(top_losers[[2024, 2025, 'Zmena_Abs', 'Zmena_Pct']].style.format({
                2024: "{:.0f}",
                2025: "{:.0f}",
                'Zmena_Abs': "{:+.0f}",
                'Zmena_Pct': "{:+.1f}%"
            }))
        
        # Graf změny priorit (Dumbbell Plot)
        st.markdown("#### Změna v prioritách uchazečů (Podíl 1. priorit)")
        st.info("Graf ukazuje posun v tom, jak moc je obor pro uchazeče 'první volbou'. Šipka ukazuje změnu z roku 2024 na 2025.")
        
        df_prio_yoy = df_yoy_base.groupby(['Obor', 'Rok'])[['Prihlaseni', 'Prihlaseni_P1']].sum().reset_index()
        df_prio_yoy['Podil_P1'] = (df_prio_yoy['Prihlaseni_P1'] / df_prio_yoy['Prihlaseni'] * 100).fillna(0)
        
        # Pivot pro graf
        df_prio_pivot = df_prio_yoy.pivot(index='Obor', columns='Rok', values='Podil_P1').dropna()
        
        # Filtrujeme jen významné obory (podle celkového počtu přihlášek v 2025)
        # Musíme si spočítat celkové přihlášky pro filtrování
        df_total_apps = df_yoy_base[df_yoy_base['Rok'] == 2025].groupby('Obor')['Prihlaseni'].sum()
        top_obory = df_total_apps.sort_values(ascending=False).head(20).index
        
        df_plot = df_prio_pivot.loc[df_prio_pivot.index.intersection(top_obory)].copy()
        
        if not df_plot.empty and 2024 in df_plot.columns and 2025 in df_plot.columns:
            df_plot = df_plot.sort_values(by=2025, ascending=True) # Seřadíme podle roku 2025
            
            fig_dumbbell = go.Figure()
            
            # Čáry spojující body
            for obor, row in df_plot.iterrows():
                color = "green" if row[2025] >= row[2024] else "red"
                fig_dumbbell.add_trace(go.Scatter(
                    x=[row[2024], row[2025]],
                    y=[obor, obor],
                    mode="lines",
                    line=dict(color=color, width=2),
                    showlegend=False,
                    hoverinfo="skip"
                ))
                
            # Body pro rok 2024
            fig_dumbbell.add_trace(go.Scatter(
                x=df_plot[2024],
                y=df_plot.index,
                # mode="markers+text",
                mode="markers",
                name="2024",
                marker=dict(color="gray", size=8),
                text=df_plot[2024].apply(lambda x: f"{x:.1f}%"),
                textposition="middle left",
                hovertemplate="2024: %{x:.1f}%<extra></extra>"
            ))
            
            # Body pro rok 2025 (šipky by byly lepší, ale body stačí pro přehlednost)
            fig_dumbbell.add_trace(go.Scatter(
                x=df_plot[2025],
                y=df_plot.index,
                # mode="markers+text",
                mode="markers",
                name="2025",
                marker=dict(color="blue", size=10),
                text=df_plot[2025].apply(lambda x: f"{x:.1f}%"),
                textposition="middle right",
                hovertemplate="2025: %{x:.1f}%<extra></extra>"
            ))
            
            fig_dumbbell.update_layout(
                title="Posun v prioritách (Top 20 oborů dle zájmu)",
                xaxis_title="Podíl 1. priorit (%)",
                yaxis_title="Obor",
                height=600,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            st.plotly_chart(fig_dumbbell, use_container_width=True)
        else:
            st.warning("Nedostatek dat pro zobrazení grafu priorit (chybí data pro oba roky u top oborů).")
    
    else:
        st.info("Pro meziroční srovnání jsou potřeba data za roky 2024 i 2025. Zkontrolujte filtry.")

elif page == "Detail školy":
    st.header("Detail vybrané školy")
    
    # Výběr školy (pokud není vybrána nahoře)
    all_schools = sorted(df_filtered['Škola'].unique())
    
    # --- Persistence Logic ---
    if 'last_selected_school' not in st.session_state:
        st.session_state.last_selected_school = None

    # Try to find the last selected school in the new list
    default_index = 0
    if st.session_state.last_selected_school in all_schools:
        default_index = all_schools.index(st.session_state.last_selected_school)
    
    if all_schools:
        # Callback function to update session state immediately
        def update_selected_school():
            st.session_state.last_selected_school = st.session_state.school_selector
            
        detail_school = st.selectbox(
            "Vyber školu pro detailní pohled", 
            all_schools, 
            index=default_index,
            key="school_selector",
            on_change=update_selected_school
        )
        # Ensure session state is synced (in case of first load or other updates)
        st.session_state.last_selected_school = detail_school
    
        if detail_school:
            # Filtrujeme df_final, protože tam už jsou správně sečtené kapacity a přihlášky
            df_school_final = df_final[df_final['Škola'] == detail_school]
            
            # Klíčové metriky
            total_capacity = df_school_final['Kapacita'].sum()
            total_applicants = df_school_final['Prihlaseni'].sum()
            total_accepted = df_school_final['Prijati'].sum()
            
            # BENCHMARKING (Srovnání s trhem)
            # Získáme průměrné hodnoty pro stejné obory v celém datasetu (nebo kraji)
            school_obory = df_school_final['Obor'].unique()
            
            # Filtr pro benchmark: Stejný kraj (pokud je vybrán) a stejné obory
            df_benchmark = df_filtered[df_filtered['Obor'].isin(school_obory) & (df_filtered['Škola'] != detail_school)]
            
            avg_previs = 0
            avg_uspesnost = 0
            
            if not df_benchmark.empty:
                # Vážený průměr převisu (celkem přihlášky / celkem kapacita v benchmarku)
                bm_capacity = df_benchmark['Kapacita'].sum()
                bm_applicants = df_benchmark['Prihlaseni'].sum()
                bm_accepted = df_benchmark['Prijati'].sum()
                
                avg_previs = bm_applicants / bm_capacity if bm_capacity > 0 else 0
                avg_uspesnost = bm_accepted / bm_applicants * 100 if bm_applicants > 0 else 0
                
            # Metriky školy
            school_previs = total_applicants / total_capacity if total_capacity > 0 else 0
            school_uspesnost = total_accepted / total_applicants * 100 if total_applicants > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Celková kapacita", int(total_capacity))
            
            # Delta color: inverse (vyšší převis je pro školu 'dobře' z hlediska zájmu, ale pro žáka 'špatně'. 
            # Z pohledu školy (analýza úspěšnosti): Vyšší převis = Větší zájem = Zelená.
            col2.metric(
                "Počet přihlášek (Převis)", 
                f"{int(total_applicants)} ({school_previs:.2f}x)",
                delta=f"{school_previs - avg_previs:.2f} vs trh",
                delta_color="normal" # Zelená když je vyšší než trh (větší zájem)
            )
            
            col3.metric(
                "Úspěšnost přijetí", 
                f"{school_uspesnost:.1f} %",
                delta=f"{school_uspesnost - avg_uspesnost:.1f} % vs trh",
                delta_color="inverse" # Červená když je vyšší (lehčí se dostat = menší prestiž?) nebo naopak? 
                # Necháme inverse: Vyšší úspěšnost = Lehčí se dostat (méně výběrové).
            )
            
            if not df_benchmark.empty:
                st.caption(f"Benchmark: Průměr konkurence ve stejném regionu/oborech (Převis: {avg_previs:.2f}x, Úspěšnost: {avg_uspesnost:.1f}%)")
            
            # --- Příprava dat pro meziroční srovnání oborů ---
            prev_year = selected_year - 1
            # Získáme data pro minulý rok pro tuto školu
            df_prev = df_raw[(df_raw['Rok'] == prev_year) & (df_raw['Škola'] == detail_school)]
            
            # Defaultní sloupce
            display_cols = ['Obor', 'Kapacita', 'Prihlaseni', 'Prijati', 'Previs_Poptavky', 'Uspesnost_Pct']
            
            if not df_prev.empty:
                # Agregace za minulý rok (suma přihlášek)
                df_prev_grouped = df_prev.groupby('Obor')['Prihlaseni'].sum().reset_index().rename(columns={'Prihlaseni': 'Prihlaseni_Prev'})
                
                # Merge s aktuálními daty
                df_school_final = pd.merge(df_school_final, df_prev_grouped, on='Obor', how='left')
                
                # Výpočet změny
                df_school_final['Zmena_Abs'] = (df_school_final['Prihlaseni'] - df_school_final['Prihlaseni_Prev']).fillna(0)
                df_school_final['Zmena_Pct'] = ((df_school_final['Prihlaseni'] - df_school_final['Prihlaseni_Prev']) / df_school_final['Prihlaseni_Prev'] * 100).fillna(0)
                
                # Formátování pro zobrazení
                def format_change(row):
                    if pd.isna(row['Prihlaseni_Prev']):
                        return "Nový obor"
                    diff = int(row['Zmena_Abs'])
                    pct = row['Zmena_Pct']
                    
                    if diff > 0:
                        return f"↑ {diff} (+{pct:.1f}%)"
                    elif diff < 0:
                        return f"↓ {diff} ({pct:.1f}%)"
                    else:
                        return f"0 (0.0%)"
                
                df_school_final['Meziroční změna'] = df_school_final.apply(format_change, axis=1)
                
                # Vložíme sloupec Trend za Prihlaseni
                display_cols = ['Obor', 'Kapacita', 'Prihlaseni', 'Meziroční změna', 'Prijati', 'Previs_Poptavky', 'Uspesnost_Pct']
            else:
                st.info(f"ℹ️ Pro rok {selected_year} není k dispozici srovnání s předchozím rokem ({prev_year}).")

            # Tabulka oborů na škole
            st.markdown("#### Nabízené obory a jejich statistiky")
            
            # Styling funkce
            def color_trend(val):
                if isinstance(val, str):
                    if "↑" in val:
                        return 'color: green'
                    elif "↓" in val:
                        return 'color: red'
                return ''

            # Aplikace stylu
            df_display = df_school_final[display_cols].sort_values('Prihlaseni', ascending=False)
            
            styler = df_display.style
            if 'Meziroční změna' in df_display.columns:
                styler = styler.map(color_trend, subset=['Meziroční změna'])
            
            st.dataframe(
                styler,
                hide_index=True
            )
    
            # --- Detailní grafy pro školu ---
            st.markdown("#### Detailní analýza po oborech")
            col_g1, col_g2 = st.columns(2)
    
            with col_g1:
                # Graf priorit po oborech
                prio_map = {'Prihlaseni_P1': '1. Priorita', 'Prihlaseni_P2': '2. Priorita', 'Prihlaseni_P3': '3. Priorita'}
                df_school_prio = df_school_final.melt(
                    id_vars=['Obor'],
                    value_vars=['Prihlaseni_P1', 'Prihlaseni_P2', 'Prihlaseni_P3'],
                    var_name='Priorita', value_name='Pocet'
                )
                df_school_prio['Priorita'] = df_school_prio['Priorita'].map(prio_map)
                
                fig_school_prio = px.bar(
                    df_school_prio,
                    x='Pocet',
                    y='Obor',
                    color='Priorita',
                    orientation='h',
                    title="Struktura priorit dle oborů",
                    text_auto=True,
                    color_discrete_map={'1. Priorita': '#2ca02c', '2. Priorita': '#ff7f0e', '3. Priorita': '#1f77b4'}
                )
                fig_school_prio.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_school_prio, use_container_width=True)
    
            with col_g2:
                # Graf odmítnutí po oborech
                reject_map = {
                    'Duvod_Kapacita': 'Nedostačující kapacita', 
                    'Duvod_Podminky': 'Nesplnění podmínek', 
                    'Duvod_Vyssi_Priorita': 'Přijat na vyšší prioritu (Odliv)'
                }
                df_school_reject = df_school_final.melt(
                    id_vars=['Obor'],
                    value_vars=['Duvod_Kapacita', 'Duvod_Podminky', 'Duvod_Vyssi_Priorita'],
                    var_name='Duvod', value_name='Pocet'
                )
                df_school_reject['Duvod'] = df_school_reject['Duvod'].map(reject_map)
                
                fig_school_reject = px.bar(
                    df_school_reject,
                    x='Pocet',
                    y='Obor',
                    color='Duvod',
                    orientation='h',
                    title="Důvody nepřijetí dle oborů",
                    text_auto=True,
                    color_discrete_map={'Nedostačující kapacita': '#d62728', 'Nesplnění podmínek': '#7f7f7f', 'Přijat na vyšší prioritu (Odliv)': '#9467bd'}
                )
                fig_school_reject.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_school_reject, use_container_width=True)
    else:
        st.warning("Pro zobrazení detailu školy upravte filtry (žádná škola neodpovídá zadání).")

# --- Zobrazení surových dat (Společné) ---
with st.expander("Zobrazit zdrojová data pro aktuální výběr"):
    st.dataframe(df_final)
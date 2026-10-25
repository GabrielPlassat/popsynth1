"""
🗺️ Dashboard Mobilité — Population synthétique France
Source : Nemotron × EMP 2019

Lancement :
  streamlit run app.py

Prérequis :
  pip install streamlit pandas plotly gdown
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json, io, re, subprocess, sys
from pathlib import Path

# ── URL Google Drive ──────────────────────────────────────────────────────────
# personas_mobilite_v4.csv  (300 000 personas Nemotron × EMP 2019)
GDRIVE_FILE_ID = "1kRHuFOwMtKYQhAb8rgnD_1hF1YmD1Y9K"

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mobilité synthétique FR",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

PALETTE_MODES = {
    'voiture': '#e74c3c', 'tc': '#3498db', 'velo': '#2ecc71',
    'marche': '#f39c12', 'moto': '#8e44ad', 'covoiturage': '#9b59b6'
}

PARADIGME_LABELS = {
    'automobiliste_contraint':      '🚗 Automobiliste contraint·e',
    'motoriste_par_choix':          '🏎️ Motoriste par goût',
    'mobilite_engagee':             '🌿 Militant·e mobilité douce',
    'cycliste_quotidien':           '🚲 Cycliste du quotidien',
    'usager_tc_urbain':             '🚌 Usager·ère TC urbain·e',
    'sedentaire_local':             '🏡 Sédentaire ancré·e',
    'hypermobile_professionnel':    '✈️ Hypermobile professionnel·le',
    'multimodal_pragmatique':       '🔄 Multimodal·e pragmatique',
}

# ── Chargement données ────────────────────────────────────────────────────────
@st.cache_data(show_spinner="⏳ Téléchargement des données depuis Google Drive…")
def load_data():
    try:
        import gdown
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdown"], check=True)
        import gdown

    tmp_csv = "/tmp/personas_mobilite_v4.csv"
    try:
        gdown.download(id=GDRIVE_FILE_ID, output=tmp_csv, quiet=True)
        df = pd.read_csv(tmp_csv, low_memory=False)
    except Exception as e:
        st.error(f"❌ Erreur chargement CSV (ID={GDRIVE_FILE_ID}) : {e}")
        st.stop()
    return df

df_full = load_data()

# ── Colonnes calculées ────────────────────────────────────────────────────────
if 'classe_age' not in df_full.columns:
    bins   = [0, 17, 24, 34, 44, 54, 64, 74, 120]
    labels = ['<18','18-24','25-34','35-44','45-54','55-64','65-74','75+']
    df_full['classe_age'] = pd.cut(df_full['age'], bins=bins, labels=labels, right=True).astype(str)

# Colonne dépendance auto (compatible v3 et v4)
SCORE_COL = 'score_dependance_auto' if 'score_dependance_auto' in df_full.columns else 'score_dep'

if 'dep_cat' not in df_full.columns and SCORE_COL in df_full.columns:
    def dep_cat(s):
        try: s = float(s)
        except: return 'indéterminé'
        if s < 30: return 'faible'
        if s < 55: return 'modéré'
        if s < 75: return 'élevé'
        return 'très élevé'
    df_full['dep_cat'] = df_full[SCORE_COL].apply(dep_cat)

# Colonne covoiturage (compatible v3 et v4)
PCT_COV_COL = 'pct_covoiturage' if 'pct_covoiturage' in df_full.columns else 'pct_cov'

# ── Sidebar filtres ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filtres")
    sel_terr = st.multiselect(
        "Territoire",
        sorted(df_full['territoire'].dropna().unique().tolist()),
        default=sorted(df_full['territoire'].dropna().unique().tolist())
    )
    sel_csp = st.multiselect(
        "CSP",
        sorted(df_full['csp'].dropna().unique().tolist()),
        default=sorted(df_full['csp'].dropna().unique().tolist())
    )
    age_range = st.slider("Tranche d'âge", 0, 99, (18, 75))

    if 'paradigme_mobilite' in df_full.columns:
        all_paradigmes = sorted(df_full['paradigme_mobilite'].dropna().unique().tolist())
        sel_paradigme = st.multiselect(
            "Paradigme mobilité",
            all_paradigmes,
            default=all_paradigmes
        )
    else:
        sel_paradigme = []

    st.markdown("---")
    st.caption(f"Dataset total : **{len(df_full):,}** personas")

# Appliquer filtres
mask = (
    df_full['territoire'].isin(sel_terr) &
    df_full['csp'].isin(sel_csp) &
    df_full['age'].between(age_range[0], age_range[1])
)
if sel_paradigme and 'paradigme_mobilite' in df_full.columns:
    mask = mask & df_full['paradigme_mobilite'].isin(sel_paradigme)

df = df_full[mask].copy()
n  = len(df)

st.sidebar.caption(f"Population filtrée : **{n:,}** personas")

if n == 0:
    st.warning("⚠️ Aucune persona avec ces filtres.")
    st.stop()

# ── Onglets ──────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "👥 Population",
    "🚗 Mobilité quotidienne",
    "🧭 Paradigmes & Profils",
    "💼 Véhicules & Budget",
    "🌍 Activités & Voyages",
    "🎯 Politiques publiques",
    "💬 Enquêtes IA",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — Population
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("👥 Portrait de la population")

    c1, c2, c3, c4 = st.columns(4)
    sex_col = 'sex' if 'sex' in df.columns else 'gender'
    if sex_col in df.columns:
        s = df[sex_col].astype(str).str.strip().str.lower()
        pct_f = s.isin(['femme','f','female','woman','2']).mean() * 100
        label_genre = f"{pct_f:.1f}%"
    else:
        label_genre = "—"

    c1.metric("Personas", f"{n:,}")
    c2.metric("Âge moyen", f"{df['age'].mean():.1f} ans")
    c3.metric("% femmes", label_genre)
    c4.metric("Km/j moyen", f"{df['km_jour'].mean():.1f} km" if 'km_jour' in df.columns else "—")

    col1, col2 = st.columns(2)
    with col1:
        color_col = sex_col if sex_col in df.columns else 'csp'
        fig = px.histogram(df, x='age', color=color_col, nbins=30,
                           title="Distribution des âges par genre",
                           color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(bargap=0.05, legend_title="Genre")
        st.plotly_chart(fig, width="stretch")

    with col2:
        csp_counts = df['csp'].value_counts().reset_index()
        csp_counts.columns = ['csp', 'n']
        fig = px.pie(csp_counts, values='n', names='csp', title="Répartition CSP",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig, width="stretch")

    col3, col4 = st.columns(2)
    with col3:
        terr_counts = df['territoire'].value_counts().reset_index()
        terr_counts.columns = ['territoire', 'n']
        fig = px.bar(terr_counts, x='territoire', y='n', title="Distribution territoriale",
                     color='territoire', color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, width="stretch")

    with col4:
        age_terr = df.groupby(['classe_age', 'territoire']).size().reset_index(name='n')
        fig = px.bar(age_terr, x='classe_age', y='n', color='territoire',
                     title="Âge × Territoire",
                     color_discrete_sequence=px.colors.qualitative.Set1)
        st.plotly_chart(fig, width="stretch")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — Mobilité quotidienne
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("🚗 Mobilité quotidienne")

    c1, c2, c3, c4, c5 = st.columns(5)
    mode_cols = [
        (c1, 'pct_voiture', '🚗'), (c2, 'pct_tc', '🚌'),
        (c3, 'pct_velo', '🚲'), (c4, 'pct_marche', '🚶'),
        (c5, PCT_COV_COL, '🤝'),
    ]
    mode_labels = {
        'pct_voiture': 'Voiture', 'pct_tc': 'TC', 'pct_velo': 'Vélo',
        'pct_marche': 'Marche', 'pct_covoiturage': 'Covoit.', 'pct_cov': 'Covoit.',
    }
    for col, mode, icon in mode_cols:
        val = df[mode].mean() if mode in df.columns else 0
        label = mode_labels.get(mode, mode.replace('pct_', ''))
        col.metric(f"{icon} {label}", f"{val:.1f}%")

    col1, col2 = st.columns(2)
    with col1:
        modes_moy = {}
        for m, lbl, color in [
            ('pct_voiture', 'Voiture', '#e74c3c'),
            ('pct_tc', 'TC', '#3498db'),
            ('pct_marche', 'Marche', '#f39c12'),
            ('pct_velo', 'Vélo', '#2ecc71'),
            (PCT_COV_COL, 'Covoiturage', '#9b59b6'),
        ]:
            if m in df.columns:
                modes_moy[lbl] = (df[m].mean(), color)

        fig = go.Figure(go.Bar(
            x=[v for v, _ in modes_moy.values()],
            y=list(modes_moy.keys()),
            orientation='h',
            marker_color=[c for _, c in modes_moy.values()]
        ))
        fig.update_layout(title="Parts modales moyennes (%)", xaxis_title="%")
        st.plotly_chart(fig, width="stretch")

    with col2:
        if 'km_jour' in df.columns:
            km_csp = df.groupby('csp')['km_jour'].mean().reset_index()
            km_csp.columns = ['csp', 'km_jour']
            km_csp = km_csp.sort_values('km_jour', ascending=False)
            fig = px.bar(km_csp, x='csp', y='km_jour', title="Km/jour par CSP",
                         color='csp', color_discrete_sequence=px.colors.qualitative.Bold)
            st.plotly_chart(fig, width="stretch")

    # Parts modales par territoire
    modes = [m for m in ['pct_voiture', 'pct_tc', 'pct_velo', 'pct_marche'] if m in df.columns]
    terr_modes = df.groupby('territoire')[modes].mean().reset_index()
    terr_modes_long = terr_modes.melt('territoire', var_name='mode', value_name='pct')
    fig = px.bar(terr_modes_long, x='territoire', y='pct', color='mode',
                 title="Parts modales par territoire", barmode='group',
                 color_discrete_map={
                     'pct_voiture': '#e74c3c', 'pct_tc': '#3498db',
                     'pct_velo': '#2ecc71', 'pct_marche': '#f39c12'
                 })
    st.plotly_chart(fig, width="stretch")

    # Télétravail
    if 'jours_teletravail_sem' in df.columns:
        st.subheader("🏠 Télétravail")
        col1, col2 = st.columns(2)
        with col1:
            tel_csp = df.groupby('csp')['jours_teletravail_sem'].mean().reset_index()
            tel_csp.columns = ['csp', 'jours']
            fig = px.bar(tel_csp.sort_values('jours', ascending=False),
                         x='csp', y='jours', title="Jours de télétravail/semaine par CSP",
                         color='csp', color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, width="stretch")
        with col2:
            tel_dist = df['jours_teletravail_sem'].value_counts().reset_index()
            tel_dist.columns = ['jours', 'n']
            tel_dist = tel_dist.sort_values('jours')
            fig = px.bar(tel_dist, x='jours', y='n',
                         title="Distribution des jours de télétravail",
                         color_discrete_sequence=['#3498db'])
            st.plotly_chart(fig, width="stretch")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — Paradigmes & Profils
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("🧭 Paradigmes de mobilité & Profils narratifs")

    if 'paradigme_mobilite' not in df.columns:
        st.info("La colonne `paradigme_mobilite` n'est pas présente dans ce CSV.")
    else:
        # Distribution des paradigmes
        paradigme_counts = df['paradigme_mobilite'].value_counts().reset_index()
        paradigme_counts.columns = ['paradigme', 'n']
        paradigme_counts['label'] = paradigme_counts['paradigme'].map(
            lambda x: PARADIGME_LABELS.get(x, x)
        )

        col1, col2 = st.columns([3, 2])
        with col1:
            fig = px.bar(
                paradigme_counts.sort_values('n', ascending=True),
                x='n', y='label', orientation='h',
                title="Distribution des paradigmes de mobilité",
                color='paradigme',
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig.update_layout(showlegend=False, yaxis_title="")
            st.plotly_chart(fig, width="stretch")
        with col2:
            fig = px.pie(paradigme_counts, values='n', names='label',
                         title="Part de chaque paradigme",
                         color_discrete_sequence=px.colors.qualitative.Bold)
            fig.update_traces(textposition='inside', textinfo='percent')
            st.plotly_chart(fig, width="stretch")

        # Paradigme × territoire
        st.subheader("Paradigmes × Territoire")
        par_terr = df.groupby(['territoire', 'paradigme_mobilite']).size().reset_index(name='n')
        par_terr['label'] = par_terr['paradigme_mobilite'].map(
            lambda x: PARADIGME_LABELS.get(x, x)
        )
        fig = px.bar(par_terr, x='territoire', y='n', color='label',
                     title="Composition des paradigmes par territoire",
                     barmode='stack',
                     color_discrete_sequence=px.colors.qualitative.Bold)
        fig.update_layout(legend_title="Paradigme")
        st.plotly_chart(fig, width="stretch")

        # Paradigme × CSP
        par_csp = df.groupby(['csp', 'paradigme_mobilite']).size().reset_index(name='n')
        par_csp['label'] = par_csp['paradigme_mobilite'].map(
            lambda x: PARADIGME_LABELS.get(x, x)
        )
        fig = px.bar(par_csp, x='csp', y='n', color='label',
                     title="Composition des paradigmes par CSP",
                     barmode='stack',
                     color_discrete_sequence=px.colors.qualitative.Bold)
        fig.update_layout(legend_title="Paradigme")
        st.plotly_chart(fig, width="stretch")

    # Profils narratifs
    if 'mobility_persona' in df.columns:
        st.subheader("💬 Exemples de profils narratifs (mobility_persona)")

        col_filter1, col_filter2, col_filter3 = st.columns(3)
        with col_filter1:
            filter_terr = st.selectbox("Territoire", ['Tous'] + sorted(df['territoire'].unique().tolist()), key='pf_terr')
        with col_filter2:
            filter_csp = st.selectbox("CSP", ['Toutes'] + sorted(df['csp'].unique().tolist()), key='pf_csp')
        with col_filter3:
            if 'paradigme_mobilite' in df.columns:
                filter_par = st.selectbox("Paradigme", ['Tous'] + sorted(df['paradigme_mobilite'].dropna().unique().tolist()), key='pf_par')
            else:
                filter_par = 'Tous'

        df_pf = df.copy()
        if filter_terr != 'Tous': df_pf = df_pf[df_pf['territoire'] == filter_terr]
        if filter_csp  != 'Toutes': df_pf = df_pf[df_pf['csp'] == filter_csp]
        if filter_par  != 'Tous' and 'paradigme_mobilite' in df_pf.columns:
            df_pf = df_pf[df_pf['paradigme_mobilite'] == filter_par]

        n_pf = len(df_pf)
        st.caption(f"{n_pf:,} personas correspondent à ces critères")

        n_show = st.slider("Nombre de profils à afficher", 1, 10, 3)
        if n_pf > 0:
            for _, row in df_pf.sample(min(n_show, n_pf), random_state=42).iterrows():
                sex_v = row.get('sex', '?')
                age_v = row.get('age', '?')
                csp_v = row.get('csp', '?')
                terr_v = row.get('territoire', '?')
                par_v = PARADIGME_LABELS.get(row.get('paradigme_mobilite', ''), row.get('paradigme_mobilite', '?'))
                with st.expander(f"**{sex_v}, {age_v} ans — {csp_v} / {terr_v}** · {par_v}"):
                    st.write(row['mobility_persona'])
        else:
            st.warning("Aucun profil avec ces critères.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — Véhicules & Budget
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("💼 Inventaire véhicules, Budget transport & Compétences")

    # KPIs véhicules
    veh_cols = {
        'nb_voitures': ('🚗', 'Voitures/ménage'),
        'nb_velos':    ('🚲', 'Vélos/ménage'),
        'nb_velos_elec': ('⚡', 'VAE/ménage'),
        'nb_motos':    ('🏍️', 'Motos/ménage'),
        'nb_camping_car': ('🏕️', 'Camping-car/ménage'),
    }
    cols_kpi = st.columns(len(veh_cols))
    for (col_name, (icon, label)), col_ui in zip(veh_cols.items(), cols_kpi):
        val = df[col_name].mean() if col_name in df.columns else None
        col_ui.metric(f"{icon} {label}", f"{val:.2f}" if val is not None else "—")

    # Inventaire par territoire
    veh_avail = [c for c in veh_cols if c in df.columns]
    if veh_avail:
        col1, col2 = st.columns(2)
        with col1:
            veh_terr = df.groupby('territoire')[veh_avail].mean().reset_index()
            veh_terr_long = veh_terr.melt('territoire', var_name='vehicule', value_name='moy')
            veh_terr_long['vehicule'] = veh_terr_long['vehicule'].map(
                lambda x: veh_cols.get(x, (None, x))[1]
            )
            fig = px.bar(veh_terr_long, x='territoire', y='moy', color='vehicule',
                         title="Inventaire véhicules moyen par territoire",
                         barmode='group',
                         color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig, width="stretch")

        with col2:
            veh_csp = df.groupby('csp')[['nb_voitures', 'nb_velos']].mean().reset_index()
            veh_csp_long = veh_csp.melt('csp', var_name='vehicule', value_name='moy')
            veh_csp_long['vehicule'] = veh_csp_long['vehicule'].map(
                lambda x: veh_cols.get(x, (None, x))[1]
            )
            fig = px.bar(veh_csp_long, x='csp', y='moy', color='vehicule',
                         title="Voitures et vélos moyens par CSP",
                         barmode='group',
                         color_discrete_sequence=['#e74c3c', '#2ecc71'])
            st.plotly_chart(fig, width="stretch")

    # Budget transport
    st.subheader("💶 Budget transport mensuel")
    budget_cols = {
        'budget_transport_mois_eur': 'Budget total',
        'budget_carburant_mois_eur': 'Carburant',
        'budget_tc_mois_eur':        'TC / abonnements',
    }
    budget_avail = [c for c in budget_cols if c in df.columns]
    if budget_avail:
        bc1, bc2, bc3 = st.columns(3)
        for col_ui, col_name in zip([bc1, bc2, bc3], budget_avail):
            col_ui.metric(budget_cols[col_name],
                          f"{df[col_name].mean():.0f} €/mois")

        col1, col2 = st.columns(2)
        with col1:
            bud_csp = df.groupby('csp')[budget_avail].mean().reset_index()
            bud_csp_long = bud_csp.melt('csp', var_name='poste', value_name='eur')
            bud_csp_long['poste'] = bud_csp_long['poste'].map(budget_cols)
            fig = px.bar(bud_csp_long, x='csp', y='eur', color='poste',
                         title="Budget transport par CSP (€/mois)",
                         barmode='stack',
                         color_discrete_sequence=['#e74c3c', '#f39c12', '#3498db'])
            st.plotly_chart(fig, width="stretch")

        with col2:
            bud_terr = df.groupby('territoire')[budget_avail].mean().reset_index()
            bud_terr_long = bud_terr.melt('territoire', var_name='poste', value_name='eur')
            bud_terr_long['poste'] = bud_terr_long['poste'].map(budget_cols)
            fig = px.bar(bud_terr_long, x='territoire', y='eur', color='poste',
                         title="Budget transport par territoire (€/mois)",
                         barmode='stack',
                         color_discrete_sequence=['#e74c3c', '#f39c12', '#3498db'])
            st.plotly_chart(fig, width="stretch")

    # Compétences et permis
    st.subheader("🪪 Permis & Compétences")
    comp_cols = {
        'a_permis_voiture': '% permis voiture',
        'a_permis_moto':    '% permis moto',
        'utilise_autopartage': '% autopartage',
        'utilise_velopartage': '% vélopartage',
    }
    comp_avail = [c for c in comp_cols if c in df.columns]
    if comp_avail:
        cols_comp = st.columns(len(comp_avail))
        for col_ui, col_name in zip(cols_comp, comp_avail):
            val = df[col_name].mean() * 100
            col_ui.metric(comp_cols[col_name], f"{val:.1f}%")

    if 'competence_tc_1_5' in df.columns:
        comp_dist = df['competence_tc_1_5'].value_counts().sort_index().reset_index()
        comp_dist.columns = ['score', 'n']
        fig = px.bar(comp_dist, x='score', y='n',
                     title="Compétence TC (1 = débutant → 5 = expert)",
                     labels={'score': 'Score /5', 'n': 'Nb personas'},
                     color_discrete_sequence=['#3498db'])
        st.plotly_chart(fig, width="stretch")


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — Activités & Voyages
# ════════════════════════════════════════════════════════════════════════════
with tab5:
    st.header("🌍 Activités de loisir & Voyages")

    # Activités sportives
    st.subheader("🏃 Mobilité sportive")
    if 'km_sport_semaine' in df.columns:
        c1, c2, c3 = st.columns(3)
        c1.metric("Km sport/semaine moyen", f"{df['km_sport_semaine'].mean():.0f} km")
        c2.metric("% pratiquant sport", f"{(df['km_sport_semaine'] > 0).mean()*100:.1f}%")
        if 'pct_voiture_sport' in df.columns:
            c3.metric("% voiture pour sport", f"{df['pct_voiture_sport'].mean():.0f}%")

        col1, col2 = st.columns(2)
        with col1:
            sport_csp = df.groupby('csp')['km_sport_semaine'].mean().reset_index()
            fig = px.bar(sport_csp.sort_values('km_sport_semaine', ascending=False),
                         x='csp', y='km_sport_semaine',
                         title="Distance sportive hebdomadaire par CSP (km)",
                         color='csp', color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig, width="stretch")

        with col2:
            # Distribution des km sport
            sample_sport = df[df['km_sport_semaine'] > 0]['km_sport_semaine']
            fig = px.histogram(sample_sport, nbins=25,
                               title="Distribution km sport/semaine (pratiquants uniquement)",
                               color_discrete_sequence=['#2ecc71'])
            st.plotly_chart(fig, width="stretch")

    # Activités culturelles
    if 'km_culture_mois' in df.columns:
        st.subheader("🎭 Mobilité culturelle")
        col1, col2 = st.columns(2)
        with col1:
            cult_csp = df.groupby('csp')['km_culture_mois'].mean().reset_index()
            fig = px.bar(cult_csp.sort_values('km_culture_mois', ascending=False),
                         x='csp', y='km_culture_mois',
                         title="Km/mois pour les activités culturelles par CSP",
                         color='csp', color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, width="stretch")

        with col2:
            cult_terr = df.groupby('territoire')['km_culture_mois'].mean().reset_index()
            fig = px.bar(cult_terr, x='territoire', y='km_culture_mois',
                         title="Km/mois culturel par territoire",
                         color='territoire', color_discrete_sequence=px.colors.qualitative.Bold)
            st.plotly_chart(fig, width="stretch")

    # Voyages & Vacances
    if 'km_vacances_an' in df.columns:
        st.subheader("✈️ Voyages et vacances")

        voy_c1, voy_c2, voy_c3 = st.columns(3)
        voy_c1.metric("Km vacances/an moyen", f"{df['km_vacances_an'].mean():,.0f} km")
        if 'pct_avion_vac' in df.columns:
            voy_c2.metric("Part avion vacances", f"{df['pct_avion_vac'].mean():.1f}%")
        if 'pct_train_vac' in df.columns:
            voy_c3.metric("Part train vacances", f"{df['pct_train_vac'].mean():.1f}%")

        col1, col2 = st.columns(2)
        with col1:
            voy_csp = df.groupby('csp')['km_vacances_an'].mean().reset_index()
            fig = px.bar(voy_csp.sort_values('km_vacances_an', ascending=False),
                         x='csp', y='km_vacances_an',
                         title="Km vacances/an par CSP",
                         color='csp', color_discrete_sequence=px.colors.qualitative.Set1)
            st.plotly_chart(fig, width="stretch")

        with col2:
            # Modes de transport vacances
            vac_mode_cols = {
                'pct_avion_vac': ('✈️ Avion', '#5dade2'),
                'pct_train_vac': ('🚆 Train', '#2ecc71'),
                'pct_vp_vac':    ('🚗 Voiture', '#e74c3c'),
            }
            vac_mode_avail = {k: v for k, v in vac_mode_cols.items() if k in df.columns}
            if vac_mode_avail:
                vac_moy = {label: df[col].mean() for col, (label, _) in vac_mode_avail.items()}
                fig = go.Figure(go.Pie(
                    labels=list(vac_moy.keys()),
                    values=list(vac_moy.values()),
                    marker_colors=[c for _, (_, c) in vac_mode_avail.items()],
                ))
                fig.update_layout(title="Modes de transport dominants pour les vacances (%)")
                st.plotly_chart(fig, width="stretch")

        # Km vacances × paradigme
        if 'paradigme_mobilite' in df.columns:
            voy_par = df.groupby('paradigme_mobilite')['km_vacances_an'].mean().reset_index()
            voy_par['label'] = voy_par['paradigme_mobilite'].map(
                lambda x: PARADIGME_LABELS.get(x, x)
            )
            fig = px.bar(voy_par.sort_values('km_vacances_an', ascending=False),
                         x='label', y='km_vacances_an',
                         title="Km vacances/an par paradigme de mobilité",
                         color='label', color_discrete_sequence=px.colors.qualitative.Bold)
            fig.update_layout(showlegend=False, xaxis_tickangle=-30)
            st.plotly_chart(fig, width="stretch")


# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — Politiques publiques
# ════════════════════════════════════════════════════════════════════════════
with tab6:
    st.header("🎯 Segments cibles pour politiques de mobilité")

    # Dépendance & CO2
    if SCORE_COL in df.columns:
        st.subheader("🌱 Dépendance automobile & CO₂")
        c1, c2, c3 = st.columns(3)
        c1.metric("Score dépendance moyen", f"{df[SCORE_COL].mean():.1f}/100")
        if 'co2_kg_an' in df.columns:
            c2.metric("CO₂ mobilité moyen/an", f"{df['co2_kg_an'].mean():.0f} kg")
            c3.metric("% très dépendants (>75)", f"{(df[SCORE_COL]>75).mean()*100:.1f}%")

        col1, col2 = st.columns(2)
        with col1:
            fig = px.histogram(df, x=SCORE_COL, nbins=30,
                               title="Distribution du score de dépendance auto",
                               color_discrete_sequence=['#e74c3c'])
            fig.add_vline(x=df[SCORE_COL].mean(), line_dash="dash", line_color="black",
                          annotation_text=f"Moy. {df[SCORE_COL].mean():.1f}")
            st.plotly_chart(fig, width="stretch")

        with col2:
            if 'co2_kg_an' in df.columns:
                co2_terr = df.groupby('territoire')['co2_kg_an'].mean().reset_index()
                fig = px.bar(co2_terr, x='territoire', y='co2_kg_an',
                             title="CO₂ moyen par territoire (kg/an)",
                             color='territoire',
                             color_discrete_sequence=px.colors.sequential.Reds)
                st.plotly_chart(fig, width="stretch")

        if 'co2_kg_an' in df.columns:
            sample = df.sample(min(5000, n), random_state=42)
            fig = px.scatter(sample, x=SCORE_COL, y='co2_kg_an', color='territoire',
                             opacity=0.4, title="Dépendance auto vs Empreinte CO₂",
                             labels={SCORE_COL: 'Score dépendance', 'co2_kg_an': 'CO₂ kg/an'},
                             color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig, width="stretch")

    # Segments cibles
    st.subheader("Segments à potentiel de report modal")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🚲 Potentiel report vers le vélo")
        mask_velo = (
            (df[SCORE_COL] < 45) &
            df['territoire'].isin(['urbain_moyen', 'urbain_dense', 'periurbain']) &
            (df['km_jour'] < 20)
        ) if SCORE_COL in df.columns and 'km_jour' in df.columns else pd.Series(False, index=df.index)
        n_velo = mask_velo.sum()
        st.metric("Personas ciblées", f"{n_velo:,} ({n_velo/n*100:.1f}%)")
        if n_velo > 0:
            fig = px.bar(df[mask_velo]['csp'].value_counts().reset_index(),
                         x='csp', y='count', title="CSP des personas pro-vélo",
                         color_discrete_sequence=['#2ecc71'])
            st.plotly_chart(fig, width="stretch")

    with col2:
        st.markdown("#### 🚌 Potentiel report vers les TC")
        mask_tc = (
            (df['pct_voiture'] > 50) &
            df['territoire'].isin(['periurbain', 'urbain_moyen'])
        ) if 'pct_voiture' in df.columns else pd.Series(False, index=df.index)
        n_tc = mask_tc.sum()
        st.metric("Personas ciblées", f"{n_tc:,} ({n_tc/n*100:.1f}%)")
        if n_tc > 0:
            fig = px.bar(df[mask_tc]['csp'].value_counts().reset_index(),
                         x='csp', y='count', title="CSP des personas pro-TC",
                         color_discrete_sequence=['#3498db'])
            st.plotly_chart(fig, width="stretch")

    st.markdown("#### 🤝 Potentiel covoiturage longue distance")
    mask_cov = (
        (df['km_jour'] > 15) &
        df['territoire'].isin(['rural', 'periurbain']) &
        (df['pct_voiture'] > 60)
    ) if 'km_jour' in df.columns and 'pct_voiture' in df.columns else pd.Series(False, index=df.index)
    n_cov = mask_cov.sum()
    st.metric("Personas ciblées", f"{n_cov:,} ({n_cov/n*100:.1f}%)")

    # Tableau de bord paradigmes × territoire
    if 'paradigme_mobilite' in df.columns:
        st.subheader("Vue croisée : Paradigme × CO₂ × Dépendance")
        if SCORE_COL in df.columns and 'co2_kg_an' in df.columns:
            par_summary = df.groupby('paradigme_mobilite').agg(
                n=('paradigme_mobilite', 'count'),
                dep_moy=(SCORE_COL, 'mean'),
                co2_moy=('co2_kg_an', 'mean'),
            ).reset_index()
            par_summary['label'] = par_summary['paradigme_mobilite'].map(
                lambda x: PARADIGME_LABELS.get(x, x)
            )
            par_summary = par_summary.sort_values('dep_moy', ascending=False)

            fig = px.scatter(par_summary, x='dep_moy', y='co2_moy',
                             size='n', color='label', text='label',
                             title="Paradigmes : Dépendance auto vs CO₂",
                             labels={'dep_moy': 'Score dépendance moyen', 'co2_moy': 'CO₂ moyen kg/an'},
                             color_discrete_sequence=px.colors.qualitative.Bold)
            fig.update_traces(textposition='top center')
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, width="stretch")


# ════════════════════════════════════════════════════════════════════════════
# TAB 7 — Enquêtes IA
# ════════════════════════════════════════════════════════════════════════════
with tab7:
    st.header("💬 Enquêtes & Sondages IA sur les personas")

    st.info("🤖 Simulation des réponses de personas synthétiques à des questions de mobilité, basée sur leurs profils statistiques EMP 2019 et leurs paradigmes de mobilité.")

    question = st.text_area(
        "Votre question :",
        value="Si une piste cyclable sécurisée était créée sur votre trajet domicile-travail, seriez-vous prêt·e à utiliser le vélo ?",
        height=80
    )

    col_q1, col_q2, col_q3 = st.columns(3)
    with col_q1:
        terr_q = st.selectbox("Territoire ciblé", ['Tous'] + sorted(df['territoire'].unique().tolist()))
    with col_q2:
        csp_q  = st.selectbox("CSP ciblée", ['Toutes'] + sorted(df['csp'].unique().tolist()))
    with col_q3:
        if 'paradigme_mobilite' in df.columns:
            par_q = st.selectbox("Paradigme ciblé",
                                  ['Tous'] + sorted(df['paradigme_mobilite'].dropna().unique().tolist()))
        else:
            par_q = 'Tous'

    if st.button("🚀 Simuler les réponses"):
        df_q = df.copy()
        if terr_q != 'Tous': df_q = df_q[df_q['territoire'] == terr_q]
        if csp_q  != 'Toutes': df_q = df_q[df_q['csp'] == csp_q]
        if par_q  != 'Tous' and 'paradigme_mobilite' in df_q.columns:
            df_q = df_q[df_q['paradigme_mobilite'] == par_q]

        n_q = len(df_q)
        st.write(f"Échantillon : **{n_q:,}** personas")

        if n_q == 0:
            st.warning("Aucune persona avec ces critères.")
        else:
            pct_velo_moy  = df_q['pct_velo'].mean() / 100 if 'pct_velo' in df_q.columns else 0.03
            score_dep_moy = df_q[SCORE_COL].mean() if SCORE_COL in df_q.columns else 50

            # Probabilité d'acceptation selon paradigme dominant
            par_dominant = df_q['paradigme_mobilite'].mode()[0] if 'paradigme_mobilite' in df_q.columns else None
            bonus_par = {
                'cycliste_quotidien': 0.25,
                'mobilite_engagee': 0.20,
                'multimodal_pragmatique': 0.10,
                'usager_tc_urbain': 0.05,
                'sedentaire_local': -0.05,
                'automobiliste_contraint': -0.10,
                'motoriste_par_choix': -0.20,
                'hypermobile_professionnel': -0.05,
            }

            p_oui = min(0.85, max(0.05,
                0.25
                + pct_velo_moy * 1.5
                - (score_dep_moy - 50) * 0.005
                + (0.1 if terr_q in ['urbain_moyen', 'urbain_dense'] else 0)
                + bonus_par.get(par_dominant or '', 0)
            ))
            p_non      = (1 - p_oui) * 0.65
            p_peut     = (1 - p_oui) * 0.25
            p_sais_pas = max(0, 1 - p_oui - p_non - p_peut)

            r = {
                'Oui, certainement':  round(p_oui * 100, 1),
                'Non, peu probable':  round(p_non * 100, 1),
                'Peut-être':          round(p_peut * 100, 1),
                'Ne sait pas':        round(p_sais_pas * 100, 1),
            }

            c1, c2 = st.columns(2)
            with c1:
                for rep, pct in r.items():
                    st.progress(int(pct), text=f"{rep} : {pct:.1f}%")
                if par_dominant:
                    st.caption(f"Paradigme dominant : **{PARADIGME_LABELS.get(par_dominant, par_dominant)}**")
            with c2:
                fig = px.pie(values=list(r.values()), names=list(r.keys()),
                             title=f"Réponses simulées ({n_q:,} personas)",
                             color_discrete_sequence=['#2ecc71', '#e74c3c', '#f39c12', '#95a5a6'])
                st.plotly_chart(fig, width="stretch")

            st.caption("⚠️ Simulation probabiliste basée sur les profils EMP 2019 et les paradigmes de mobilité. Résultats indicatifs.")

            # Afficher quelques profils texte si disponibles
            if 'mobility_persona' in df_q.columns:
                with st.expander("📋 Voir des exemples de profils dans ce segment"):
                    n_ex = min(3, n_q)
                    for _, row in df_q.sample(n_ex, random_state=7).iterrows():
                        st.markdown(f"**{row.get('sex','?')}, {row.get('age','?')} ans — {row.get('csp','?')} / {row.get('territoire','?')}**")
                        st.write(row['mobility_persona'])
                        st.divider()


# ── Pied de page ─────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Sources : EMP 2019 (SDES/INSEE) · Population synthétique NVIDIA Nemotron-Personas-France "
    "· Enrichissement et traitement Claude AI — personas_mobilite_v4.csv"
)

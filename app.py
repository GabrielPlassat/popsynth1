"""
🗺️ Dashboard Mobilité — Population synthétique France
Source : Nemotron × EMP 2019

Lancement :
  streamlit run dashboard_mobilite.py

Prérequis :
  pip install streamlit pandas plotly gdown
  Renseignez les URLs Google Drive ci-dessous.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json, io, re, subprocess, sys
from pathlib import Path

# ── URLs Google Drive ─────────────────────────────────────────────────────────
# Partagez chaque fichier en "Tout le monde avec le lien" puis collez l'URL ici
GDRIVE_CSV  = "https://drive.google.com/file/d/1sKz65OjE7SZHkb4cASU6CcdelZj4TK8v/view?usp=sharing"
GDRIVE_JSON = "https://drive.google.com/file/d/1AWBcbVQvb1sqcBGetqcc1434yF2bEBB2/view?usp=sharing"

def gdrive_id(url):
    m = re.search(r'/d/([^/]+)', url)
    return m.group(1) if m else None

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mobilité synthétique FR",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

PALETTE = {
    'voiture': '#e74c3c', 'tc': '#3498db', 'velo': '#2ecc71',
    'marche': '#f39c12', 'covoiturage': '#9b59b6'
}

# ── Chargement données ────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Chargement des données depuis Google Drive…")
def load_data():
    try:
        import gdown
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdown"], check=True)
        import gdown

    # CSV
    csv_id = gdrive_id(GDRIVE_CSV)
    if not csv_id:
        st.error("❌ GDRIVE_CSV invalide — collez l'URL de partage complète.")
        st.stop()
    try:
        tmp_csv = "/tmp/personas_mobilite.csv"
        gdown.download(id=csv_id, output=tmp_csv, quiet=True, fuzzy=True)
        df = pd.read_csv(tmp_csv, low_memory=False)
    except Exception as e:
        st.error(f"❌ Erreur chargement CSV : {e}")
        st.stop()

    # JSON stats (optionnel)
    stats = {}
    json_id = gdrive_id(GDRIVE_JSON)
    if json_id:
        try:
            tmp_json = "/tmp/stats_mobilite.json"
            gdown.download(id=json_id, output=tmp_json, quiet=True, fuzzy=True)
            with open(tmp_json) as f:
                stats = json.load(f)
        except Exception:
            pass

    return df, stats

df_full, STATS = load_data()

# ── Sidebar filtres ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filtres")
    sel_terr = st.multiselect("Territoire", df_full['terr'].unique().tolist(),
                               default=df_full['terr'].unique().tolist())
    sel_csp  = st.multiselect("CSP", df_full['csp'].unique().tolist(),
                               default=df_full['csp'].unique().tolist())
    age_range = st.slider("Tranche d'âge", 0, 99, (18, 75))
    st.markdown("---")
    st.caption(f"Population filtrée : {len(df_full):,} personas")

# Appliquer filtres
df = df_full[
    (df_full['terr'].isin(sel_terr)) &
    (df_full['csp'].isin(sel_csp)) &
    (df_full['age'].between(age_range[0], age_range[1]))
].copy()

n = len(df)
if n == 0:
    st.warning("Aucune persona avec ces filtres.")
    st.stop()

# ── Onglets ──────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "👥 Population", "🚗 Pratiques de mobilité",
    "🌱 Dépendance & CO₂", "🎯 Segments cibles", "💬 Enquêtes IA"
])

# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("👥 Portrait de la population")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Personas", f"{n:,}")
    c2.metric("Âge moyen", f"{df['age'].mean():.1f} ans")
    c3.metric("% femmes", f"{(df['gender'].str.lower().str.contains('f|femme', na=False)).mean()*100:.1f}%")
    c4.metric("Km/j moyen", f"{df['km_jour'].mean():.1f} km")

    col1, col2 = st.columns(2)
    with col1:
        fig = px.histogram(df, x='age', color='gender', nbins=30,
                           title="Pyramide des âges",
                           color_discrete_sequence=['#3498db','#e91e63','#95a5a6'])
        fig.update_layout(bargap=0.05, legend_title="Genre")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        csp_counts = df['csp'].value_counts().reset_index()
        csp_counts.columns = ['csp','n']
        fig = px.pie(csp_counts, values='n', names='csp', title="Répartition CSP",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        terr_counts = df['terr'].value_counts().reset_index()
        terr_counts.columns = ['territoire','n']
        fig = px.bar(terr_counts, x='territoire', y='n', title="Distribution territoriale",
                     color='territoire', color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        age_terr = df.groupby(['classe_age','terr']).size().reset_index(name='n')
        fig = px.bar(age_terr, x='classe_age', y='n', color='terr',
                     title="Âge × Territoire",
                     color_discrete_sequence=px.colors.qualitative.Set1)
        st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("🚗 Pratiques de mobilité")

    # KPIs modes
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, mode, icon in [
        (c1,'pct_voiture','🚗'), (c2,'pct_tc','🚌'),
        (c3,'pct_velo','🚲'), (c4,'pct_marche','🚶'), (c5,'pct_cov','🤝')
    ]:
        val = df[mode].mean() if mode in df.columns else 0
        col.metric(f"{icon} {mode.replace('pct_','').title()}", f"{val:.1f}%")

    col1, col2 = st.columns(2)
    with col1:
        modes_moy = {
            'Voiture': df['pct_voiture'].mean(),
            'TC': df['pct_tc'].mean(),
            'Marche': df['pct_marche'].mean(),
            'Vélo': df['pct_velo'].mean(),
            'Covoiturage': df['pct_cov'].mean(),
        }
        fig = go.Figure(go.Bar(
            x=list(modes_moy.values()), y=list(modes_moy.keys()),
            orientation='h',
            marker_color=['#e74c3c','#3498db','#f39c12','#2ecc71','#9b59b6']
        ))
        fig.update_layout(title="Parts modales moyennes (%)", xaxis_title="%")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        km_csp = df.groupby('csp')['km_jour'].mean().reset_index()
        km_csp.columns = ['csp','km_jour']
        km_csp = km_csp.sort_values('km_jour', ascending=False)
        fig = px.bar(km_csp, x='csp', y='km_jour', title="Km/jour par CSP",
                     color='csp', color_discrete_sequence=px.colors.qualitative.Bold)
        st.plotly_chart(fig, use_container_width=True)

    # Modes par territoire
    modes = ['pct_voiture','pct_tc','pct_velo','pct_marche']
    terr_modes = df.groupby('terr')[modes].mean().reset_index()
    terr_modes_long = terr_modes.melt('terr', var_name='mode', value_name='pct')
    fig = px.bar(terr_modes_long, x='terr', y='pct', color='mode',
                 title="Parts modales par territoire", barmode='group',
                 color_discrete_map={'pct_voiture':'#e74c3c','pct_tc':'#3498db',
                                      'pct_velo':'#2ecc71','pct_marche':'#f39c12'})
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("🌱 Dépendance automobile & CO₂")

    c1, c2, c3 = st.columns(3)
    c1.metric("Score dépendance moyen", f"{df['score_dep'].mean():.1f}/100")
    c2.metric("CO₂ mobilité moyen/an", f"{df['co2_kg_an'].mean():.0f} kg")
    c3.metric("% très dépendants (>75)", f"{(df['score_dep']>75).mean()*100:.1f}%")

    col1, col2 = st.columns(2)
    with col1:
        fig = px.histogram(df, x='score_dep', nbins=30,
                           title="Distribution du score de dépendance auto",
                           color_discrete_sequence=['#e74c3c'])
        fig.add_vline(x=df['score_dep'].mean(), line_dash="dash", line_color="black",
                      annotation_text=f"Moy. {df['score_dep'].mean():.1f}")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        co2_terr = df.groupby('terr')['co2_kg_an'].mean().reset_index()
        fig = px.bar(co2_terr, x='terr', y='co2_kg_an', title="CO₂ moyen par territoire (kg/an)",
                     color='terr', color_discrete_sequence=px.colors.sequential.Reds)
        st.plotly_chart(fig, use_container_width=True)

    # Scatter dépendance vs CO2
    sample = df.sample(min(5000, n), random_state=42)
    fig = px.scatter(sample, x='score_dep', y='co2_kg_an', color='terr',
                     opacity=0.4, title="Dépendance auto vs Empreinte CO₂",
                     labels={'score_dep':'Score dépendance','co2_kg_an':'CO₂ kg/an'},
                     color_discrete_sequence=px.colors.qualitative.Safe)
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("🎯 Segments cibles pour politiques de mobilité")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🚲 Potentiel report vers le vélo")
        mask_velo = (
            (df['score_dep'] < 45) &
            (df['terr'].isin(['urbain_moyen','urbain_dense','periurbain'])) &
            (df['km_jour'] < 20)
        )
        n_velo = mask_velo.sum()
        st.metric("Personas ciblées", f"{n_velo:,} ({n_velo/n*100:.1f}%)")
        df_velo = df[mask_velo]
        fig = px.bar(df_velo['csp'].value_counts().reset_index(),
                     x='csp', y='count', title="CSP des personas pro-vélo",
                     color_discrete_sequence=['#2ecc71'])
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🚌 Potentiel report vers les TC")
        mask_tc = (
            (df['acces_train'] > 50) &
            (df['pct_voiture'] > 50) &
            (df['terr'].isin(['periurbain','urbain_moyen']))
        )
        n_tc = mask_tc.sum()
        st.metric("Personas ciblées", f"{n_tc:,} ({n_tc/n*100:.1f}%)")
        df_tc = df[mask_tc]
        fig = px.bar(df_tc['csp'].value_counts().reset_index(),
                     x='csp', y='count', title="CSP des personas pro-TC",
                     color_discrete_sequence=['#3498db'])
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("🤝 Potentiel covoiturage longue distance")
    mask_cov = (
        (df['km_jour'] > 15) &
        (df['terr'].isin(['rural','periurbain'])) &
        (df['pct_voiture'] > 60)
    )
    n_cov = mask_cov.sum()
    st.metric("Personas ciblées", f"{n_cov:,} ({n_cov/n*100:.1f}%)")

# ════════════════════════════════════════════════════════════════════════════
with tab5:
    st.header("💬 Enquêtes & Sondages IA sur les personas")

    st.info("🤖 Cette fonctionnalité simule les réponses de personas synthétiques à des questions de mobilité. Chaque réponse est générée à partir du profil statistique du segment.")

    question = st.text_area("Votre question :", value="Si une piste cyclable sécurisée était créée sur votre trajet domicile-travail, seriez-vous prêt à utiliser le vélo ?", height=80)

    terr_q = st.selectbox("Territoire ciblé", ['Tous'] + df['terr'].unique().tolist())
    csp_q  = st.selectbox("CSP ciblée", ['Toutes'] + df['csp'].unique().tolist())

    if st.button("🚀 Simuler les réponses"):
        df_q = df.copy()
        if terr_q != 'Tous': df_q = df_q[df_q['terr'] == terr_q]
        if csp_q  != 'Toutes': df_q = df_q[df_q['csp'] == csp_q]

        n_q = len(df_q)
        st.write(f"Échantillon : {n_q:,} personas")

        if n_q == 0:
            st.warning("Aucune persona avec ces critères.")
        else:
            # Simulation probabiliste basée sur les profils de mobilité
            pct_velo_moy = df_q['pct_velo'].mean() / 100
            score_dep_moy = df_q['score_dep'].mean()

            # Probabilité d'acceptation (simplifiée)
            p_oui = min(0.85, max(0.10,
                0.25  # base
                + pct_velo_moy * 1.5
                - (score_dep_moy - 50) * 0.005
                + (0.1 if terr_q in ['urbain_moyen','urbain_dense'] else 0)
            ))
            p_non     = (1 - p_oui) * 0.7
            p_peut    = (1 - p_oui) * 0.3
            p_sais_pas = max(0, 1 - p_oui - p_non - p_peut)

            r = {
                'Oui, certainement': round(p_oui * 100, 1),
                'Non, peu probable': round(p_non * 100, 1),
                'Peut-être': round(p_peut * 100, 1),
                'Ne sait pas': round(p_sais_pas * 100, 1),
            }

            c1, c2 = st.columns(2)
            with c1:
                for rep, pct in r.items():
                    st.progress(int(pct), text=f"{rep} : {pct:.1f}%")
            with c2:
                fig = px.pie(values=list(r.values()), names=list(r.keys()),
                             title=f"Réponses simulées ({n_q:,} personas)",
                             color_discrete_sequence=['#2ecc71','#e74c3c','#f39c12','#95a5a6'])
                st.plotly_chart(fig, use_container_width=True)

            st.caption("⚠️ Simulation probabiliste basée sur les profils EMP 2019. Les résultats sont indicatifs.")

# ── Pied de page ─────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Sources : EMP 2019 (SDES/INSEE) · Population synthétique NVIDIA Nemotron-Personas-France · Traitement Claude AI")

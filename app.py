import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import re
from pypdf import PdfReader

# ==========================================
# CONFIGURATION
# ==========================================
st.set_page_config(page_title="Gestion Financière Pro", layout="wide")

# ==========================================
# INITIALISATION EN MÉMOIRE
# ==========================================
if 'setup_step' not in st.session_state:
    st.session_state.setup_step = 1

if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {}

if 'df_charges_actuelles' not in st.session_state:
    st.session_state.df_charges_actuelles = pd.DataFrame([
        {"Catégorie": "Abonnements", "Description": "Forfait Téléphone", "Montant": 20.0},
        {"Catégorie": "Auto/Transport", "Description": "Assurance Auto", "Montant": 0.0}
    ])

if 'df_charges_futures' not in st.session_state:
    st.session_state.df_charges_futures = pd.DataFrame(columns=["Catégorie", "Description", "Montant"])

if 'transactions' not in st.session_state:
    st.session_state.transactions = pd.DataFrame(columns=["Date", "Mois", "Type", "Catégorie", "Description", "Montant", "Nature"])

if 'closed_months' not in st.session_state:
    st.session_state.closed_months = []

CATEGORIES_BESOINS = ["Logement", "Courses", "Auto/Transport", "Assurances", "Abonnements", "Frais Bancaires", "Santé"]
CATEGORIES_ENVIES = ["Sorties/Loisirs", "Shopping", "Vacances", "Autre"]
CATEGORIES_REV = ["Salaire", "Aides/CAF", "Ventes", "Remboursement", "Autre"]

def get_current_month_str():
    return datetime.date.today().strftime('%Y-%m')

def add_transaction(date_obj, type_trans, cat, desc, montant):
    mois_str = date_obj.strftime('%Y-%m')
    nature = "Besoin" if cat in CATEGORIES_BESOINS else ("Envie" if cat in CATEGORIES_ENVIES else "Revenu")
    new_row = pd.DataFrame([{"Date": date_obj, "Mois": mois_str, "Type": type_trans, "Catégorie": cat, "Description": desc, "Montant": float(montant), "Nature": nature}])
    st.session_state.transactions = pd.concat([st.session_state.transactions, new_row], ignore_index=True)

# ==========================================
# ASSISTANT DE CONFIGURATION (PARTIES 1 & 2)
# ==========================================
if st.session_state.setup_step < 4:
    st.title("Configuration de votre Profil")
    st.progress(st.session_state.setup_step / 3.0)

    # --- ÉTAPE 1 : CHOIX DU PROJET ---
    if st.session_state.setup_step == 1:
        st.header("Étape 1 : Quel est votre objectif principal ?")
        projet_type = st.radio("Sélectionnez votre projet de vie :", [
            "🏠 Prendre mon indépendance (Location)", 
            "🚗 Acheter un véhicule (Auto / Moto)", 
            "🛡️ Créer un Fonds d'Urgence (Sécurité)"
        ])
        if st.button("Suivant", type="primary"):
            st.session_state.user_profile['projet_type'] = projet_type
            st.session_state.setup_step = 2
            st.rerun()

    # --- ÉTAPE 2 : DÉTAILS DU PROJET ---
    elif st.session_state.setup_step == 2:
        st.header("Étape 2 : Cadrage du projet")
        projet = st.session_state.user_profile['projet_type']
        
        if projet == "🏠 Prendre mon indépendance (Location)":
            st.info("💡 Astuce Marché : Un T2/T3 se loue en moyenne entre 800 € et 1050 €/mois. Les agences exigent des revenus égaux à 3 fois le loyer.")
            st.session_state.user_profile['loyer_vise'] = st.number_input("Loyer maximum visé (€)", value=800.0, step=50.0)
            st.session_state.user_profile['apport_vise'] = st.number_input("Apport de départ (Caution + Meubles) (€)", value=2000.0, step=100.0)
            st.session_state.df_charges_futures = pd.DataFrame([
                {"Catégorie": "Logement", "Description": "Electricité / Gaz", "Montant": 80.0},
                {"Catégorie": "Logement", "Description": "Assurance Habitation", "Montant": 20.0},
                {"Catégorie": "Courses", "Description": "Courses Alimentaires (Est.)", "Montant": 250.0}
            ])
            
        elif projet == "🚗 Acheter un véhicule (Auto / Moto)":
            st.info("💡 Astuce Auto : Une citadine fiable coûte environ 8000 €. Gardez 500 € pour la carte grise et la première assurance.")
            st.session_state.user_profile['montant_achat'] = st.number_input("Prix total estimé du véhicule (€)", value=8000.0, step=500.0)
            st.session_state.user_profile['delai_mois'] = st.slider("Dans combien de mois voulez-vous l'acheter ?", 1, 48, 12)
            st.session_state.df_charges_futures = pd.DataFrame([
                {"Catégorie": "Auto/Transport", "Description": "Nouvelle Assurance Auto", "Montant": 90.0},
                {"Catégorie": "Auto/Transport", "Description": "Nouveau budget Essence", "Montant": 100.0}
            ])

        elif projet == "🛡️ Créer un Fonds d'Urgence (Sécurité)":
            st.info("💡 Règle d'or : Un matelas de sécurité doit représenter entre 3 et 6 mois de salaire.")
            st.session_state.user_profile['mois_securite'] = st.slider("Mois de salaire à sécuriser ?", 1, 12, 3)

        col1, col2 = st.columns(2)
        if col1.button("Retour"):
            st.session_state.setup_step = 1
            st.rerun()
        if col2.button("Suivant", type="primary"):
            st.session_state.setup_step = 3
            st.rerun()

    # --- ÉTAPE 3 : REVENUS ET CHARGES ---
    elif st.session_state.setup_step == 3:
        st.header("Étape 3 : Vos flux réguliers")
        
        st.subheader("1. Votre Salaire Net Mensuel")
        st.session_state.user_profile['salaire_base'] = st.number_input("Salaire principal (€)", value=1500.0, step=10.0)

        c_actuelles, c_futures = st.columns(2)
        with c_actuelles:
            st.subheader("2. Vos charges actuelles")
            edited_actuelles = st.data_editor(st.session_state.df_charges_actuelles, num_rows="dynamic", use_container_width=True)
            
        with c_futures:
            st.subheader("3. Simulation des charges futures")
            edited_futures = st.data_editor(st.session_state.df_charges_futures, num_rows="dynamic", use_container_width=True)

        col1, col2 = st.columns(2)
        if col1.button("Retour"):
            st.session_state.setup_step = 2
            st.rerun()
        if col2.button("Finaliser et Lancer", type="primary"):
            st.session_state.df_charges_actuelles = edited_actuelles
            st.session_state.df_charges_futures = edited_futures
            st.session_state.user_profile['total_actuel'] = edited_actuelles['Montant'].sum()
            st.session_state.user_profile['total_futur'] = edited_futures['Montant'].sum()
            st.session_state.setup_step = 4
            st.rerun()

# ==========================================
# L'APPLICATION : TABLEAU DE BORD (PARTIE 3)
# ==========================================
elif st.session_state.setup_step == 4:
    df = st.session_state.transactions.copy()
    current_m = get_current_month_str()
    mois_dispos = sorted(list(set(df['Mois'].tolist() + [current_m])), reverse=True)
    profil = st.session_state.user_profile
    
    # --- BARRE D'ACTIONS LATÉRALE ---
    st.sidebar.title("Menu d'actions")
    selected_month = st.sidebar.selectbox("Sélectionner le mois", mois_dispos)
    
    st.sidebar.divider()
    
    # NOUVEAU MODULE : ENTRÉES RAPIDES ET MODIFIABLES
    st.sidebar.subheader("💵 Entrées Rapides")
    
    # Salaire
    salaire_reel = st.sidebar.number_input("Salaire exact reçu ce mois-ci (€)", value=float(profil['salaire_base']), step=10.0)
    if st.sidebar.button("Ajouter ce Salaire", use_container_width=True):
        add_transaction(datetime.date.today(), "Revenu", "Salaire", "Salaire mensuel", salaire_reel)
        st.rerun()

    # CAF
    caf_reelle = st.sidebar.number_input("Aides CAF exactes reçues (€)", value=0.0, step=10.0)
    if st.sidebar.button("Ajouter la CAF", use_container_width=True):
        if caf_reelle > 0:
            add_transaction(datetime.date.today(), "Revenu", "Aides/CAF", "Versement CAF", caf_reelle)
            st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("🔒 Clôturer le mois", type="primary", use_container_width=True):
        if selected_month not in st.session_state.closed_months:
            st.session_state.closed_months.append(selected_month)
            next_month_date = datetime.date.today().replace(day=1) + datetime.timedelta(days=32)
            # Recopie automatique des charges actuelles
            for _, row in st.session_state.df_charges_actuelles.iterrows():
                add_transaction(next_month_date.replace(day=1), "Dépense", row["Catégorie"], f"{row['Description']} (Auto)", row["Montant"])
            st.rerun()
            
    st.sidebar.divider()
    if st.sidebar.button("⚙️ Recommencer la configuration", use_container_width=True):
        st.session_state.setup_step = 1
        st.rerun()

    # --- CALCULS DU MOIS ---
    df_selected = df[df['Mois'] == selected_month]
    rev_mois = df_selected[df_selected['Type'] == 'Revenu']['Montant'].sum()
    dep_mois = df_selected[df_selected['Type'] == 'Dépense']['Montant'].sum()
    epargne_mois = rev_mois - dep_mois
    
    epargne_totale = df[df['Type'] == 'Revenu']['Montant'].sum() - df[df['Type'] == 'Dépense']['Montant'].sum()

    tab_dash, tab_transac, tab_import = st.tabs(["📊 Tableau de Bord", "✍️ Saisie Manuelle", "📄 Import PDF (Caisse d'Epargne)"])

    # --- ONGLET 1 : LE DASHBOARD ÉPURÉ ---
    with tab_dash:
        st.markdown(f"### Objectif : {profil['projet_type']}")
        
        # 1. EN-TÊTE : LES 3 GROS CHIFFRES (Crash-Test intégré)
        reste_futur = epargne_mois - profil.get('total_futur', 0)
        loyer_simule = profil.get('loyer_vise', 0)
        if profil['projet_type'] == "🏠 Prendre mon indépendance (Location)":
            reste_futur -= loyer_simule

        c1, c2, c3 = st.columns(3)
        c1.metric("Disponible ce mois", f"{epargne_mois:.2f} €", "Reste à vivre actuel")
        c2.metric("Épargne Globale Sécurisée", f"{epargne_totale:.2f} €")
        c3.metric("Crash-Test : Reste à vivre FUTUR", f"{reste_futur:.2f} €", "Si votre projet était réalisé", delta_color="normal" if reste_futur > 0 else "inverse")
        st.divider()

        # 2. CŒUR DU DASHBOARD
        col_gauche, col_droite = st.columns([1, 1.2])

        with col_gauche:
            st.write("**Répartition 50/30/20 (Santé financière)**")
            if rev_mois > 0:
                dep_besoins = df_selected[df_selected['Nature'] == 'Besoin']['Montant'].sum()
                dep_envies = df_selected[df_selected['Nature'] == 'Envie']['Montant'].sum()
                
                pct_besoins = (dep_besoins / rev_mois) * 100
                pct_envies = (dep_envies / rev_mois) * 100
                pct_epargne = (epargne_mois / rev_mois) * 100
                
                st.progress(min(pct_besoins/100, 1.0))
                st.caption(f"Besoins incompressibles : {pct_besoins:.0f}% (Idéal < 50%)")
                
                st.progress(min(pct_envies/100, 1.0))
                st.caption(f"Envies / Loisirs : {pct_envies:.0f}% (Idéal < 30%)")
                
                st.progress(min(max(pct_epargne, 0)/100, 1.0))
                st.caption(f"Épargne : {pct_epargne:.0f}% (Idéal > 20%)")
            else:
                st.info("Ajoutez des revenus pour voir la répartition.")

            st.write("**Catégories de dépenses**")
            df_dep_mois = df_selected[df_selected['Type'] == 'Dépense']
            if not df_dep_mois.empty:
                fig_donut = px.pie(df_dep_mois, values='Montant', names='Catégorie', hole=0.6, height=250)
                fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
                st.plotly_chart(fig_donut, use_container_width=True)

        with col_droite:
            st.write("**Analyse Spécifique du Projet**")
            if profil['projet_type'] == "🏠 Prendre mon indépendance (Location)":
                taux_effort = (loyer_simule / rev_mois) * 100 if rev_mois > 0 else 100
                st.write(f"Taux d'effort (Loyer / Revenus) : **{taux_effort:.1f}%**")
                if taux_effort <= 33: st.success("Dossier d'agence : ACCEPTABLE (Taux < 33%)")
                else: st.error("Dossier d'agence : RISQUÉ (Garant obligatoire)")
                
                progress_apport = min(epargne_totale / profil['apport_vise'], 1.0) if profil['apport_vise'] > 0 else 1.0
                st.write(f"Apport (Caution/Meubles) : **{epargne_totale:.2f} € / {profil['apport_vise']:.2f} €**")
                st.progress(progress_apport)

            # Courbe de prédiction simplifiée
            st.write("**Évolution de l'épargne**")
            df_hist = df.groupby('Mois').apply(lambda x: x[x['Type']=='Revenu']['Montant'].sum() - x[x['Type']=='Dépense']['Montant'].sum()).reset_index(name='Epargne_Nette')
            if not df_hist.empty:
                df_hist['Cumul'] = df_hist['Epargne_Nette'].cumsum()
                fig_line = go.Figure()
                fig_line.add_trace(go.Scatter(x=df_hist['Mois'], y=df_hist['Cumul'], mode='lines+markers', name='Épargne', line=dict(color='#2ECC71', width=3)))
                fig_line.update_layout(height=250, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig_line, use_container_width=True)

    # --- ONGLET 2 : SAISIE MANUELLE ---
    with tab_transac:
        with st.form("ajout_transac"):
            c1, c2, c3, c4 = st.columns(4)
            t_type = c1.selectbox("Type", ["Dépense", "Revenu"])
            t_cat = c2.selectbox("Catégorie", CATEGORIES_BESOINS + CATEGORIES_ENVIES if t_type == "Dépense" else CATEGORIES_REV)
            t_desc = c3.text_input("Libellé")
            t_montant = c4.number_input("Montant (€)", min_value=0.0, step=1.0)
            if st.form_submit_button("Ajouter") and t_desc and t_montant > 0:
                add_transaction(datetime.date.today(), t_type, t_cat, t_desc, t_montant)
                st.rerun()
        st.dataframe(df_selected[['Date', 'Type', 'Catégorie', 'Description', 'Montant']].sort_values(by="Date", ascending=False), use_container_width=True, hide_index=True)

    # --- ONGLET 3 : IMPORT PDF CAISSE D'EPARGNE (PARTIE 4) ---
    with tab_import:
        st.info("Lecteur intelligent calibré pour les relevés de la Caisse d'Épargne CEPAC.")
        uploaded_pdf = st.file_uploader("Déposez votre relevé PDF", type="pdf")
        if uploaded_pdf and st.button("Analyser le relevé"):
            reader = PdfReader(uploaded_pdf)
            text_ext = "".join([page.extract_text() + "\n" for page in reader.pages])
            
            # Filtre chirurgical : Date + Date + Texte + Montant (Exclut les soldes)
            pattern = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(?:\d{2}/\d{2}/\d{4})\s+(.*?)([+-]\s?\d{1,3}(?:\s?\d{3})*,\d{2})")
            
            count = 0
            for match in pattern.findall(text_ext):
                date_str, desc, amount_str = match
                desc = desc.strip()
                
                # SÉCURITÉ : On ignore les lignes de Solde Total
                if "SOLDE" in desc.upper():
                    continue
                    
                amount_clean = amount_str.replace(" ", "").replace(",", ".")
                val = float(amount_clean)
                
                # Extraction de la date
                d, m, y = map(int, date_str.split('/'))
                trans_date = datetime.date(y, m, d)
                
                if val > 0: add_transaction(trans_date, "Revenu", "Autre", desc[:40], val)
                elif val < 0: add_transaction(trans_date, "Dépense", "Autre", desc[:40], abs(val))
                count += 1
                
            st.success(f"Opération réussie : {count} vraies transactions importées (Les soldes ont été ignorés).")
            st.rerun()

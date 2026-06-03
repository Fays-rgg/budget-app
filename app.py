import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import re
import os
import json
from pypdf import PdfReader

# ==========================================
# CONFIGURATION
# ==========================================
st.set_page_config(page_title="Gestion Financière Pro", layout="wide")

# ==========================================
# FONCTIONS DE SAUVEGARDE (AUTO-SAVE)
# ==========================================
def save_state():
    """Sauvegarde toutes les données dans des fichiers locaux."""
    # Sauvegarde du profil et de l'étape
    data = {
        "setup_step": st.session_state.setup_step,
        "user_profile": st.session_state.user_profile,
        "closed_months": st.session_state.closed_months
    }
    with open("profil.json", "w") as f:
        json.dump(data, f)
        
    # Sauvegarde des tableaux (CSV)
    st.session_state.df_charges_actuelles.to_csv("charges_actuelles.csv", index=False)
    st.session_state.df_charges_futures.to_csv("charges_futures.csv", index=False)
    st.session_state.transactions.to_csv("transactions.csv", index=False)

def load_state():
    """Charge les données si les fichiers de sauvegarde existent."""
    if os.path.exists("profil.json"):
        with open("profil.json", "r") as f:
            data = json.load(f)
        st.session_state.setup_step = data["setup_step"]
        st.session_state.user_profile = data["user_profile"]
        st.session_state.closed_months = data["closed_months"]
        
    if os.path.exists("charges_actuelles.csv"):
        st.session_state.df_charges_actuelles = pd.read_csv("charges_actuelles.csv")
    if os.path.exists("charges_futures.csv"):
        st.session_state.df_charges_futures = pd.read_csv("charges_futures.csv")
    if os.path.exists("transactions.csv"):
        df_trans = pd.read_csv("transactions.csv")
        df_trans['Date'] = pd.to_datetime(df_trans['Date']).dt.date
        st.session_state.transactions = df_trans

# ==========================================
# INITIALISATION EN MÉMOIRE
# ==========================================
if 'init_done' not in st.session_state:
    # 1. Variables par défaut
    st.session_state.setup_step = 1
    st.session_state.user_profile = {}
    st.session_state.df_charges_actuelles = pd.DataFrame([
        {"Catégorie": "Abonnements", "Description": "Forfait Téléphone", "Montant": 20.0},
        {"Catégorie": "Auto/Transport", "Description": "Assurance Auto", "Montant": 0.0}
    ])
    st.session_state.df_charges_futures = pd.DataFrame(columns=["Catégorie", "Description", "Montant"])
    st.session_state.transactions = pd.DataFrame(columns=["Date", "Mois", "Type", "Catégorie", "Description", "Montant", "Nature"])
    st.session_state.closed_months = []
    
    # 2. On essaie de charger la sauvegarde
    load_state()
    st.session_state.init_done = True

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
    save_state() # <-- AUTO-SAVE

# ==========================================
# ASSISTANT DE CONFIGURATION (PARTIES 1 & 2)
# ==========================================
if st.session_state.setup_step < 4:
    st.title("Configuration de votre Profil")
    st.progress(st.session_state.setup_step / 3.0)

    # --- ÉTAPE 1 ---
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
            save_state()
            st.rerun()

    # --- ÉTAPE 2 ---
    elif st.session_state.setup_step == 2:
        st.header("Étape 2 : Cadrage du projet")
        projet = st.session_state.user_profile['projet_type']
        
        if projet == "🏠 Prendre mon indépendance (Location)":
            st.info("💡 Astuce Marché : Un T2/T3 se loue en moyenne entre 800 € et 1050 €/mois.")
            st.session_state.user_profile['loyer_vise'] = st.number_input("Loyer maximum visé (€)", value=800.0, step=50.0)
            st.session_state.user_profile['apport_vise'] = st.number_input("Apport de départ (Caution + Meubles) (€)", value=2000.0, step=100.0)
            st.session_state.df_charges_futures = pd.DataFrame([
                {"Catégorie": "Logement", "Description": "Electricité / Gaz", "Montant": 80.0},
                {"Catégorie": "Logement", "Description": "Assurance Habitation", "Montant": 20.0},
                {"Catégorie": "Courses", "Description": "Courses Alimentaires (Est.)", "Montant": 250.0}
            ])
            
        elif projet == "🚗 Acheter un véhicule (Auto / Moto)":
            st.info("💡 Astuce Auto : Une citadine fiable coûte environ 8000 €.")
            st.session_state.user_profile['montant_achat'] = st.number_input("Prix total estimé du véhicule (€)", value=8000.0, step=500.0)
            st.session_state.user_profile['delai_mois'] = st.slider("Dans combien de mois voulez-vous l'acheter ?", 1, 48, 12)
            st.session_state.df_charges_futures = pd.DataFrame([
                {"Catégorie": "Auto/Transport", "Description": "Nouvelle Assurance Auto", "Montant": 90.0},
                {"Catégorie": "Auto/Transport", "Description": "Nouveau budget Essence", "Montant": 100.0}
            ])

        elif projet == "🛡️ Créer un Fonds d'Urgence (Sécurité)":
            st.session_state.user_profile['mois_securite'] = st.slider("Mois de salaire à sécuriser ?", 1, 12, 3)

        col1, col2 = st.columns(2)
        if col1.button("Retour"):
            st.session_state.setup_step = 1
            st.rerun()
        if col2.button("Suivant", type="primary"):
            st.session_state.setup_step = 3
            save_state()
            st.rerun()

    # --- ÉTAPE 3 ---
    elif st.session_state.setup_step == 3:
        st.header("Étape 3 : Vos flux réguliers & Compte Bancaire")
        
        c_compte, c_salaire = st.columns(2)
        with c_compte:
            st.session_state.user_profile['solde_initial'] = st.number_input("🏦 Solde ACTUEL sur votre compte en banque (€)", value=0.0, step=50.0)
        with c_salaire:
            st.session_state.user_profile['salaire_base'] = st.number_input("💶 Salaire principal prévu ce mois-ci (€)", value=1500.0, step=10.0)

        st.divider()

        c_actuelles, c_futures = st.columns(2)
        with c_actuelles:
            st.subheader("Vos charges actuelles")
            edited_actuelles = st.data_editor(st.session_state.df_charges_actuelles, num_rows="dynamic", use_container_width=True)
            
        with c_futures:
            st.subheader("Simulation des charges futures")
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
            save_state() # <-- AUTO-SAVE
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
    
    st.sidebar.subheader("💵 Entrées Rapides")
    salaire_reel = st.sidebar.number_input("Salaire reçu ce mois-ci (€)", value=float(profil['salaire_base']), step=10.0)
    if st.sidebar.button("Ajouter ce Salaire", use_container_width=True):
        add_transaction(datetime.date.today(), "Revenu", "Salaire", "Salaire mensuel", salaire_reel)
        st.rerun()

    caf_reelle = st.sidebar.number_input("Aides CAF reçues (€)", value=0.0, step=10.0)
    if st.sidebar.button("Ajouter la CAF", use_container_width=True):
        if caf_reelle > 0:
            add_transaction(datetime.date.today(), "Revenu", "Aides/CAF", "Versement CAF", caf_reelle)
            st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("🔒 Clôturer le mois", type="primary", use_container_width=True):
        if selected_month not in st.session_state.closed_months:
            st.session_state.closed_months.append(selected_month)
            next_month_date = datetime.date.today().replace(day=1) + datetime.timedelta(days=32)
            for _, row in st.session_state.df_charges_actuelles.iterrows():
                add_transaction(next_month_date.replace(day=1), "Dépense", row["Catégorie"], f"{row['Description']} (Auto)", row["Montant"])
            save_state() # <-- AUTO-SAVE
            st.rerun()
            
    st.sidebar.divider()
    if st.sidebar.button("⚙️ Recommencer la configuration", use_container_width=True):
        st.session_state.setup_step = 1
        save_state()
        st.rerun()

    # --- CALCULS DU MOIS ---
    df_selected = df[df['Mois'] == selected_month]
    rev_mois = df_selected[df_selected['Type'] == 'Revenu']['Montant'].sum()
    dep_mois = df_selected[df_selected['Type'] == 'Dépense']['Montant'].sum()
    epargne_mois = rev_mois - dep_mois
    
    epargne_totale = df[df['Type'] == 'Revenu']['Montant'].sum() - df[df['Type'] == 'Dépense']['Montant'].sum()
    solde_bancaire_actuel = profil.get('solde_initial', 0.0) + epargne_totale

    tab_dash, tab_transac, tab_import = st.tabs(["📊 Tableau de Bord", "✍️ Saisie Manuelle & Modification", "📄 Import PDF (Caisse d'Epargne)"])

    # --- ONGLET 1 : LE DASHBOARD ---
    with tab_dash:
        st.markdown(f"### Objectif : {profil['projet_type']}")
        
        reste_futur = epargne_mois - profil.get('total_futur', 0)
        loyer_simule = profil.get('loyer_vise', 0)
        if profil['projet_type'] == "🏠 Prendre mon indépendance (Location)":
            reste_futur -= loyer_simule

        c1, c2, c3 = st.columns(3)
        c1.metric("🏦 Solde en Banque", f"{solde_bancaire_actuel:.2f} €", "Votre vrai solde (Aujourd'hui)")
        c2.metric("Bilan du mois", f"{epargne_mois:.2f} €", f"Entrées: {rev_mois}€ | Sorties: {dep_mois}€")
        c3.metric("Crash-Test : Reste à vivre FUTUR", f"{reste_futur:.2f} €", "Ce qu'il resterait avec votre projet", delta_color="normal" if reste_futur > 0 else "inverse")
        st.divider()

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

            st.write("**Évolution de l'épargne**")
            if not df.empty:
                df_hist = df.groupby('Mois').apply(lambda x: x[x['Type']=='Revenu']['Montant'].sum() - x[x['Type']=='Dépense']['Montant'].sum()).reset_index()
                df_hist.columns = ['Mois', 'Epargne_Nette']
                df_hist['Cumul'] = df_hist['Epargne_Nette'].cumsum()
                
                fig_line = go.Figure()
                fig_line.add_trace(go.Scatter(x=df_hist['Mois'], y=df_hist['Cumul'], mode='lines+markers', name='Épargne', line=dict(color='#2ECC71', width=3)))
                fig_line.update_layout(height=250, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.info("Saisissez des revenus ou dépenses pour générer la courbe.")

    # --- ONGLET 2 : SAISIE & MODIFICATION ---
    with tab_transac:
        c_ajout, c_suppr = st.columns([1.5, 1])
        
        with c_ajout:
            st.subheader("Ajouter une opération")
            with st.form("ajout_transac"):
                c1, c2, c3 = st.columns(3)
                t_type = c1.selectbox("Type", ["Dépense", "Revenu"])
                t_cat = c2.selectbox("Catégorie", CATEGORIES_BESOINS + CATEGORIES_ENVIES if t_type == "Dépense" else CATEGORIES_REV)
                t_desc = c3.text_input("Libellé")
                t_montant = st.number_input("Montant (€)", min_value=0.0, step=1.0)
                if st.form_submit_button("Ajouter") and t_desc and t_montant > 0:
                    add_transaction(datetime.date.today(), t_type, t_cat, t_desc, t_montant)
                    st.rerun()
                    
        with c_suppr:
            st.subheader("🗑️ Supprimer une ligne")
            if not df_selected.empty:
                options_dict = {i: f"{row['Date']} - {row['Description']} ({row['Montant']}€)" for i, row in df_selected.iterrows()}
                op_to_delete = st.selectbox("Choisissez l'opération à retirer :", options=list(options_dict.keys()), format_func=lambda x: options_dict[x])
                
                if st.button("Supprimer définitivement", type="primary"):
                    st.session_state.transactions = st.session_state.transactions.drop(op_to_delete)
                    save_state() # <-- AUTO-SAVE
                    st.rerun()
            else:
                st.info("Aucune opération ce mois-ci.")

        st.divider()
        st.write("Historique du mois :")
        st.dataframe(df_selected[['Date', 'Type', 'Catégorie', 'Description', 'Montant']].sort_values(by="Date", ascending=False), use_container_width=True, hide_index=True)

    # --- ONGLET 3 : IMPORT PDF ---
    with tab_import:
        st.info("Lecteur intelligent calibré pour les relevés de la Caisse d'Épargne CEPAC.")
        uploaded_pdf = st.file_uploader("Déposez votre relevé PDF", type="pdf")
        if uploaded_pdf and st.button("Analyser le relevé"):
            reader = PdfReader(uploaded_pdf)
            text_ext = "".join([page.extract_text() + "\n" for page in reader.pages])
            
            pattern = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(?:\d{2}/\d{2}/\d{4})\s+(.*?)([+-]\s?\d{1,3}(?:\s?\d{3})*,\d{2})")
            
            count = 0
            for match in pattern.findall(text_ext):
                date_str, desc, amount_str = match
                desc = desc.strip()
                
                if "SOLDE" in desc.upper():
                    continue
                    
                amount_clean = amount_str.replace(" ", "").replace(",", ".")
                val = float(amount_clean)
                d, m, y = map(int, date_str.split('/'))
                trans_date = datetime.date(y, m, d)
                
                if val > 0: add_transaction(trans_date, "Revenu", "Autre", desc[:40], val)
                elif val < 0: add_transaction(trans_date, "Dépense", "Autre", desc[:40], abs(val))
                count += 1
                
            st.success(f"Opération réussie : {count} vraies transactions importées.")
            st.rerun()

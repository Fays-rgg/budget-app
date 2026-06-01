import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import calendar
import re
from pypdf import PdfReader

# ==========================================
# CONFIGURATION
# ==========================================
st.set_page_config(page_title="Logiciel de Gestion Financière", layout="wide")

# ==========================================
# INITIALISATION EN MÉMOIRE (SESSION STATE)
# ==========================================
if 'setup_step' not in st.session_state:
    st.session_state.setup_step = 1  # L'assistant commence à l'étape 1

if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {}

if 'df_charges_fixes' not in st.session_state:
    st.session_state.df_charges_fixes = pd.DataFrame([
        {"Catégorie": "Auto/Transport", "Description": "Assurance", "Montant": 100.0},
        {"Catégorie": "Abonnements", "Description": "Téléphone", "Montant": 20.0}
    ])

if 'transactions' not in st.session_state:
    st.session_state.transactions = pd.DataFrame(columns=["Date", "Mois", "Type", "Catégorie", "Description", "Montant", "Nature"])

if 'closed_months' not in st.session_state:
    st.session_state.closed_months = []

CATEGORIES_BESOINS = ["Logement", "Courses", "Auto/Transport", "Assurances", "Abonnements", "Frais Bancaires", "Santé"]
CATEGORIES_ENVIES = ["Sorties/Loisirs", "Shopping", "Vacances", "Autre"]
CATEGORIES_REV = ["Salaire", "Aides/CAF", "Ventes", "Remboursement", "Autre"]

def get_current_month_str():
    return datetime.date.today().strftime('%Y-%m')

def apply_rule_28(date_obj):
    if date_obj.day >= 25:
        if date_obj.month == 12: return datetime.date(date_obj.year + 1, 1, 1)
        else: return datetime.date(date_obj.year, date_obj.month + 1, 1)
    return date_obj

def add_transaction(date_obj, type_trans, cat, desc, montant):
    adjusted_date = apply_rule_28(date_obj) if type_trans == "Revenu" else date_obj
    mois_str = adjusted_date.strftime('%Y-%m')
    nature = "Besoin" if cat in CATEGORIES_BESOINS else ("Envie" if cat in CATEGORIES_ENVIES else "Revenu")
    new_row = pd.DataFrame([{"Date": adjusted_date, "Mois": mois_str, "Type": type_trans, "Catégorie": cat, "Description": desc, "Montant": float(montant), "Nature": nature}])
    st.session_state.transactions = pd.concat([st.session_state.transactions, new_row], ignore_index=True)

# ==========================================
# ASSISTANT DE CONFIGURATION (MULTI-ÉTAPES)
# ==========================================
if st.session_state.setup_step < 4:
    st.title("Configuration du Profil Financier")
    st.progress(st.session_state.setup_step / 3.0)

    # --- ÉTAPE 1 : CHOIX DU PROJET ---
    if st.session_state.setup_step == 1:
        st.header("Étape 1 : Quel est votre objectif principal ?")
        projet_type = st.radio("Sélectionnez la nature de votre projet :", [
            "Indépendance (Louer un appartement)", 
            "Achat ciblé (Véhicule, Matériel...)", 
            "Matelas de sécurité (Épargner sans but précis)"
        ])
        
        if st.button("Suivant"):
            st.session_state.user_profile['projet_type'] = projet_type
            st.session_state.setup_step = 2
            st.rerun()

    # --- ÉTAPE 2 : DÉTAILS DYNAMIQUES DU PROJET ---
    elif st.session_state.setup_step == 2:
        st.header("Étape 2 : Détails du projet")
        
        # Formulaire dynamique selon le choix précédent
        if st.session_state.user_profile['projet_type'] == "Indépendance (Louer un appartement)":
            st.write("Pour un logement, l'important est la capacité mensuelle (Loyer + Charges) et l'apport (Caution + Meubles).")
            loyer_vise = st.number_input("Loyer maximum envisagé (Charges comprises) (€)", value=500.0, step=50.0)
            apport_vise = st.number_input("Épargne de départ nécessaire (Caution + Meubles) (€)", value=1500.0, step=100.0)
            st.session_state.user_profile['loyer_vise'] = loyer_vise
            st.session_state.user_profile['apport_vise'] = apport_vise
            
        elif st.session_state.user_profile['projet_type'] == "Achat ciblé (Véhicule, Matériel...)":
            st.write("Pour un achat, l'important est le prix total et le délai que vous vous accordez.")
            montant_achat = st.number_input("Prix total estimé (€)", value=3000.0, step=100.0)
            delai_mois = st.slider("Dans combien de mois souhaitez-vous réaliser cet achat ?", 1, 48, 12)
            st.session_state.user_profile['montant_achat'] = montant_achat
            st.session_state.user_profile['delai_mois'] = delai_mois
            
        elif st.session_state.user_profile['projet_type'] == "Matelas de sécurité (Épargner sans but précis)":
            st.write("L'objectif est d'atteindre un fonds d'urgence équivalent à plusieurs mois de salaire.")
            mois_securite = st.slider("Combien de mois de salaire voulez-vous sécuriser ?", 1, 12, 3)
            st.session_state.user_profile['mois_securite'] = mois_securite

        col1, col2 = st.columns(2)
        if col1.button("Retour"):
            st.session_state.setup_step = 1
            st.rerun()
        if col2.button("Suivant", type="primary"):
            st.session_state.setup_step = 3
            st.rerun()

    # --- ÉTAPE 3 : REVENUS & MULTIPLES CHARGES FIXES ---
    elif st.session_state.setup_step == 3:
        st.header("Étape 3 : Vos flux réguliers")
        
        col_rev, col_dep = st.columns([1, 1.5])
        with col_rev:
            st.subheader("Revenus")
            salaire = st.number_input("Revenu mensuel net (€)", value=970.0, step=10.0)
            foyer = st.number_input("Personnes dans le foyer", value=1, min_value=1)
            
        with col_dep:
            st.subheader("Charges fixes")
            st.write("Listez toutes vos dépenses incompressibles ci-dessous :")
            edited_charges = st.data_editor(
                st.session_state.df_charges_fixes,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Catégorie": st.column_config.SelectboxColumn("Catégorie", options=CATEGORIES_BESOINS, required=True),
                    "Description": st.column_config.TextColumn("Description", required=True),
                    "Montant": st.column_config.NumberColumn("Montant (€)", min_value=0.0, format="%.2f", required=True)
                }
            )
            total_fixes = edited_charges["Montant"].sum()
            st.info(f"Total charges fixes : {total_fixes:.2f} € / mois")

        col1, col2 = st.columns(2)
        if col1.button("Retour"):
            st.session_state.setup_step = 2
            st.rerun()
        if col2.button("Finaliser et Lancer", type="primary"):
            st.session_state.user_profile['salaire_base'] = salaire
            st.session_state.user_profile['foyer'] = foyer
            st.session_state.user_profile['depenses_fixes'] = total_fixes
            st.session_state.df_charges_fixes = edited_charges
            st.session_state.setup_step = 4 # Lance l'application
            st.rerun()

# ==========================================
# L'APPLICATION (DASHBOARD)
# ==========================================
elif st.session_state.setup_step == 4:
    df = st.session_state.transactions.copy()
    current_m = get_current_month_str()
    mois_dispos = sorted(list(set(df['Mois'].tolist() + [current_m])), reverse=True)
    profil = st.session_state.user_profile
    
    st.sidebar.title("Menu")
    selected_month = st.sidebar.selectbox("Mois de travail", mois_dispos)
    
    if st.sidebar.button("Clôturer ce mois"):
        if selected_month not in st.session_state.closed_months:
            st.session_state.closed_months.append(selected_month)
            next_month_date = datetime.date.today().replace(day=1) + datetime.timedelta(days=32)
            for _, row in st.session_state.df_charges_fixes.iterrows():
                add_transaction(next_month_date.replace(day=1), "Dépense", row["Catégorie"], f"{row['Description']} (Auto)", row["Montant"])
            st.rerun()
            
    st.sidebar.divider()
    if st.sidebar.button("Recommencer la configuration"):
        st.session_state.setup_step = 1
        st.rerun()

    df_selected = df[df['Mois'] == selected_month]
    rev_mois = df_selected[df_selected['Type'] == 'Revenu']['Montant'].sum()
    dep_mois = df_selected[df_selected['Type'] == 'Dépense']['Montant'].sum()
    epargne_mois = rev_mois - dep_mois

    tab_dash, tab_transac = st.tabs(["Tableau de bord", "Saisie des opérations"])

    with tab_dash:
        st.title(f"Projet : {profil['projet_type']}")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Revenus du mois", f"{rev_mois:.2f} €")
        c2.metric("Dépenses du mois", f"{dep_mois:.2f} €")
        c3.metric("Bilan (Épargne)", f"{epargne_mois:.2f} €")
        st.divider()

        # AFFICHAGE DYNAMIQUE SELON LE PROJET
        if profil['projet_type'] == "Indépendance (Louer un appartement)":
            st.subheader("Analyse du dossier de location")
            loyer = profil['loyer_vise']
            taux_effort = (loyer / rev_mois) * 100 if rev_mois > 0 else 100
            
            c_loyer, c_apport = st.columns(2)
            c_loyer.metric("Taux d'effort (Objectif < 33%)", f"{taux_effort:.1f}%", delta_color="inverse")
            if taux_effort <= 33: c_loyer.success("Revenus suffisants pour ce loyer.")
            else: c_loyer.error("Revenus trop faibles pour ce loyer (Garant obligatoire).")
                
            # Calcul de l'épargne cumulée pour la caution
            epargne_totale = df.groupby('Mois').apply(lambda x: x[x['Type']=='Revenu']['Montant'].sum() - x[x['Type']=='Dépense']['Montant'].sum()).sum()
            progress_apport = min(epargne_totale / profil['apport_vise'], 1.0) if profil['apport_vise'] > 0 else 1.0
            c_apport.write(f"Constitution de l'apport : {epargne_totale:.2f} € / {profil['apport_vise']:.2f} €")
            c_apport.progress(progress_apport)

        elif profil['projet_type'] == "Achat ciblé (Véhicule, Matériel...)":
            st.subheader("Progression de l'achat")
            epargne_totale = df.groupby('Mois').apply(lambda x: x[x['Type']=='Revenu']['Montant'].sum() - x[x['Type']=='Dépense']['Montant'].sum()).sum()
            cible = profil['montant_achat']
            
            st.write(f"Fonds sécurisés : {epargne_totale:.2f} € / {cible:.2f} €")
            st.progress(min(epargne_totale / cible, 1.0) if cible > 0 else 1.0)

        elif profil['projet_type'] == "Matelas de sécurité (Épargner sans but précis)":
            st.subheader("Fonds d'urgence")
            cible = profil['salaire_base'] * profil['mois_securite']
            epargne_totale = df.groupby('Mois').apply(lambda x: x[x['Type']=='Revenu']['Montant'].sum() - x[x['Type']=='Dépense']['Montant'].sum()).sum()
            
            st.write(f"Matelas actuel : {epargne_totale:.2f} € / {cible:.2f} € (Objectif : {profil['mois_securite']} mois de salaire)")
            st.progress(min(epargne_totale / cible, 1.0) if cible > 0 else 1.0)

    with tab_transac:
        st.subheader("Ajouter une opération")
        with st.form("ajout_transac"):
            c1, c2, c3, c4 = st.columns(4)
            t_type = c1.selectbox("Type", ["Dépense", "Revenu"])
            t_cat = c2.selectbox("Catégorie", CATEGORIES_BESOINS + CATEGORIES_ENVIES if t_type == "Dépense" else CATEGORIES_REV)
            t_desc = c3.text_input("Libellé détaillé")
            t_montant = c4.number_input("Montant (€)", min_value=0.0, step=1.0)
            if st.form_submit_button("Ajouter la ligne") and t_desc and t_montant > 0:
                add_transaction(datetime.date.today(), t_type, t_cat, t_desc, t_montant)
                st.rerun()
                
        st.dataframe(df_selected[['Date', 'Type', 'Catégorie', 'Description', 'Montant']].sort_values(by="Date", ascending=False), use_container_width=True, hide_index=True)

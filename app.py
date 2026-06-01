import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import calendar
import re
from pypdf import PdfReader
from fpdf import FPDF

# ==========================================
# CONFIGURATION
# ==========================================
st.set_page_config(page_title="Logiciel de Gestion Financière", layout="wide")

# ==========================================
# INITIALISATION DES DONNÉES EN MÉMOIRE
# ==========================================
if 'setup_complete' not in st.session_state:
    st.session_state.setup_complete = False

if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {}

# Initialisation du tableau des charges fixes modifiables
if 'df_charges_fixes' not in st.session_state:
    st.session_state.df_charges_fixes = pd.DataFrame([
        {"Catégorie": "Auto/Transport", "Description": "Assurance Auto", "Montant": 139.0},
        {"Catégorie": "Auto/Transport", "Description": "Carburant", "Montant": 70.0},
        {"Catégorie": "Abonnements", "Description": "Téléphone", "Montant": 10.0}
    ])

if 'transactions' not in st.session_state:
    st.session_state.transactions = pd.DataFrame(columns=["Date", "Mois", "Type", "Catégorie", "Description", "Montant", "Nature"])

if 'closed_months' not in st.session_state:
    st.session_state.closed_months = []

CATEGORIES_BESOINS = ["Logement", "Courses", "Auto/Transport", "Assurances", "Abonnements", "Frais Bancaires", "Santé"]
CATEGORIES_ENVIES = ["Sorties/Loisirs", "Shopping", "Vacances", "Autre"]
CATEGORIES_REV = ["Salaire", "Aides/CAF", "Ventes", "Remboursement", "Autre"]

# ==========================================
# FONCTIONS MÉTIER
# ==========================================
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
    
    new_row = pd.DataFrame([{
        "Date": adjusted_date, "Mois": mois_str, "Type": type_trans, 
        "Catégorie": cat, "Description": desc, "Montant": float(montant), "Nature": nature
    }])
    st.session_state.transactions = pd.concat([st.session_state.transactions, new_row], ignore_index=True)

# ==========================================
# PAGE 1 : ASSISTANT DE CONFIGURATION
# ==========================================
if not st.session_state.setup_complete:
    st.title("Paramétrage de l'espace financier")
    st.write("Définissez votre profil et listez vos flux réguliers pour calibrer l'algorithme.")
    
    col_profil, col_charges = st.columns([1, 1])
    
    with col_profil:
        st.subheader("1. Situation et Objectif")
        salaire = st.number_input("Revenu mensuel principal net (€)", value=970.0, step=10.0)
        personnes = st.number_input("Nombre de personnes dans le foyer", value=1, min_value=1)
        
        projet_type = st.selectbox("Type de projet stratégique", [
            "Indépendance (Logement)", 
            "Épargne de précaution (Matelas de sécurité)",
            "Achat matériel ciblé (Voiture, PC...)", 
            "Remboursement de dette"
        ])
        nom_proj = st.text_input("Intitulé précis du projet", value="Emménagement Vitrolles")
        montant_proj = st.number_input("Montant cible total (€)", value=2000.0, step=100.0)
        mois_proj = st.slider("Délai de réalisation souhaité (mois)", 1, 48, 12)
        
    with col_charges:
        st.subheader("2. Dépenses récurrentes (Charges fixes)")
        st.write("Ajoutez ou modifiez vos lignes de dépenses régulières ci-dessous :")
        edited_charges = st.data_editor(
            st.session_state.df_charges_fixes,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Catégorie": st.column_config.SelectboxColumn("Catégorie", options=CATEGORIES_BESOINS + CATEGORIES_ENVIES, required=True),
                "Description": st.column_config.TextColumn("Description", required=True),
                "Montant": st.column_config.NumberColumn("Montant (€)", min_value=0.0, format="%.2f", required=True)
            }
        )
        total_fixes = edited_charges["Montant"].sum()
        st.info(f"Total de vos charges fixes estimées : {total_fixes:.2f} € / mois")

    epargne_calc = montant_proj / mois_proj if mois_proj > 0 else montant_proj
    
    if st.button("Initialiser le logiciel", type="primary"):
        st.session_state.df_charges_fixes = edited_charges
        st.session_state.user_profile = {
            "salaire_base": salaire,
            "depenses_fixes": total_fixes,
            "foyer": personnes,
            "projet_type": projet_type,
            "nom_projet": nom_proj,
            "montant_projet": montant_proj,
            "mois_pour_projet": mois_proj,
            "epargne_cible": epargne_calc
        }
        st.session_state.setup_complete = True
        st.rerun()

# ==========================================
# PAGE 2 : APPLICATION PRINCIPALE
# ==========================================
else:
    df = st.session_state.transactions.copy()
    current_m = get_current_month_str()
    mois_dispos = sorted(list(set(df['Mois'].tolist() + [current_m])), reverse=True)
    profil = st.session_state.user_profile
    
    # --- BARRE LATÉRALE ---
    st.sidebar.title("Navigation")
    selected_month = st.sidebar.selectbox("Mois de travail", mois_dispos)
    is_closed = selected_month in st.session_state.closed_months
    
    if is_closed:
        st.sidebar.success("Ce mois est clôturé.")
        if st.sidebar.button("Déverrouiller"):
            st.session_state.closed_months.remove(selected_month)
            st.rerun()
    else:
        st.sidebar.warning("Mois en cours.")
        if st.sidebar.button("Clôturer le mois"):
            st.session_state.closed_months.append(selected_month)
            # Reconduction DÉTAILLÉE des charges fixes
            next_month_date = datetime.date.today().replace(day=1) + datetime.timedelta(days=32)
            first_day_next_month = next_month_date.replace(day=1)
            for _, row in st.session_state.df_charges_fixes.iterrows():
                add_transaction(first_day_next_month, "Dépense", row["Catégorie"], f"{row['Description']} (Auto)", row["Montant"])
            st.rerun()
            
    st.sidebar.divider()
    if st.sidebar.button("Ajouter Salaire Mensuel"):
        add_transaction(datetime.date.today(), "Revenu", "Salaire", "Salaire principal", profil["salaire_base"])
        if profil["salaire_base"] >= 1329.0:
            add_transaction(datetime.date.today(), "Revenu", "Aides/CAF", "Aides (Estimation)", 540.0)
        st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("Réinitialiser le profil"):
        st.session_state.setup_complete = False
        st.rerun()

    # --- DONNÉES DU MOIS SÉLECTIONNÉ ---
    df_selected = df[df['Mois'] == selected_month]
    rev_mois = df_selected[df_selected['Type'] == 'Revenu']['Montant'].sum()
    dep_mois = df_selected[df_selected['Type'] == 'Dépense']['Montant'].sum()
    epargne_mois = rev_mois - dep_mois

    # --- ONGLETS PRINCIPAUX ---
    tab_dash, tab_transac, tab_outils = st.tabs(["Tableau de bord", "Registre des opérations", "Import de données"])

    # --- ONGLET 1 : TABLEAU DE BORD ---
    with tab_dash:
        st.title(f"Tableau de bord : {profil['nom_projet']}")
        
        # Bilan Standard
        col1, col2, col3 = st.columns(3)
        col1.metric("Total des Revenus", f"{rev_mois:.2f} €")
        col2.metric("Total des Dépenses", f"{dep_mois:.2f} €")
        col3.metric("Épargne Réalisée", f"{epargne_mois:.2f} €", f"Objectif initial: {profil['epargne_cible']:.2f} €")
        
        st.divider()

        # --- MODULE D'ANALYSE DYNAMIQUE SELON LE PROJET ---
        st.subheader("Analyse Spécifique à votre Projet")
        
        if profil['projet_type'] == "Indépendance (Logement)":
            st.write("Critère clé : Le Taux d'Effort (Loyer et charges sur revenus ne doit pas dépasser 33%).")
            loyer_vise = profil['epargne_cible'] # L'épargne cible représente virtuellement le loyer futur
            taux_effort = (loyer_vise / rev_mois) * 100 if rev_mois > 0 else 100
            
            st.progress(min(taux_effort / 100.0, 1.0))
            if taux_effort <= 33:
                st.success(f"Taux d'effort estimé : {taux_effort:.1f}%. Votre dossier serait accepté par les agences immobilières.")
            else:
                st.error(f"Taux d'effort estimé : {taux_effort:.1f}%. C'est supérieur aux 33% légaux. Il vous faudra un garant solide ou augmenter vos revenus.")

        elif profil['projet_type'] == "Épargne de précaution (Matelas de sécurité)":
            st.write("Critère clé : Règle des 50/30/20 (50% Besoins, 30% Envies, 20% Épargne).")
            if rev_mois > 0:
                dep_besoins = df_selected[df_selected['Nature'] == 'Besoin']['Montant'].sum()
                dep_envies = df_selected[df_selected['Nature'] == 'Envie']['Montant'].sum()
                
                pct_besoins = (dep_besoins / rev_mois) * 100
                pct_envies = (dep_envies / rev_mois) * 100
                pct_epargne = (epargne_mois / rev_mois) * 100
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Besoins (Cible 50%)", f"{pct_besoins:.1f}%", "Ajuster les charges fixes" if pct_besoins > 50 else "Sain", delta_color="inverse" if pct_besoins > 50 else "normal")
                c2.metric("Envies (Cible 30%)", f"{pct_envies:.1f}%", "Réduire les loisirs" if pct_envies > 30 else "Sain", delta_color="inverse" if pct_envies > 30 else "normal")
                c3.metric("Épargne (Cible 20%)", f"{pct_epargne:.1f}%", "Excellent" if pct_epargne >= 20 else "Effort requis")
            else:
                st.info("Attente de saisie des revenus pour le calcul 50/30/20.")

        elif profil['projet_type'] == "Achat matériel ciblé (Voiture, PC...)":
            st.write("Critère clé : Évolution dynamique de la durée restante basée sur votre rythme actuel.")
            df_hist = df.groupby('Mois').apply(lambda x: x[x['Type']=='Revenu']['Montant'].sum() - x[x['Type']=='Dépense']['Montant'].sum()).reset_index(name='Epargne_Nette')
            epargne_cumulee = df_hist['Epargne_Nette'].sum() if not df_hist.empty else 0
            
            reste_a_financer = profil['montant_projet'] - epargne_cumulee
            moyenne_epargne = df_hist['Epargne_Nette'].mean() if not df_hist.empty else epargne_mois
            
            if moyenne_epargne > 0:
                mois_restants = max(0, reste_a_financer / moyenne_epargne)
                st.metric("Délai réestimé", f"{mois_restants:.1f} mois", "Basé sur votre rythme d'épargne réel", delta_color="off")
            else:
                st.warning("Épargne moyenne nulle ou négative. Calcul de projection impossible.")

        elif profil['projet_type'] == "Remboursement de dette":
            st.write("Critère clé : Impact de l'épargne sur le capital restant dû.")
            df_hist = df.groupby('Mois').apply(lambda x: x[x['Type']=='Revenu']['Montant'].sum() - x[x['Type']=='Dépense']['Montant'].sum()).reset_index(name='Epargne_Nette')
            epargne_cumulee = df_hist['Epargne_Nette'].sum() if not df_hist.empty else 0
            
            capital_restant = profil['montant_projet'] - epargne_cumulee
            st.metric("Capital restant à rembourser", f"{max(0, capital_restant):.2f} €")
            st.progress(min(epargne_cumulee / profil['montant_projet'], 1.0) if profil['montant_projet'] > 0 else 1.0)

    # --- ONGLET 2 : REGISTRE DE SAISIE MASSIF ---
    with tab_transac:
        st.subheader("Saisie rapide d'opérations")
        if not is_closed:
            with st.form("ajout_transac"):
                c1, c2, c3, c4 = st.columns(4)
                t_type = c1.selectbox("Type", ["Dépense", "Revenu"])
                t_cat = c2.selectbox("Catégorie", CATEGORIES_BESOINS + CATEGORIES_ENVIES if t_type == "Dépense" else CATEGORIES_REV)
                t_desc = c3.text_input("Libellé détaillé")
                t_montant = c4.number_input("Montant (€)", min_value=0.0, step=1.0)
                if st.form_submit_button("Ajouter la ligne") and t_desc and t_montant > 0:
                    add_transaction(datetime.date.today(), t_type, t_cat, t_desc, t_montant)
                    st.rerun()
        else:
            st.info("Verrouillage actif : Déverrouillez le mois pour ajouter des opérations.")
            
        st.write("Historique du mois")
        st.dataframe(df_selected[['Date', 'Type', 'Catégorie', 'Description', 'Montant', 'Nature']].sort_values(by="Date", ascending=False), use_container_width=True, hide_index=True)

    # --- ONGLET 3 : IMPORT PDF ---
    with tab_outils:
        st.subheader("Analyseur de relevés bancaires automatiques")
        if is_closed:
            st.warning("Impossible d'importer sur un mois clôturé.")
        else:
            uploaded_pdf = st.file_uploader("Format supporté : PDF", type="pdf")
            if uploaded_pdf and st.button("Traiter le document"):
                reader = PdfReader(uploaded_pdf)
                text_ext = "".join([page.extract_text() + "\n" for page in reader.pages])
                pattern = re.compile(r"([A-Za-z0-9\s]+?)\s*([+-]?\d+[\.,]\d{2})")
                
                count = 0
                for match in pattern.findall(text_ext):
                    desc = match[0].strip()
                    val = float(match[1].replace(',', '.'))
                    if val > 0: add_transaction(datetime.date.today(), "Revenu", "Autre", desc, val)
                    elif val < 0: add_transaction(datetime.date.today(), "Dépense", "Autre", desc, abs(val))
                    count += 1
                st.success(f"Analyse terminée. {count} transactions extraites et ajoutées.")
                st.rerun()

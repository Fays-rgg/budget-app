import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import calendar
from pypdf import PdfReader
import re

# ==========================================
# CONFIGURATION DE LA PAGE
# ==========================================
st.set_page_config(page_title="Gestion de Budget", layout="wide")

# ==========================================
# INITIALISATION DES DONNÉES (SESSION STATE)
# ==========================================
if 'setup_complete' not in st.session_state:
    st.session_state.setup_complete = False

if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {
        "salaire_base": 970.0,
        "depenses_fixes": 219.0,
        "nom_projet": "Emménagement Vitrolles",
        "montant_projet": 2000.0,
        "mois_pour_projet": 12,
        "epargne_mensuelle_cible": 166.67
    }

CATEGORIES_DEP = ["Courses", "Auto/Transport", "Sorties/Loisirs", "Logement", "Abonnements", "Frais Bancaires", "Autre"]
CATEGORIES_REV = ["Salaire", "Vente", "Aides (CAF)", "Autre"]

if 'transactions' not in st.session_state:
    initial_data = [
        {"Date": datetime.date.today().replace(day=5), "Type": "Dépense", "Catégorie": "Auto/Transport", "Description": "Assurance & Essence", "Montant": 219.0},
    ]
    st.session_state.transactions = pd.DataFrame(initial_data)

# ==========================================
# FONCTIONS MÉTIER
# ==========================================
def apply_rule_28(date_obj):
    """Règle du 28 : Les revenus fin de mois comptent pour le mois suivant."""
    if date_obj.day >= 25:
        if date_obj.month == 12: return datetime.date(date_obj.year + 1, 1, 1)
        else: return datetime.date(date_obj.year, date_obj.month + 1, 1)
    return date_obj

def add_transaction(date, type_trans, cat, desc, montant):
    adjusted_date = apply_rule_28(date) if type_trans == "Revenu" else date
    new_row = pd.DataFrame([{"Date": adjusted_date, "Type": type_trans, "Catégorie": cat, "Description": desc, "Montant": float(montant)}])
    st.session_state.transactions = pd.concat([st.session_state.transactions, new_row], ignore_index=True)

def days_left_in_month():
    today = datetime.date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    return days_in_month - today.day + 1

# ==========================================
# PAGE 1 : ASSISTANT DE CONFIGURATION
# ==========================================
if not st.session_state.setup_complete:
    st.title("Configuration du profil financier")
    st.write("Veuillez définir vos paramètres de base pour calibrer le tableau de bord.")
    
    with st.form("setup_form"):
        st.subheader("Revenus")
        salaire = st.number_input("Salaire mensuel net actuel (€)", value=st.session_state.user_profile["salaire_base"], step=10.0)
        
        st.subheader("Charges fixes")
        fixes = st.number_input("Montant total des frais fixes incontournables (€)", value=st.session_state.user_profile["depenses_fixes"], step=10.0)
        
        st.subheader("Objectif principal")
        col1, col2 = st.columns(2)
        nom_proj = col1.text_input("Nom du projet", value=st.session_state.user_profile["nom_projet"])
        montant_proj = col2.number_input("Montant total ciblé (€)", value=st.session_state.user_profile["montant_projet"], step=100.0)
        
        mois_proj = st.slider("Durée de réalisation (mois)", min_value=1, max_value=36, value=st.session_state.user_profile["mois_pour_projet"])
        
        epargne_calc = montant_proj / mois_proj if mois_proj > 0 else montant_proj
        st.info(f"Objectif : {montant_proj} € en {mois_proj} mois. Épargne requise : {epargne_calc:.2f} € / mois.")
        
        submitted = st.form_submit_button("Valider et générer le tableau de bord")
        if submitted:
            st.session_state.user_profile = {
                "salaire_base": salaire,
                "depenses_fixes": fixes,
                "nom_projet": nom_proj,
                "montant_projet": montant_proj,
                "mois_pour_projet": mois_proj,
                "epargne_mensuelle_cible": epargne_calc
            }
            st.session_state.setup_complete = True
            st.rerun()

# ==========================================
# PAGE 2 : APPLICATION PRINCIPALE
# ==========================================
else:
    df = st.session_state.transactions.copy()
    df['Mois'] = pd.to_datetime(df['Date']).dt.to_period('M').astype(str)
    current_month_str = datetime.date.today().strftime('%Y-%m')
    
    # --- BARRE LATÉRALE ---
    st.sidebar.title("Menu")
    if st.sidebar.button("Modifier le profil"):
        st.session_state.setup_complete = False
        st.rerun()
        
    st.sidebar.divider()
    st.sidebar.subheader("Actions rapides")
    if st.sidebar.button("Ajouter le salaire du mois"):
        add_transaction(datetime.date.today(), "Revenu", "Salaire", "Salaire Alternance", st.session_state.user_profile["salaire_base"])
        if st.session_state.user_profile["salaire_base"] >= 1329.00:
            add_transaction(datetime.date.today(), "Revenu", "Aides (CAF)", "Prime d'Activité estimée", 210.0)
            add_transaction(datetime.date.today(), "Revenu", "Aides (CAF)", "APL estimée", 330.0)
            st.sidebar.success("Salaire et aides ajoutés.")
        else:
            st.sidebar.success("Salaire ajouté.")
            
    st.sidebar.divider()
    st.sidebar.subheader("Simulation")
    simulateur_on = st.sidebar.toggle("Activer mode 'Indépendance'")
    if simulateur_on:
        st.sidebar.warning("Simulation active : +750€ de charges fictives appliquées au calcul du reste à vivre.")

    # --- ONGLETS PRINCIPAUX ---
    tab_dash, tab_rev, tab_dep = st.tabs(["Tableau de bord", "Entrées", "Sorties"])

    # --- ONGLET 1 : TABLEAU DE BORD ---
    with tab_dash:
        st.title(f"Projet : {st.session_state.user_profile['nom_projet']}")
        
        df_current = df[df['Mois'] == current_month_str]
        rev_mois = df_current[df_current['Type'] == 'Revenu']['Montant'].sum()
        dep_mois = df_current[df_current['Type'] == 'Dépense']['Montant'].sum()
        
        if simulateur_on:
            dep_mois += 750.0 
            
        epargne_cible = st.session_state.user_profile["epargne_mensuelle_cible"]
        reste_a_vivre_total = rev_mois - st.session_state.user_profile["depenses_fixes"] - dep_mois - epargne_cible
        
        jours_restants = days_left_in_month()
        budget_jour = reste_a_vivre_total / jours_restants if jours_restants > 0 else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Reste à vivre global (Mois courant)", f"{reste_a_vivre_total:.2f} €")
        with col2:
            st.metric("Budget journalier autorisé", f"{budget_jour:.2f} € / jour")
        with col3:
            st.metric(f"Épargne cible ({st.session_state.user_profile['mois_pour_projet']} mois)", f"{epargne_cible:.2f} € / mois")

        st.divider()
        
        col_g1, col_g2 = st.columns([1, 1])
        with col_g1:
            st.subheader("Répartition des dépenses")
            df_dep_current = df_current[df_current['Type'] == 'Dépense']
            if simulateur_on:
                df_fake = pd.DataFrame([
                    {"Catégorie": "Logement", "Montant": 550.0},
                    {"Catégorie": "Courses", "Montant": 200.0}
                ])
                df_dep_current = pd.concat([df_dep_current, df_fake])
                
            if not df_dep_current.empty:
                # Graphique sobre et épuré
                fig_donut = px.pie(df_dep_current, values='Montant', names='Catégorie', hole=0.6, color_discrete_sequence=px.colors.sequential.Teal)
                fig_donut.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=True)
                st.plotly_chart(fig_donut, use_container_width=True)
            else:
                st.info("Données insuffisantes.")
                
        with col_g2:
            st.subheader("Progression de l'épargne")
            total_rev = df[df['Type'] == 'Revenu']['Montant'].sum()
            total_dep = df[df['Type'] == 'Dépense']['Montant'].sum()
            epargne_reelle = total_rev - total_dep
            
            cible_totale = st.session_state.user_profile['montant_projet']
            progress = min(epargne_reelle / cible_totale, 1.0) if cible_totale > 0 else 0
            if progress < 0: progress = 0.0
            
            st.progress(progress)
            st.write(f"Montant sécurisé : **{epargne_reelle:.2f} €** / {cible_totale:.2f} € ({(progress*100):.1f}%)")
            
            if progress >= 1.0:
                st.success("Statut : Objectif financier atteint.")
            else:
                st.warning("Statut : Phase d'épargne en cours.")

    # --- ONGLET 2 : REVENUS ---
    with tab_rev:
        st.subheader("Saisie d'un revenu")
        with st.form("form_rev"):
            c1, c2, c3 = st.columns(3)
            cat_rev = c1.selectbox("Catégorie", CATEGORIES_REV)
            desc_rev = c2.text_input("Description")
            montant_rev = c3.number_input("Montant (€)", min_value=0.0, step=1.0)
            if st.form_submit_button("Enregistrer") and desc_rev and montant_rev > 0:
                add_transaction(datetime.date.today(), "Revenu", cat_rev, desc_rev, montant_rev)
                st.rerun()
                
        st.dataframe(df[df['Type'] == 'Revenu'][['Date', 'Catégorie', 'Description', 'Montant']].sort_values(by="Date", ascending=False), use_container_width=True, hide_index=True)

    # --- ONGLET 3 : DÉPENSES & PDF ---
    with tab_dep:
        st.subheader("Saisie d'une dépense")
        with st.form("form_dep"):
            c1, c2, c3 = st.columns(3)
            cat_dep = c1.selectbox("Catégorie", CATEGORIES_DEP)
            desc_dep = c2.text_input("Description")
            montant_dep = c3.number_input("Montant (€)", min_value=0.0, step=1.0)
            if st.form_submit_button("Enregistrer") and desc_dep and montant_dep > 0:
                add_transaction(datetime.date.today(), "Dépense", cat_dep, desc_dep, montant_dep)
                st.rerun()

        with st.expander("Importation depuis relevé bancaire (PDF)"):
            uploaded_pdf = st.file_uploader("Sélectionner un fichier PDF", type="pdf")
            if uploaded_pdf and st.button("Lancer l'analyse"):
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
                st.success(f"Analyse terminée : {count} opérations ajoutées.")
                st.rerun()

        st.dataframe(df[df['Type'] == 'Dépense'][['Date', 'Catégorie', 'Description', 'Montant']].sort_values(by="Date", ascending=False), use_container_width=True, hide_index=True)

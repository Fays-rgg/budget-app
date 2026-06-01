import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime
from io import BytesIO
from pypdf import PdfReader
import re

# ==========================================
# CONFIGURATION DE LA PAGE
# ==========================================
st.set_page_config(page_title="Budget Alternant -> Emménagement", page_icon="🚀", layout="wide")

# ==========================================
# INITIALISATION DES DONNÉES (SESSION STATE)
# ==========================================
# On initialise un registre de transactions s'il n'existe pas encore
if 'transactions' not in st.session_state:
    # On pré-remplit avec tes données de base (Mai 2026)
    initial_data = [
        {"Date": datetime.date(2026, 5, 5), "Type": "Dépense", "Description": "Assurance Auto", "Montant": 139.0},
        {"Date": datetime.date(2026, 5, 10), "Type": "Dépense", "Description": "Carburant", "Montant": 70.0},
        {"Date": datetime.date(2026, 5, 15), "Type": "Dépense", "Description": "Téléphone", "Montant": 10.0}
    ]
    st.session_state.transactions = pd.DataFrame(initial_data)

# ==========================================
# FONCTIONS MÉTIER (LOGIQUE DE L'APP)
# ==========================================
def apply_rule_28(date_obj):
    """
    Règle de Gestion : Si la date est entre le 25 et le 31,
    on bascule la transaction au 1er du mois suivant.
    """
    if date_obj.day >= 25:
        if date_obj.month == 12:
            return datetime.date(date_obj.year + 1, 1, 1)
        else:
            return datetime.date(date_obj.year, date_obj.month + 1, 1)
    return date_obj

def add_transaction(date, type_trans, desc, montant):
    """Ajoute une transaction au registre après application de la règle du 28."""
    adjusted_date = apply_rule_28(date)
    new_row = pd.DataFrame([{
        "Date": adjusted_date, 
        "Type": type_trans, 
        "Description": desc, 
        "Montant": float(montant)
    }])
    st.session_state.transactions = pd.concat([st.session_state.transactions, new_row], ignore_index=True)

# ==========================================
# BARRE LATÉRALE (SIMULATEUR ET PARAMÈTRES)
# ==========================================
st.sidebar.title("⚙️ Paramètres & Simulateur")

st.sidebar.subheader("Évolution Légale (Salaire)")
is_year_2 = st.sidebar.checkbox("Passage en 2ème année d'alternance")
is_21_yo = st.sidebar.checkbox("J'ai fêté mes 21 ans (Décembre 2026)")

# Détermination du salaire de base en fonction des cases cochées
base_salary = 970.00
if is_21_yo:
    base_salary = 1329.54
elif is_year_2:
    base_salary = 1159.26

st.sidebar.info(f"💶 Salaire de base actuel estimé : **{base_salary:.2f} €**")

# Bouton Dette (Optionnel, désactivé par défaut comme demandé)
enable_debt = st.sidebar.checkbox("Activer un plan de remboursement de prêt (Optionnel)")
if enable_debt:
    st.sidebar.warning("⚠️ Plan de remboursement activé. Pense à ajouter ta mensualité dans les dépenses.")

# Ajout du salaire mensuel pour le mois en cours
if st.sidebar.button("Ajouter le salaire ce mois-ci"):
    add_transaction(datetime.date.today(), "Revenu", "Salaire Alternance", base_salary)
    # Calculateur CAF Automatique (Se déclenche si le salaire est à la tranche des 21 ans)
    if base_salary == 1329.54:
        add_transaction(datetime.date.today(), "Revenu", "Prime d'Activité (CAF)", 210.00)
        add_transaction(datetime.date.today(), "Revenu", "APL (CAF)", 330.00)
        st.sidebar.success("Aides CAF ajoutées automatiquement !")

# ==========================================
# INTERFACE PRINCIPALE (ONGLETS)
# ==========================================
st.title("📊 Gestion de Budget & Projet Vitrolles")

tab_rev, tab_dep, tab_dash = st.tabs(["🟢 Revenus", "🔴 Dépenses", "🚀 Dashboard"])

# Préparation des données pour l'affichage (Extraction du mois/année pour grouper)
df = st.session_state.transactions.copy()
df['Mois'] = pd.to_datetime(df['Date']).dt.to_period('M').astype(str)

# --- ONGLET 1 : REVENUS ---
with tab_rev:
    st.header("Entrées d'argent")
    
    # Formulaire "Vente Flash"
    with st.expander("⚡ Ajouter une Vente Flash (Vinted, Leboncoin, etc.)"):
        with st.form("flash_sale"):
            col1, col2 = st.columns(2)
            sale_name = col1.text_input("Nom de la vente")
            sale_amount = col2.number_input("Montant (€)", min_value=0.0, step=1.0)
            submitted = st.form_submit_button("Ajouter")
            if submitted and sale_name and sale_amount > 0:
                add_transaction(datetime.date.today(), "Revenu", sale_name, sale_amount)
                st.rerun()

    # Tableau des revenus
    df_rev = df[df['Type'] == 'Revenu']
    if not df_rev.empty:
        # Pivot table pour avoir les mois en colonnes
        pivot_rev = df_rev.pivot_table(index='Description', columns='Mois', values='Montant', aggfunc='sum', fill_value=0)
        st.dataframe(pivot_rev, use_container_width=True)
    else:
        st.info("Aucun revenu enregistré pour le moment.")

# --- ONGLET 2 : DÉPENSES ---
with tab_dep:
    st.header("Sorties d'argent")
    
    # Analyseur de Relevé de Compte PDF
    st.subheader("📄 Analyseur de Relevé Bancaire")
    st.write("Uploade un relevé PDF. L'algorithme détectera les montants pour les classer.")
    uploaded_pdf = st.file_uploader("Choisir un fichier PDF", type="pdf")
    
    if uploaded_pdf is not None:
        if st.button("Analyser le PDF"):
            reader = PdfReader(uploaded_pdf)
            text_extracted = ""
            for page in reader.pages:
                text_extracted += page.extract_text() + "\n"
            
            # Algorithme basique d'extraction (Expression Régulière)
            # Cherche des lignes avec des montants (ex: "Boulangerie -4.50" ou "Virement +150.00")
            # Note pour l'utilisateur : C'est une simulation simplifiée. Les vrais relevés nécessitent un regex complexe.
            pattern = re.compile(r"([A-Za-z0-9\s]+?)\s*([+-]?\d+[\.,]\d{2})")
            matches = pattern.findall(text_extracted)
            
            added_count = 0
            for match in matches:
                desc = match[0].strip()
                montant_str = match[1].replace(',', '.')
                montant = float(montant_str)
                
                if montant > 0:
                    add_transaction(datetime.date.today(), "Revenu", desc, montant)
                elif montant < 0:
                    add_transaction(datetime.date.today(), "Dépense", desc, abs(montant))
                added_count += 1
            
            st.success(f"{added_count} transactions identifiées et ajoutées au registre !")
            st.rerun()

    # Tableau des dépenses
    df_dep = df[df['Type'] == 'Dépense']
    if not df_dep.empty:
        pivot_dep = df_dep.pivot_table(index='Description', columns='Mois', values='Montant', aggfunc='sum', fill_value=0)
        st.dataframe(pivot_dep, use_container_width=True)
    else:
        st.info("Aucune dépense enregistrée.")

# --- ONGLET 3 : DASHBOARD ---
with tab_dash:
    st.header("Visualisation & Objectif Vitrolles")
    
    # Calculs globaux
    total_revenus = df[df['Type'] == 'Revenu']['Montant'].sum()
    total_depenses = df[df['Type'] == 'Dépense']['Montant'].sum()
    epargne_cumulee = total_revenus - total_depenses
    
    # Calcul des revenus du mois en cours (pour le trigger Feu Vert)
    current_month = datetime.date.today().strftime('%Y-%m')
    revenus_du_mois = df[(df['Type'] == 'Revenu') & (df['Mois'] == current_month)]['Montant'].sum()
    
    # --- SYSTÈME DE TRIGGERS ---
    # Objectifs : Epargne >= 2000 € ET Revenus du mois >= 2300 €
    if epargne_cumulee >= 2000 and revenus_du_mois >= 2300:
        st.success("### 🚀 FEU VERT EMMÉNAGEMENT ! \nFélicitations ! Tu as l'épargne nécessaire pour la caution/meubles et le revenu mensuel pour rassurer le propriétaire.")
    else:
        st.warning(f"### 🐜 Mode Fourmi Activé \nContinue d'épargner ! \n- **Épargne actuelle** : {epargne_cumulee:.2f} € / 2 000.00 € \n- **Revenus ce mois-ci** : {revenus_du_mois:.2f} € / 2 300.00 €")
    
    st.divider()

    # --- GRAPHIQUE COMBINÉ ---
    # On groupe les données par mois
    df_monthly = df.groupby(['Mois', 'Type'])['Montant'].sum().unstack(fill_value=0).reset_index()
    
    # Si le tableau est vide (manque de données de revenus ou dépenses), on le sécurise
    if 'Revenu' not in df_monthly.columns:
        df_monthly['Revenu'] = 0.0
    if 'Dépense' not in df_monthly.columns:
        df_monthly['Dépense'] = 0.0
        
    df_monthly['Benefice Net'] = df_monthly['Revenu'] - df_monthly['Dépense']
    
    fig = go.Figure()
    # Barres pour les revenus (Vert)
    fig.add_trace(go.Bar(x=df_monthly['Mois'], y=df_monthly['Revenu'], name='Revenus', marker_color='#2ca02c'))
    # Barres pour les dépenses (Rouge)
    fig.add_trace(go.Bar(x=df_monthly['Mois'], y=df_monthly['Dépense'], name='Dépenses', marker_color='#d62728'))
    # Courbe pour le bénéfice net (Jaune)
    fig.add_trace(go.Scatter(x=df_monthly['Mois'], y=df_monthly['Benefice Net'], name='Bénéfice Net', mode='lines+markers', line=dict(color='#ff7f0e', width=3)))
    
    fig.update_layout(title="Évolution de la santé financière par mois", barmode='group', xaxis_title="Mois", yaxis_title="Montant (€)")
    st.plotly_chart(fig, use_container_width=True)
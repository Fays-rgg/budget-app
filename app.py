import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import calendar
import re
import io
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

if 'transactions' not in st.session_state:
    st.session_state.transactions = pd.DataFrame(columns=["Date", "Mois", "Type", "Catégorie", "Description", "Montant", "Nature"])

if 'closed_months' not in st.session_state:
    st.session_state.closed_months = []

CATEGORIES_BESOINS = ["Logement", "Courses", "Auto/Transport", "Assurances/Abonnements", "Frais Bancaires", "Santé"]
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
    # La règle du 28 s'applique uniquement aux revenus
    adjusted_date = apply_rule_28(date_obj) if type_trans == "Revenu" else date_obj
    mois_str = adjusted_date.strftime('%Y-%m')
    
    # Classification Besoin vs Envie (pour l'algorithme)
    nature = "Besoin" if cat in CATEGORIES_BESOINS else ("Envie" if cat in CATEGORIES_ENVIES else "Revenu")
    
    new_row = pd.DataFrame([{
        "Date": adjusted_date, "Mois": mois_str, "Type": type_trans, 
        "Catégorie": cat, "Description": desc, "Montant": float(montant), "Nature": nature
    }])
    st.session_state.transactions = pd.concat([st.session_state.transactions, new_row], ignore_index=True)

def generate_pdf_report(mois_str, df_mois, epargne, budget_restant):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"Rapport Financier Mensuel - {mois_str}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"Bilan : Epargne du mois = {epargne:.2f} EUR | Budget non alloue = {budget_restant:.2f} EUR", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(40, 8, "Date", border=1)
    pdf.cell(30, 8, "Type", border=1)
    pdf.cell(50, 8, "Categorie", border=1)
    pdf.cell(50, 8, "Description", border=1)
    pdf.cell(20, 8, "Montant", border=1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 10)
    for _, row in df_mois.iterrows():
        pdf.cell(40, 8, str(row['Date']), border=1)
        pdf.cell(30, 8, row['Type'], border=1)
        pdf.cell(50, 8, str(row['Catégorie'])[:20], border=1)
        pdf.cell(50, 8, str(row['Description'])[:20], border=1)
        pdf.cell(20, 8, f"{row['Montant']:.2f}", border=1)
        pdf.ln()
        
    return pdf.output(dest='S').encode('latin1')

# ==========================================
# PAGE 1 : ASSISTANT DE CONFIGURATION
# ==========================================
if not st.session_state.setup_complete:
    st.title("Paramétrage de l'espace financier")
    st.write("Définissez votre profil pour calibrer les algorithmes de prédiction et d'analyse.")
    
    with st.form("setup_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Situation actuelle")
            salaire = st.number_input("Revenu mensuel principal net (€)", value=970.0, step=10.0)
            fixes = st.number_input("Charges fixes incompressibles actuelles (€)", value=219.0, step=10.0)
            personnes = st.number_input("Nombre de personnes dans le foyer", value=1, min_value=1)
        
        with col2:
            st.subheader("Objectif stratégique")
            projet_type = st.selectbox("Type de projet", [
                "Indépendance (Logement)", 
                "Achat matériel (Voiture, PC...)", 
                "Épargne de précaution (Matelas de sécurité)",
                "Remboursement de dette"
            ])
            nom_proj = st.text_input("Intitulé précis du projet", value="Emménagement Vitrolles")
            montant_proj = st.number_input("Montant cible total (€)", value=2000.0, step=100.0)
            mois_proj = st.slider("Délai de réalisation (mois)", 1, 48, 12)
        
        epargne_calc = montant_proj / mois_proj if mois_proj > 0 else montant_proj
        st.info(f"Effort d'épargne calculé : {epargne_calc:.2f} € / mois.")
        
        if st.form_submit_button("Initialiser le logiciel"):
            st.session_state.user_profile = {
                "salaire_base": salaire,
                "depenses_fixes": fixes,
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
    
    # Identification des mois disponibles (Mois actuel par défaut)
    current_m = get_current_month_str()
    mois_dispos = sorted(list(set(df['Mois'].tolist() + [current_m])), reverse=True)
    
    # --- BARRE LATÉRALE ---
    st.sidebar.title("Navigation")
    selected_month = st.sidebar.selectbox("Mois de travail", mois_dispos)
    is_closed = selected_month in st.session_state.closed_months
    
    if is_closed:
        st.sidebar.success("🔒 Ce mois est clôturé.")
        if st.sidebar.button("Déverrouiller le mois"):
            st.session_state.closed_months.remove(selected_month)
            st.rerun()
    else:
        st.sidebar.warning("🔓 Mois en cours.")
        if st.sidebar.button("Clôturer le mois"):
            st.session_state.closed_months.append(selected_month)
            # Reconduction des charges fixes vers le mois suivant
            next_month_date = datetime.date.today().replace(day=1) + datetime.timedelta(days=32)
            add_transaction(next_month_date.replace(day=1), "Dépense", "Assurances/Abonnements", "Charges fixes automatiques", st.session_state.user_profile["depenses_fixes"])
            st.rerun()
            
    st.sidebar.divider()
    
    # CONSEILLER DYNAMIQUE
    st.sidebar.subheader("Conseiller Algorithmique")
    df_selected = df[df['Mois'] == selected_month]
    rev_tot = df_selected[df_selected['Type'] == 'Revenu']['Montant'].sum()
    dep_envies = df_selected[df_selected['Nature'] == 'Envie']['Montant'].sum()
    
    if rev_tot > 0:
        ratio_envies = (dep_envies / rev_tot) * 100
        if ratio_envies > 30:
            st.sidebar.error(f"Alerte : Vos dépenses 'Plaisir' atteignent {ratio_envies:.1f}% de vos revenus. La norme recommandée est de 30% maximum.")
        else:
            st.sidebar.success(f"Ratio dépenses variables sain ({ratio_envies:.1f}%).")
            
        epargne_reelle = rev_tot - df_selected[df_selected['Type'] == 'Dépense']['Montant'].sum()
        cible = st.session_state.user_profile['epargne_cible']
        if epargne_reelle > cible + 50 and not is_closed:
            st.sidebar.info(f"Suggestion : Vous avez un excédent de {epargne_reelle - cible:.2f} €. Envisagez de les virer sur votre compte épargne avant de clôturer.")

    st.sidebar.divider()
    if st.sidebar.button("Réinitialiser le profil complet"):
        st.session_state.setup_complete = False
        st.rerun()

    # --- ONGLETS PRINCIPAUX ---
    tab_dash, tab_transac, tab_outils = st.tabs(["Tableau de bord", "Registre des opérations", "Import / Export"])

    # --- ONGLET 1 : TABLEAU DE BORD ---
    with tab_dash:
        st.title(f"Suivi : {st.session_state.user_profile['nom_projet']}")
        
        rev_mois = rev_tot
        dep_mois = df_selected[df_selected['Type'] == 'Dépense']['Montant'].sum()
        epargne_mois = rev_mois - dep_mois
        cible = st.session_state.user_profile["epargne_cible"]
        reste_a_vivre = rev_mois - st.session_state.user_profile["depenses_fixes"] - cible - (dep_mois - st.session_state.user_profile["depenses_fixes"])
        
        # Affichage des KPIs
        col1, col2, col3 = st.columns(3)
        col1.metric("Revenus du mois", f"{rev_mois:.2f} €")
        col2.metric("Dépenses du mois", f"{dep_mois:.2f} €")
        col3.metric("Bilan (Épargne générée)", f"{epargne_mois:.2f} €", f"Cible: {cible:.2f} €", delta_color="normal" if epargne_mois >= cible else "inverse")

        st.divider()
        
        # Donut Chart & Prédiction
        col_g1, col_g2 = st.columns([1, 1.5])
        
        with col_g1:
            st.write("**Répartition des charges (Besoins vs Envies)**")
            df_dep = df_selected[df_selected['Type'] == 'Dépense']
            if not df_dep.empty:
                fig_donut = px.pie(df_dep, values='Montant', names='Catégorie', hole=0.5, color='Nature', color_discrete_map={'Besoin': '#2C3E50', 'Envie': '#E74C3C'})
                fig_donut.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_donut, use_container_width=True)
            else:
                st.info("Aucune donnée pour ce mois.")
                
        with col_g2:
            st.write("**Projection vers l'objectif**")
            # Calcul cumulé
            df_hist = df.groupby('Mois').apply(lambda x: x[x['Type']=='Revenu']['Montant'].sum() - x[x['Type']=='Dépense']['Montant'].sum()).reset_index(name='Epargne_Nette')
            df_hist = df_hist.sort_values('Mois')
            df_hist['Cumul'] = df_hist['Epargne_Nette'].cumsum()
            
            # Prédiction basique
            fig_proj = go.Figure()
            if not df_hist.empty:
                current_cumul = df_hist['Cumul'].iloc[-1]
                moyenne_epargne = df_hist['Epargne_Nette'].mean()
                if moyenne_epargne <= 0: moyenne_epargne = cible
                
                # Génération des points futurs
                future_months = [f"Mois +{i}" for i in range(1, 6)]
                future_vals = [current_cumul + (moyenne_epargne * i) for i in range(1, 6)]
                
                fig_proj.add_trace(go.Scatter(x=df_hist['Mois'], y=df_hist['Cumul'], mode='lines+markers', name='Épargne Réelle', line=dict(color='#27AE60', width=3)))
                fig_proj.add_trace(go.Scatter(x=[df_hist['Mois'].iloc[-1]] + future_months, y=[current_cumul] + future_vals, mode='lines', name='Prédiction', line=dict(color='#7F8C8D', width=2, dash='dash')))
                fig_proj.add_hline(y=st.session_state.user_profile['montant_projet'], line_dash="dot", annotation_text="Objectif", annotation_position="top right")
                
            fig_proj.update_layout(margin=dict(t=20, b=0, l=0, r=0), plot_bgcolor='rgba(0,0,0,0)', yaxis_title="Montant Cumulé (€)")
            st.plotly_chart(fig_proj, use_container_width=True)

    # --- ONGLET 2 : REGISTRE ---
    with tab_transac:
        st.subheader(f"Opérations de {selected_month}")
        
        if not is_closed:
            with st.form("ajout_transac"):
                c1, c2, c3, c4 = st.columns(4)
                t_type = c1.selectbox("Type", ["Dépense", "Revenu"])
                # Logique pour adapter la liste de catégories
                t_cat = c2.selectbox("Catégorie", CATEGORIES_BESOINS + CATEGORIES_ENVIES if t_type == "Dépense" else CATEGORIES_REV)
                t_desc = c3.text_input("Libellé")
                t_montant = c4.number_input("Montant (€)", min_value=0.0, step=1.0)
                if st.form_submit_button("Ajouter l'opération") and t_desc and t_montant > 0:
                    add_transaction(datetime.date.today(), t_type, t_cat, t_desc, t_montant)
                    st.rerun()
        else:
            st.info("Saisie désactivée : Ce mois est clôturé.")
            
        st.dataframe(df_selected[['Date', 'Type', 'Catégorie', 'Description', 'Montant', 'Nature']].sort_values(by="Date", ascending=False), use_container_width=True, hide_index=True)

    # --- ONGLET 3 : IMPORT / EXPORT ---
    with tab_outils:
        col_import, col_export = st.columns(2)
        
        with col_import:
            st.subheader("Analyseur de relevé bancaire")
            if is_closed:
                st.warning("Impossible d'importer sur un mois clôturé.")
            else:
                uploaded_pdf = st.file_uploader("Importer un fichier PDF", type="pdf")
                if uploaded_pdf and st.button("Lancer l'extraction"):
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
                    st.success(f"{count} lignes importées avec succès.")
                    st.rerun()
                    
        with col_export:
            st.subheader("Générateur de rapport")
            st.write("Éditer une version imprimable du mois sélectionné.")
            if st.button("Préparer le rapport PDF"):
                pdf_bytes = generate_pdf_report(selected_month, df_selected, epargne_mois, reste_a_vivre)
                st.download_button(
                    label="📥 Télécharger le fichier PDF",
                    data=pdf_bytes,
                    file_name=f"Rapport_Financier_{selected_month}.pdf",
                    mime="application/pdf"
                )

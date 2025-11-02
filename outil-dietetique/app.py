
import os, uuid, datetime as dt
import pandas as pd
import streamlit as st
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------------- CONFIGURATION ----------------
st.set_page_config(page_title="Outil diététique – Fiches clients", page_icon="🥗", layout="wide")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CSV_PATH = os.path.join(DATA_DIR, "clients.csv")
os.makedirs(DATA_DIR, exist_ok=True)

COLUMNS = [
    "id","date_creation","date_maj","nom","prenom","sexe","age",
    "taille_cm","poids_kg","poids_initial_kg","objectif","sport","seances_semaine",
    "grignote","repas_par_jour","aliments_ok","aliments_ko","allergies","antecedents",
    "traitements","tabac","alcool","digestion","appetit",
    "imc","imc_cat","dej_mj","dej_kcal","pct_perte_prise"
]

# ---------------- TABLE SIMPLIFIÉE DES ALIMENTS ----------------
ALIMENTS = {
    "Lait 1/2 écrémé": {"P": 3, "L": 2, "G": 5},
    "Yaourt nature": {"P": 5, "L": 2, "G": 6},
    "Fromage (moyenne)": {"P": 22, "L": 28, "G": 0},
    "VPO (viande/poisson/œuf)": {"P": 18, "L": 10, "G": 0},
    "Pain": {"P": 9, "L": 1.5, "G": 55},
    "Céréales (crues)": {"P": 10, "L": 2, "G": 75},
    "Légumineuses": {"P": 25, "L": 1, "G": 50},
    "Pomme de terre": {"P": 2, "L": 0, "G": 16},
    "Légumes (cuits/crus)": {"P": 2, "L": 0, "G": 6},
    "Fruits": {"P": 1, "L": 0, "G": 12},
    "Beurre": {"P": 0, "L": 82, "G": 0},
    "Huile": {"P": 0, "L": 100, "G": 0},
    "Graines oléagineuses": {"P": 20, "L": 60, "G": 10},
    "Sucre": {"P": 0, "L": 0, "G": 100},
    "Confiture": {"P": 0, "L": 0, "G": 60},
}

# ---------------- OUTILS ----------------
def load_df():
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = None
        return df[COLUMNS]
    else:
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(CSV_PATH, index=False)
        return df

def save_df(df):
    df.to_csv(CSV_PATH, index=False)

def compute_imc(poids, taille_cm):
    if not poids or not taille_cm or taille_cm <= 0:
        return None, None
    taille_m = taille_cm / 100
    imc = poids / (taille_m ** 2)
    if imc < 18.5:
        cat = "Insuffisance pondérale"
    elif imc < 25:
        cat = "Corpulence normale"
    elif imc < 30:
        cat = "Surpoids"
    else:
        cat = "Obésité"
    return round(imc, 2), cat

def compute_dej(sexe, poids, taille_cm, age):
    if not all([sexe, poids, taille_cm, age]) or min(poids, taille_cm, age) <= 0:
        return None, None
    taille_m = taille_cm / 100.0
    if str(sexe).lower().startswith("f"):
        dej_mj = 0.963 * (poids ** 0.48) * (taille_m ** 0.50) * (age ** -0.13)
    else:
        dej_mj = 1.083 * (poids ** 0.48) * (taille_m ** 0.50) * (age ** -0.13)
    dej_kcal = dej_mj * 238.8459
    nap = 1.63  # NAP moyen ajouté
    return round(dej_mj * nap, 3), round(dej_kcal * nap, 0)

def pct_perte_prise(p0, p):
    if not p0 or not p or p0 <= 0:
        return None
    return round(((p0 - p) / p0) * 100, 2)

def sort_alpha(df):
    return df.sort_values(["nom", "prenom"], key=lambda s: s.str.lower(), na_position="last").reset_index(drop=True)

# ---------------- PDF ----------------
def generate_pdf(client):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * 72, 27 * 28, "Fiche client diététique")
    c.setFont("Helvetica", 11)
    y = 25.5 * 28

    def line(label, value):
        nonlocal y
        c.drawString(60, y, f"{label}: {value}")
        y -= 18

    line("Nom", f"{client['nom']} {client['prenom']}")
    line("Sexe", client['sexe'])
    line("Âge", client['age'])
    line("Taille (cm)", client['taille_cm'])
    line("Poids (kg)", client['poids_kg'])
    line("IMC", f"{client['imc']} ({client['imc_cat']})")
    line("DEJ (kcal)", client['dej_kcal'])
    line("Objectif", client['objectif'])
    line("Sport", client['sport'])
    line("Séances/semaine", client['seances_semaine'])
    line("Grignote", client['grignote'])
    line("Digestion", client['digestion'])
    line("Appétit", client['appetit'])
    line("Date mise à jour", client['date_maj'])

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# ---------------- PAGES ----------------
st.sidebar.title("🥗 Outil diététique")
page = st.sidebar.radio("Aller à :", [
    "Ajouter / Éditer",
    "Liste (A→Z)",
    "Calcul rapide",
    "💪 Calcul de ration"
])

# ---- PAGE AJOUTER / ÉDITER ----
def page_add_edit():
    st.header("Ajouter / Modifier / Supprimer un client")
    df = load_df()
    mode = st.radio("Mode :", ["Ajouter", "Éditer / Supprimer"], horizontal=True)
    selected_id = None
    rec = {}

    if mode == "Éditer / Supprimer" and not df.empty:
        dfv = sort_alpha(df)
        selected_id = st.selectbox(
            "Choisir un client",
            options=dfv["id"].tolist(),
            format_func=lambda _id: f"{dfv.loc[dfv['id']==_id,'nom'].values[0]} {dfv.loc[dfv['id']==_id,'prenom'].values[0]}"
        )
        rec = df.loc[df["id"] == selected_id].iloc[0].to_dict()

    with st.form("form_client", clear_on_submit=(mode=="Ajouter")):
        c1,c2,c3,c4 = st.columns(4)
        nom = c1.text_input("Nom", value=rec.get("nom",""))
        prenom = c2.text_input("Prénom", value=rec.get("prenom",""))
        sexe = c3.selectbox("Sexe", ["Femme","Homme"], index=0 if rec.get("sexe","Femme")=="Femme" else 1)
        age = c4.number_input("Âge", min_value=0, max_value=120, value=int(rec.get("age",0) or 0))

        c5,c6,c7 = st.columns(3)
        taille = c5.number_input("Taille (cm)", min_value=0, max_value=260, value=int(rec.get("taille_cm",0) or 0))
        poids = c6.number_input("Poids actuel (kg)", min_value=0.0, max_value=500.0, value=float(rec.get("poids_kg",0) or 0))
        p_init = c7.number_input("Poids initial (kg)", min_value=0.0, max_value=500.0, value=float(rec.get("poids_initial_kg",0) or 0))

        objectif = st.selectbox("Objectif", ["Perte de poids","Prise de masse","Stabilisation","Autre"])
        sport = st.text_input("Sport", value=rec.get("sport",""))
        seances = st.number_input("Séances/sem.", min_value=0, max_value=21, value=int(rec.get("seances_semaine",0) or 0))

        imc_val, imc_cat = compute_imc(poids, taille)
        dej_mj, dej_kcal = compute_dej(sexe, poids, taille, age)
        pct = pct_perte_prise(p_init, poids)

        m1,m2,m3 = st.columns(3)
        m1.metric("IMC", imc_val if imc_val else "—", imc_cat or "")
        m2.metric("DEJ (MJ)", dej_mj if dej_mj else "—")
        m3.metric("DEJ (kcal)", dej_kcal if dej_kcal else "—")

        submitted = st.form_submit_button("💾 Enregistrer")
        now = dt.datetime.now().isoformat(timespec="seconds")

        if submitted:
            new = {
                "id": selected_id or str(uuid.uuid4()),
                "date_creation": rec.get("date_creation", now),
                "date_maj": now, "nom": nom, "prenom": prenom, "sexe": sexe, "age": age,
                "taille_cm": taille, "poids_kg": poids, "poids_initial_kg": p_init,
                "objectif": objectif, "sport": sport, "seances_semaine": seances,
                "imc": imc_val, "imc_cat": imc_cat, "dej_mj": dej_mj, "dej_kcal": dej_kcal, "pct_perte_prise": pct
            }
            if mode == "Ajouter":
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
            else:
                df.loc[df["id"] == selected_id, :] = pd.Series(new)
            save_df(df)
            st.success("✅ Données enregistrées !")

    if mode == "Éditer / Supprimer" and selected_id:
        st.download_button(
            "🧾 Télécharger fiche (PDF)",
            generate_pdf(df.loc[df["id"]==selected_id].iloc[0]),
            file_name=f"fiche_{rec.get('nom')}_{rec.get('prenom')}.pdf",
            mime="application/pdf"
        )
        if st.button("🗑️ Supprimer ce client"):
            df = df[df["id"] != selected_id]
            save_df(df)
            st.warning("Client supprimé.")

# ---- PAGE LISTE ----
def page_list():
    st.header("Clients — tri alphabétique (A → Z)")
    df = load_df()
    if df.empty:
        st.info("Aucun client enregistré.")
        return
    df = sort_alpha(df)
    st.dataframe(df[["nom","prenom","sexe","age","poids_kg","imc","dej_kcal","objectif","sport"]], use_container_width=True)

# ---- PAGE CALCUL RAPIDE ----
def page_quick():
    st.header("Calcul rapide IMC / DEJ")
    sexe = st.selectbox("Sexe", ["Femme","Homme"])
    poids = st.number_input("Poids (kg)", min_value=0.0)
    taille = st.number_input("Taille (cm)", min_value=0.0)
    age = st.number_input("Âge", min_value=0)
    imc_val, imc_cat = compute_imc(poids, taille)
    dej_mj, dej_kcal = compute_dej(sexe, poids, taille, age)
    st.metric("IMC", imc_val if imc_val else "—", imc_cat or "")
    st.metric("DEJ (MJ)", dej_mj if dej_mj else "—")
    st.metric("DEJ (kcal)", dej_kcal if dej_kcal else "—")

# ---- PAGE CALCUL DE RATION ----
def page_ration():
    st.header("💪 Calcul de ration alimentaire")
    alim = st.selectbox("Aliment :", list(ALIMENTS.keys()))
    qte = st.number_input("Quantité (g ou ml)", min_value=0.0, value=100.0, step=10.0)
    data = ALIMENTS[alim]
    p = data["P"] * qte / 100
    l = data["L"] * qte / 100
    g = data["G"] * qte / 100
    kcal = round((p * 4) + (l * 9) + (g * 4), 1)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Protéines (g)", f"{p:.1f}")
    c2.metric("Lipides (g)", f"{l:.1f}")
    c3.metric("Glucides (g)", f"{g:.1f}")
    c4.metric("Énergie (kcal)", f"{kcal}")
    st.info("Valeurs issues de la table CIQUAL (moyennes pour 100g).")

# ---- ROUTEUR ----
if page == "Ajouter / Éditer":
    page_add_edit()
elif page == "Liste (A→Z)":
    page_list()
elif page == "Calcul rapide":
    page_quick()
else:
    page_ration()

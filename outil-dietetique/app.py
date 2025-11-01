import os, uuid, datetime as dt
import pandas as pd
import streamlit as st
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

# --------- Configuration de l'application ---------
st.set_page_config(page_title="Outil diététique – Fiches clients", page_icon="🥗", layout="wide")

DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")
CSV_PATH   = os.path.join(DATA_DIR, "clients.csv")
os.makedirs(DATA_DIR, exist_ok=True)

COLUMNS = [
    "id","date_creation","date_maj","nom","prenom","sexe","age",
    "taille_cm","poids_kg","poids_initial_kg","objectif","sport","seances_semaine",
    "grignote","repas_par_jour","aliments_ok","aliments_ko","allergies","antecedents",
    "traitements","tabac","alcool","digestion","appetit",
    "imc","imc_cat","dej_mj","dej_kcal","pct_perte_prise"
]

# --------- Fonctions de base ---------
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
    return round(dej_mj, 3), round(dej_kcal, 0)

def pct_perte_prise(p0, p):
    if not p0 or not p or p0 <= 0:
        return None
    return round(((p0 - p) / p0) * 100, 2)

def sort_alpha(df):
    return df.sort_values(["nom", "prenom"], key=lambda s: s.str.lower(), na_position="last").reset_index(drop=True)

# --------- Génération PDF ---------
def generate_pdf(client):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, 27 * cm, "Fiche client diététique")
    c.setFont("Helvetica", 11)
    y = 25.5 * cm

    def line(label, value):
        nonlocal y
        c.drawString(2 * cm, y, f"{label}: {value}")
        y -= 0.7 * cm

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
    line("Aliments aimés", client['aliments_ok'])
    line("Aliments non aimés", client['aliments_ko'])
    line("Allergies", client['allergies'])
    line("Antécédents", client['antecedents'])
    line("Traitements", client['traitements'])
    line("Tabac", client['tabac'])
    line("Alcool", client['alcool'])
    line("Date mise à jour", client['date_maj'])

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# --------- Navigation ---------
st.sidebar.title("🥗 Outil diététique")
page = st.sidebar.radio("Aller à :", ["Ajouter / Éditer", "Liste (A→Z)", "Calcul rapide"])

# --------- Page principale ---------
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
        c1,c2,c3,c4 = st.columns([1,1,1,1])
        nom = c1.text_input("Nom", value=rec.get("nom",""))
        prenom = c2.text_input("Prénom", value=rec.get("prenom",""))
        sexe = c3.selectbox("Sexe", ["Femme","Homme"], index=0 if rec.get("sexe","Femme")=="Femme" else 1)
        age = c4.number_input("Âge", min_value=0, max_value=120, value=int(rec.get("age",0) or 0))

        c5,c6,c7 = st.columns([1,1,1])
        taille = c5.number_input("Taille (cm)", min_value=0, max_value=260, value=int(rec.get("taille_cm",0) or 0))
        poids = c6.number_input("Poids actuel (kg)", min_value=0.0, max_value=500.0, value=float(rec.get("poids_kg",0) or 0))
        p_init = c7.number_input("Poids initial (kg)", min_value=0.0, max_value=500.0, value=float(rec.get("poids_initial_kg",0) or 0))

        c8,c9,c10,c11 = st.columns([1,1,1,1])
        objectif = c8.selectbox("Objectif", ["Perte de poids","Prise de masse","Stabilisation","Autre"],
                                index=["Perte de poids","Prise de masse","Stabilisation","Autre"].index(rec.get("objectif","Perte de poids")))
        sport = c9.text_input("Sport", value=rec.get("sport",""))
        seances = c10.number_input("Séances/sem.", min_value=0, max_value=21, value=int(rec.get("seances_semaine",0) or 0))
        grignote = c11.selectbox("Grignote ?", ["Non","Oui"], index=1 if str(rec.get("grignote","Non")).lower()=="oui" else 0)

        c12,c13 = st.columns([1,1])
        repas_val = rec.get("repas_par_jour", 3)
        if pd.isna(repas_val) or repas_val == "":
            repas_val = 3
        repas_par_jour = c12.number_input("Repas/jour", min_value=1, max_value=10, value=int(repas_val))
        digestion = c13.selectbox("Digestion", ["Normale","Constipé(e)","Autre"],
                                  index={"Normale":0,"Constipé(e)":1,"Autre":2}.get(rec.get("digestion","Normale"),0))

        c14,c15,c16 = st.columns([1,1,1])
        appetit = c14.selectbox("Appétit", ["Normal","Faible","Élevé"],
                                index={"Normal":0,"Faible":1,"Élevé":2}.get(rec.get("appetit","Normal"),0))
        tabac = c15.selectbox("Tabac", ["Non","Oui"], index=1 if str(rec.get("tabac","Non")).lower()=="oui" else 0)
        alcool = c16.selectbox("Alcool", ["Non","Oui"], index=1 if str(rec.get("alcool","Non")).lower()=="oui" else 0)

        aliments_ok = st.text_area("Aliments aimés", value=rec.get("aliments_ok",""))
        aliments_ko = st.text_area("Aliments non aimés", value=rec.get("aliments_ko",""))
        allergies = st.text_area("Allergies", value=rec.get("allergies",""))
        antecedents = st.text_area("Antécédents médicaux", value=rec.get("antecedents",""))
        traitements = st.text_input("Traitements (médicaments)", value=rec.get("traitements",""))

        st.markdown("---")
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
            if mode == "Ajouter":
                new = {
                    "id": str(uuid.uuid4()), "date_creation": now, "date_maj": now,
                    "nom": nom, "prenom": prenom, "sexe": sexe, "age": age,
                    "taille_cm": taille, "poids_kg": poids, "poids_initial_kg": p_init,
                    "objectif": objectif, "sport": sport, "seances_semaine": seances,
                    "grignote": grignote, "repas_par_jour": repas_par_jour,
                    "aliments_ok": aliments_ok, "aliments_ko": aliments_ko,
                    "allergies": allergies, "antecedents": antecedents,
                    "traitements": traitements, "tabac": tabac, "alcool": alcool,
                    "digestion": digestion, "appetit": appetit,
                    "imc": imc_val, "imc_cat": imc_cat, "dej_mj": dej_mj,
                    "dej_kcal": dej_kcal, "pct_perte_prise": pct
                }
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                save_df(df)
                st.success("✅ Client ajouté avec succès")
            elif selected_id:
                idx = df.index[df["id"] == selected_id].tolist()
                if idx:
                    idx = idx[0]
                    for key, value in {
                        "date_maj": now, "nom": nom, "prenom": prenom, "sexe": sexe,
                        "age": age, "taille_cm": taille, "poids_kg": poids,
                        "poids_initial_kg": p_init, "objectif": objectif, "sport": sport,
                        "seances_semaine": seances, "grignote": grignote,
                        "repas_par_jour": repas_par_jour, "aliments_ok": aliments_ok,
                        "aliments_ko": aliments_ko, "allergies": allergies,
                        "antecedents": antecedents, "traitements": traitements,
                        "tabac": tabac, "alcool": alcool, "digestion": digestion,
                        "appetit": appetit, "imc": imc_val, "imc_cat": imc_cat,
                        "dej_mj": dej_mj, "dej_kcal": dej_kcal, "pct_perte_prise": pct
                    }.items():
                        df.loc[idx, key] = value
                    save_df(df)
                    st.success("✅ Modifications enregistrées")

    if mode == "Éditer / Supprimer" and selected_id:
        st.markdown("---")
        client = df.loc[df["id"] == selected_id].iloc[0].to_dict()
        pdf_data = generate_pdf(client)
        st.download_button(
            "🧾 Télécharger fiche (PDF)",
            pdf_data,
            file_name=f"fiche_{client['nom']}_{client['prenom']}.pdf",
            mime="application/pdf"
        )

        st.error("⚠️ Attention : cette action est définitive !")
        if st.button("🗑️ Supprimer ce client", use_container_width=True):
            df = df[df["id"] != selected_id].reset_index(drop=True)
            save_df(df)
            st.success("✅ Client supprimé avec succès")
            st.rerun()

# --------- Page Liste clients ---------
def page_list():
    st.header("Clients — tri alphabétique (A → Z)")
    df = load_df()
    if df.empty:
        st.info("Aucun client enregistré.")
        return
    df = sort_alpha(df)
    q = st.text_input("Recherche (nom, prénom, sport…)", "")
    if q:
        ql = q.lower()
        mask = df.apply(lambda row: any(str(v).lower().find(ql)>=0 for v in row.values if pd.notna(v)), axis=1)
        df = df[mask]
    st.dataframe(df[["nom","prenom","sexe","age","poids_kg","imc","dej_kcal","objectif","sport"]], use_container_width=True)

# --------- Page calcul rapide ---------
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

# --------- Router ---------
if page == "Ajouter / Éditer":
    page_add_edit()
elif page == "Liste (A→Z)":
    page_list()
else:
    page_quick()


import os, re, uuid, datetime as dt
import pandas as pd
import streamlit as st
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ================== CONFIG ==================
st.set_page_config(page_title="Outil diététique – Cabinet PRO", page_icon="🥗", layout="wide")

# ---- Tables et constantes ----
CLIENT_COLUMNS = [
    "id","date_creation","date_maj","nom","prenom","sexe","age",
    "taille_cm","poids_kg","poids_initial_kg","objectif","sport","seances_semaine",
    "grignote","repas_par_jour","aliments_ok","aliments_ko","allergies","antecedents",
    "traitements","tabac","alcool","digestion","appetit",
    "imc","imc_cat","dej_mj","dej_kcal","nap","pct_perte_prise"
]
SUIVI_COLUMNS = ["id_client","nom","prenom","date","poids_kg","imc"]

# Valeurs moyennes CIQUAL / 100 g (ou ml)
ALIMENTS = {
    "Lait 1/2 écrémé": {"P": 3, "L": 2, "G": 5, "kJ": 200},
    "Yaourt nature": {"P": 5, "L": 2, "G": 6, "kJ": 250},
    "Fromages moyens": {"P": 22, "L": 28, "G": 0, "kJ": 1450},
    "VPO": {"P": 18, "L": 10, "G": 0, "kJ": 680},
    "Céréales crues": {"P": 10, "L": 2, "G": 75, "kJ": 1450},
    "Pain blanc": {"P": 9, "L": 1.5, "G": 55, "kJ": 1150},
    "Légumineuses (secs)": {"P": 25, "L": 1, "G": 50, "kJ": 1243},
    "Légumes verts": {"P": 2, "L": 0, "G": 6, "kJ": 20},
    "Fruits": {"P": 1, "L": 0, "G": 12, "kJ": 200},
    "Beurre": {"P": 0, "L": 82, "G": 0, "kJ": 3110},
    "Huile": {"P": 0, "L": 100, "G": 0, "kJ": 3800},
    "Graines oléagineuses": {"P": 20, "L": 60, "G": 10, "kJ": 2300},
    "Sucre": {"P": 0, "L": 0, "G": 100, "kJ": 1700},
}

# ================== HELPERS (espace par diététicienne) ==================
def _sanitize_user_id(uid:str)->str:
    uid = uid.strip().lower()
    uid = re.sub(r"[^a-z0-9._-]+", "_", uid)
    return uid or "default"

def ensure_user_space(user_id:str):
    """Crée data/<user_id> avec clients.csv & suivi.csv si absents, et enregistre chemins en session."""
    base_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(base_dir, exist_ok=True)
    uid = _sanitize_user_id(user_id)
    user_dir = os.path.join(base_dir, uid)
    os.makedirs(user_dir, exist_ok=True)

    csv_path  = os.path.join(user_dir, "clients.csv")
    sv_path   = os.path.join(user_dir, "suivi.csv")

    if not os.path.exists(csv_path):
        pd.DataFrame(columns=CLIENT_COLUMNS).to_csv(csv_path, index=False)
    else:
        # s'assurer du superset de colonnes
        df = pd.read_csv(csv_path)
        for c in CLIENT_COLUMNS:
            if c not in df.columns: df[c] = None
        df[CLIENT_COLUMNS].to_csv(csv_path, index=False)

    if not os.path.exists(sv_path):
        pd.DataFrame(columns=SUIVI_COLUMNS).to_csv(sv_path, index=False)

    st.session_state["user_id"] = uid
    st.session_state["csv_path"] = csv_path
    st.session_state["suivi_path"] = sv_path
    st.session_state["user_dir"] = user_dir

def load_df():
    return pd.read_csv(st.session_state["csv_path"])

def save_df(df:pd.DataFrame):
    df.to_csv(st.session_state["csv_path"], index=False)

def load_suivi():
    return pd.read_csv(st.session_state["suivi_path"])

def append_suivi(id_client, nom, prenom, date_iso, poids_kg, imc):
    sv = load_suivi()
    row = {
        "id_client": id_client, "nom": nom, "prenom": prenom,
        "date": date_iso, "poids_kg": poids_kg, "imc": imc
    }
    sv = pd.concat([sv, pd.DataFrame([row])], ignore_index=True)
    sv.to_csv(st.session_state["suivi_path"], index=False)

# ================== CALCULS ==================
def compute_imc(poids, taille_cm):
    if not poids or not taille_cm or taille_cm <= 0:
        return None, None
    t = taille_cm/100
    imc = poids/(t*t)
    if imc < 18.5: cat = "Insuffisance pondérale"
    elif imc < 25: cat = "Corpulence normale"
    elif imc < 30: cat = "Surpoids"
    else: cat = "Obésité"
    return round(imc,2), cat

def compute_dej(sexe, poids, taille_cm, age, nap):
    if not all([sexe, poids, taille_cm, age]) or min(poids, taille_cm, age) <= 0:
        return None, None
    t = taille_cm/100
    if str(sexe).lower().startswith("f"):
        dej_mj = 0.963*(poids**0.48)*(t**0.50)*(age**-0.13)
    else:
        dej_mj = 1.083*(poids**0.48)*(t**0.50)*(age**-0.13)
    dej_mj *= nap
    dej_kcal = dej_mj*238.8459
    return round(dej_mj,3), round(dej_kcal,0)

def pct_perte_prise(p0, p):
    if not p0 or not p or p0 <= 0: return None
    return round(((p0-p)/p0)*100, 2)

def sort_alpha(df):
    return df.sort_values(["nom","prenom"], key=lambda s: s.str.lower(), na_position="last").reset_index(drop=True)

def calcul_ration(sel:dict):
    total_P=total_L=total_G=total_kJ=0
    rows=[]
    for alim,qte in sel.items():
        if alim not in ALIMENTS or qte<=0: continue
        P = ALIMENTS[alim]["P"]*qte/100
        L = ALIMENTS[alim]["L"]*qte/100
        G = ALIMENTS[alim]["G"]*qte/100
        kJ = ALIMENTS[alim]["kJ"]*qte/100
        kcal = P*4 + G*4 + L*9
        rows.append([alim, qte, round(P,1), round(L,1), round(G,1), round(kcal,1), round(kJ,1)])
        total_P += P; total_L += L; total_G += G; total_kJ += kJ
    total_kcal = total_P*4 + total_G*4 + total_L*9
    df = pd.DataFrame(rows, columns=["Aliment","Quantité (g/ml)","Prot (g)","Lip (g)","Gluc (g)","Énergie (kcal)","Énergie (kJ)"])
    return df, round(total_P,1), round(total_L,1), round(total_G,1), round(total_kcal,1), round(total_kJ,1)

# ================== PDFS ==================
def pdf_client(client:dict):
    buf=BytesIO(); c=canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold",14); c.drawString(2*cm,28*cm,"🥗 Fiche client diététique")
    c.setFont("Helvetica",11); y=26.6*cm
    def line(lbl,val):
        nonlocal y
        c.drawString(2*cm,y,f"{lbl} : {val}"); y-=0.52*cm
        if y<3*cm: c.showPage(); c.setFont("Helvetica",11); y=27*cm
    for lbl,key in [
        ("Nom","nom"),("Prénom","prenom"),("Sexe","sexe"),("Âge","age"),
        ("Taille (cm)","taille_cm"),("Poids (kg)","poids_kg"),
        ("IMC","imc"),("Catégorie IMC","imc_cat"),
        ("NAP","nap"),("DEJ (kcal)","dej_kcal"),
        ("Objectif","objectif"),("Sport","sport"),("Séances/semaine","seances_semaine"),
        ("Aliments aimés","aliments_ok"),("Aliments non aimés","aliments_ko"),
        ("Allergies","allergies"),("Antécédents médicaux","antecedents"),
        ("Traitements","traitements"),("Digestion","digestion"),("Appétit","appetit"),
        ("Tabac","tabac"),("Alcool","alcool"),("Grignote","grignote"),
        ("Repas/jour","repas_par_jour"),("Dernière MAJ","date_maj")
    ]:
        line(lbl, client.get(key,""))
    c.showPage(); c.save(); pdf=buf.getvalue(); buf.close(); return pdf

def pdf_ration(df_ration, P,L,G,kcal,kJ, df_rep, total_kcal_j, total_kJ_j):
    buf=BytesIO(); c=canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold",16); c.drawString(2*cm,28*cm,"🥗 Rapport – Ration & Répartition")
    c.setFont("Helvetica",10); y=26.6*cm
    c.drawString(2*cm,y,f"Protéines {P} g  |  Lipides {L} g  |  Glucides {G} g"); y-=0.5*cm
    c.drawString(2*cm,y,f"Énergie totale : {kcal} kcal ({kJ} kJ)"); y-=0.8*cm
    c.setFont("Helvetica-Bold",12); c.drawString(2*cm,y,"Tableau de ration :"); y-=0.55*cm
    c.setFont("Helvetica",10)
    for _,row in df_ration.iterrows():
        c.drawString(2*cm,y,f"- {row['Aliment']} ({row['Quantité (g/ml)']} g) : {row['Énergie (kcal)']} kcal / {row['Énergie (kJ)']} kJ")
        y-=0.42*cm
        if y<3*cm: c.showPage(); y=27*cm; c.setFont("Helvetica",10)
    c.showPage(); c.setFont("Helvetica-Bold",12); c.drawString(2*cm,28*cm,"🍽 Répartition journalière")
    y=26.6*cm; c.setFont("Helvetica",10)
    for _,row in df_rep.iterrows():
        c.drawString(2*cm,y,f"{row['Repas']} : {row['Total (kcal)']} kcal / {row['Total (kJ)']} kJ"); y-=0.5*cm
    y-=0.5*cm; c.setFont("Helvetica-Bold",11)
    c.drawString(2*cm,y,f"⚡ Total journée : {total_kcal_j} kcal ({total_kJ_j} kJ)")
    c.showPage(); c.save(); pdf=buf.getvalue(); buf.close(); return pdf

# ================== LOGIN (identifiant = espace dédié) ==================
st.sidebar.title("🔐 Connexion")
if "user_id" not in st.session_state:
    with st.sidebar.form("login_form"):
        ident = st.text_input("Bonjour veuillez entrez votre identifiant! ")
        ok = st.form_submit_button("Se connecter")
    if ok and ident.strip():
        ensure_user_space(ident)
        st.rerun()

    st.stop()
else:
    st.sidebar.success(f"Connecté : {st.session_state['user_id']}")
    if st.sidebar.button("Changer d'identifiant"):
        for k in ("user_id","csv_path","suivi_path","user_dir"):
            st.session_state.pop(k, None)
        st.rerun()


# ================== NAVIGATION ==================
NAV = st.sidebar.radio("Navigation :", ["Ajouter / Éditer", "Liste (A→Z)", "Calcul rapide", "🍽 Ration & Répartition"])

# ================== PAGES ==================
def page_add_edit():
    st.header("Ajouter / Modifier / Supprimer un client")
    df = load_df()
    mode = st.radio("Mode :", ["Ajouter", "Éditer / Supprimer"], horizontal=True)
    selected_id, rec = None, {}

    if mode == "Éditer / Supprimer" and not df.empty:
        dfv = sort_alpha(df)
        selected_id = st.selectbox(
            "Choisir un client",
            options=dfv["id"].tolist(),
            format_func=lambda i: f"{dfv.loc[dfv['id']==i,'nom'].values[0]} {dfv.loc[dfv['id']==i,'prenom'].values[0]}"
        )
        rec = df.loc[df["id"]==selected_id].iloc[0].to_dict()

        # ---- Graphique de suivi (poids + IMC) ----
        st.markdown("### 📈 Suivi d'évolution (Poids & IMC)")
        sv = load_suivi()
        sv_c = sv[sv["id_client"]==selected_id].copy()
        if not sv_c.empty:
            sv_c["date"] = pd.to_datetime(sv_c["date"])
            sv_c = sv_c.sort_values("date")
            sv_c = sv_c.set_index("date")[["poids_kg","imc"]]
            st.line_chart(sv_c, use_container_width=True)
        else:
            st.info("Pas encore d'historique pour ce client. Enregistrez une première mesure.")

    with st.form("form_client", clear_on_submit=(mode=="Ajouter")):
        c1,c2,c3,c4 = st.columns(4)
        nom    = c1.text_input("Nom", rec.get("nom",""))
        prenom = c2.text_input("Prénom", rec.get("prenom",""))
        sexe   = c3.selectbox("Sexe", ["Femme","Homme"], index=0 if rec.get("sexe","Femme")=="Femme" else 1)
        age    = c4.number_input("Âge", 0, 120, int(rec.get("age",0) or 0))

        c5,c6,c7,c8 = st.columns(4)
        taille = c5.number_input("Taille (cm)", 0, 250, int(rec.get("taille_cm",0) or 0))
        poids  = c6.number_input("Poids actuel (kg)", 0.0, 500.0, float(rec.get("poids_kg",0) or 0))
        p_init = c7.number_input("Poids initial (kg)", 0.0, 500.0, float(rec.get("poids_initial_kg",0) or 0))
        nap    = c8.number_input("NAP (activité)", 1.0, 2.5, step=0.05, value=float(rec.get("nap",1.63) or 1.63))

        imc, cat = compute_imc(poids, taille)
        dej_mj, dej_kcal = compute_dej(sexe, poids, taille, age, nap)
        pct = pct_perte_prise(p_init, poids)

        c9,c10,c11 = st.columns(3)
        objectif = c9.selectbox("Objectif", ["Perte de poids","Prise de masse","Stabilisation","Autre"],
                                index=["Perte de poids","Prise de masse","Stabilisation","Autre"].index(rec.get("objectif","Perte de poids")))
        sport    = c10.text_input("Sport", rec.get("sport",""))
        seances  = c11.number_input("Séances/semaine", 0, 21, int(rec.get("seances_semaine",0) or 0))

        st.markdown("### 🍽 Habitudes & préférences")
        aliments_ok = st.text_area("Aliments aimés", rec.get("aliments_ok",""))
        aliments_ko = st.text_area("Aliments non aimés", rec.get("aliments_ko",""))
        allergies   = st.text_area("Allergies", rec.get("allergies",""))
        antecedents = st.text_area("Antécédents médicaux", rec.get("antecedents",""))
        traitements = st.text_input("Traitements (médicaments)", rec.get("traitements",""))

        c12,c13,c14,c15 = st.columns(4)
        digestion = c12.selectbox("Digestion", ["Normale","Constipé(e)","Autre"],
                                  index={"Normale":0,"Constipé(e)":1,"Autre":2}.get(rec.get("digestion","Normale"),0))
        appetit   = c13.selectbox("Appétit", ["Normal","Faible","Élevé"],
                                  index={"Normal":0,"Faible":1,"Élevé":2}.get(rec.get("appetit","Normal"),0))
        tabac     = c14.selectbox("Tabac", ["Non","Oui"], index=1 if str(rec.get("tabac","Non")).lower()=="oui" else 0)
        alcool    = c15.selectbox("Alcool", ["Non","Oui"], index=1 if str(rec.get("alcool","Non")).lower()=="oui" else 0)

        grignote = st.selectbox("Grignote ?", ["Non","Oui"], index=1 if str(rec.get("grignote","Non")).lower()=="oui" else 0)
        repas_j  = st.number_input("Repas/jour", 1, 10, int(rec.get("repas_par_jour",3) or 3))

        st.markdown("---")
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("IMC", imc if imc else "—", cat or "")
        m2.metric("NAP", nap)
        m3.metric("DEJ (MJ)", dej_mj if dej_mj else "—")
        m4.metric("DEJ (kcal)", dej_kcal if dej_kcal else "—")

        submitted = st.form_submit_button("💾 Enregistrer")
        now = dt.datetime.now().isoformat(timespec="seconds")

        if submitted:
            df = load_df()
            new = {
                "id": selected_id or str(uuid.uuid4()),
                "date_creation": rec.get("date_creation", now),
                "date_maj": now, "nom": nom, "prenom": prenom, "sexe": sexe, "age": age,
                "taille_cm": taille, "poids_kg": poids, "poids_initial_kg": p_init,
                "objectif": objectif, "sport": sport, "seances_semaine": seances,
                "grignote": grignote, "repas_par_jour": repas_j,
                "aliments_ok": aliments_ok, "aliments_ko": aliments_ko, "allergies": allergies,
                "antecedents": antecedents, "traitements": traitements, "tabac": tabac, "alcool": alcool,
                "digestion": digestion, "appetit": appetit,
                "imc": imc, "imc_cat": cat, "dej_mj": dej_mj, "dej_kcal": dej_kcal, "nap": nap,
                "pct_perte_prise": pct
            }
            if mode == "Ajouter":
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
            else:
                for k,v in new.items():
                    df.loc[df["id"]==selected_id, k] = v
            save_df(df)

            # historique => suivi.csv
            append_suivi(new["id"], nom, prenom, now, poids, imc)

            st.success("✅ Données enregistrées & suivi mis à jour.")

    if mode == "Éditer / Supprimer" and selected_id:
        st.markdown("---")
        df = load_df()
        client = df.loc[df["id"]==selected_id].iloc[0].to_dict()
        st.download_button("🧾 Télécharger fiche (PDF)", pdf_client(client),
                           file_name=f"fiche_{client.get('nom','')}_{client.get('prenom','')}.pdf",
                           mime="application/pdf")
        st.error("⚠️ Suppression définitive")
        if st.button("🗑️ Supprimer ce client", use_container_width=True):
            df = df[df["id"]!=selected_id].reset_index(drop=True)
            save_df(df)
            # Nettoyage optionnel du suivi : on garde l'historique par défaut
            st.success("✅ Client supprimé."); st.rerun()

def page_list():
    st.header("Clients — tri alphabétique (A → Z)")
    df = load_df()
    if df.empty:
        st.info("Aucun client enregistré.")
        return
    df = sort_alpha(df)
    q = st.text_input("Recherche (nom, prénom, mots-clés)…", "")
    if q:
        ql = q.lower()
        mask = df.apply(lambda r: any(str(v).lower().find(ql)>=0 for v in r.values if pd.notna(v)), axis=1)
        df = df[mask]
    st.dataframe(df[["nom","prenom","sexe","age","poids_kg","imc","dej_kcal","nap","objectif","sport"]],
                 use_container_width=True)

def page_quick():
    st.header("Calcul rapide IMC / DEJ")
    sexe  = st.selectbox("Sexe", ["Femme","Homme"])
    poids = st.number_input("Poids (kg)", min_value=0.0)
    taille= st.number_input("Taille (cm)", min_value=0.0)
    age   = st.number_input("Âge", min_value=0)
    nap   = st.number_input("NAP", min_value=1.0, max_value=2.5, step=0.05, value=1.63)
    imc, cat = compute_imc(poids, taille)
    dej_mj, dej_kcal = compute_dej(sexe, poids, taille, age, nap)
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("IMC", imc if imc else "—", cat or "")
    m2.metric("NAP", nap)
    m3.metric("DEJ (MJ)", dej_mj if dej_mj else "—")
    m4.metric("DEJ (kcal)", dej_kcal if dej_kcal else "—")

def page_ration():
    st.header("🍽 Calcul de ration & Répartition énergétique")

    st.subheader("🧮 Sélection d’aliments multiples")
    n = st.number_input("Nombre d’aliments :", min_value=1, max_value=20, value=3)
    sel = {}
    cols = st.columns(3)
    for i in range(int(n)):
        alim = cols[0].selectbox(f"Aliment #{i+1}", list(ALIMENTS.keys()), key=f"alim_{i}")
        qte  = cols[1].number_input(f"Quantité (g/ml) #{i+1}", min_value=0.0, step=10.0, value=100.0, key=f"qte_{i}")
        sel[alim] = qte

    df_ration, P,L,G,kcal,kJ = calcul_ration(sel)
    if not df_ration.empty:
        st.table(df_ration)
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Protéines (g)", P); c2.metric("Lipides (g)", L); c3.metric("Glucides (g)", G)
        c4.metric("Énergie (kcal)", kcal); c5.metric("Énergie (kJ)", kJ)
    else:
        st.info("Ajoute au moins un aliment avec une quantité > 0 g.")

    st.markdown("---")
    st.subheader("🍽 Répartition par repas (2 collations possibles)")
    repas_list = ["Petit-déjeuner","Déjeuner","Collation matin","Collation après-midi","Dîner"]
    rep_sel={}
    for r in repas_list:
        with st.expander(f"⚡ {r}", expanded=False):
            nr = st.number_input(f"Nombre d’aliments pour {r}", min_value=0, max_value=15, value=0, key=f"n_{r}")
            s={}
            for i in range(int(nr)):
                a = st.selectbox(f"{r} - Aliment #{i+1}", list(ALIMENTS.keys()), key=f"{r}_a_{i}")
                q = st.number_input(f"{r} - Quantité (g/ml) #{i+1}", min_value=0.0, step=10.0, value=100.0, key=f"{r}_q_{i}")
                s[a]=q
            rep_sel[r]=s

    resume=[]; total_kcal_j=0; total_kJ_j=0
    for r, s in rep_sel.items():
        _, _,_,_, kcal_r, kJ_r = calcul_ration(s)
        total_kcal_j += kcal_r; total_kJ_j += kJ_r
        resume.append([r, round(kcal_r,1), round(kJ_r,1)])

    df_rep = pd.DataFrame(resume, columns=["Repas","Total (kcal)","Total (kJ)"])
    st.table(df_rep)
    d1,d2 = st.columns(2)
    d1.metric("Total journée (kcal)", round(total_kcal_j,1))
    d2.metric("Total journée (kJ)",   round(total_kJ_j,1))

    st.markdown("---")
    pdf = pdf_ration(df_ration, P,L,G,kcal,kJ, df_rep, round(total_kcal_j,1), round(total_kJ_j,1))
    st.download_button("🧾 Télécharger le rapport ration/répartition (PDF)",
                       data=pdf, file_name="rapport_ration_repartition.pdf", mime="application/pdf")

# ================== ROUTER ==================
if NAV == "Ajouter / Éditer":
    page_add_edit()
elif NAV == "Liste (A→Z)":
    page_list()
elif NAV == "Calcul rapide":
    page_quick()
else:
    page_ration()

import os
import pandas as pd
import streamlit as st
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

# ---------------- CONFIGURATION ----------------
st.set_page_config(page_title="Outil diététique – Ration & Répartition", page_icon="🥗", layout="wide")

# ---------------- TABLE DES ALIMENTS ----------------
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

# ---------------- CALCUL RATION ----------------
def calcul_ration(selection):
    total_P = total_L = total_G = total_kJ = 0
    data = []
    for alim, qte in selection.items():
        if alim in ALIMENTS:
            p = ALIMENTS[alim]["P"] * qte / 100
            l = ALIMENTS[alim]["L"] * qte / 100
            g = ALIMENTS[alim]["G"] * qte / 100
            kj = ALIMENTS[alim]["kJ"] * qte / 100
            kcal = (p * 4) + (g * 4) + (l * 9)
            data.append([alim, qte, round(p,1), round(l,1), round(g,1), round(kcal,1), round(kj,1)])
            total_P += p
            total_L += l
            total_G += g
            total_kJ += kj
    total_kcal = (total_P * 4) + (total_G * 4) + (total_L * 9)
    return data, total_P, total_L, total_G, total_kcal, total_kJ

# ---------------- PDF ----------------
def generate_pdf(df_ration, P, L, G, kcal, kJ, df_repartition, total_jour_kcal, total_jour_kJ):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, 28 * cm, "🥗 Rapport diététique – Ration & Répartition")
    c.setFont("Helvetica", 11)
    y = 26.5 * cm

    # Totaux globaux
    c.drawString(2 * cm, y, f"Protéines : {P:.1f} g")
    c.drawString(6 * cm, y, f"Lipides : {L:.1f} g")
    c.drawString(10 * cm, y, f"Glucides : {G:.1f} g")
    y -= 0.6 * cm
    c.drawString(2 * cm, y, f"Énergie totale : {kcal:.1f} kcal ({kJ:.1f} kJ)")
    y -= 1.0 * cm

    # Tableau ration
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Tableau de ration :")
    y -= 0.6 * cm
    c.setFont("Helvetica", 10)
    for _, row in df_ration.iterrows():
        txt = f"- {row['Aliment']} ({row['Quantité (g/ml)']} g) : {row['Énergie (kcal)']} kcal / {row['Énergie (kJ)']} kJ"
        c.drawString(2 * cm, y, txt)
        y -= 0.5 * cm
        if y < 3 * cm:
            c.showPage()
            y = 27 * cm

    # Nouvelle page pour répartition
    c.showPage()
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, 28 * cm, "🍽 Répartition énergétique par repas")
    y = 26.5 * cm
    c.setFont("Helvetica", 10)
    for _, row in df_repartition.iterrows():
        c.drawString(2 * cm, y, f"{row['Repas']} : {row['Total (kcal)']} kcal / {row['Total (kJ)']} kJ")
        y -= 0.6 * cm

    y -= 0.8 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, f"⚡ Total journée : {total_jour_kcal:.1f} kcal ({total_jour_kJ:.1f} kJ)")
    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# ---------------- PAGE PRINCIPALE ----------------
st.title("💪 Calcul de ration et répartition énergétique")

st.markdown("### 🧮 Sélection d’aliments multiples")
n = st.number_input("Nombre d’aliments :", min_value=1, max_value=15, value=3)
selection = {}
cols = st.columns(3)
for i in range(n):
    alim = cols[0].selectbox(f"Aliment #{i+1}", list(ALIMENTS.keys()), key=f"alim_{i}")
    qte = cols[1].number_input(f"Quantité (g/ml) #{i+1}", min_value=0.0, step=10.0, value=100.0, key=f"qte_{i}")
    selection[alim] = qte

data, P, L, G, kcal, kJ = calcul_ration(selection)
df_ration = pd.DataFrame(data, columns=["Aliment", "Quantité (g/ml)", "Prot (g)", "Lip (g)", "Gluc (g)", "Énergie (kcal)", "Énergie (kJ)"])
st.table(df_ration)

st.markdown("### 🔢 Totaux globaux")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Protéines (g)", f"{P:.1f}")
c2.metric("Lipides (g)", f"{L:.1f}")
c3.metric("Glucides (g)", f"{G:.1f}")
c4.metric("Énergie (kcal)", f"{kcal:.1f}")
c5.metric("Énergie (kJ)", f"{kJ:.1f}")

# ---------------- REPARTITION ----------------
st.markdown("---")
st.subheader("🍽 Répartition énergétique journalière")

repas = ["Petit-déjeuner", "Déjeuner", "Collation", "Dîner"]
repas_selection = {}
for r in repas:
    with st.expander(f"⚡ {r}"):
        n_r = st.number_input(f"Nombre d’aliments pour {r}", min_value=0, max_value=10, value=2, key=f"nb_{r}")
        sel = {}
        for i in range(int(n_r)):
            alim = st.selectbox(f"{r} - Aliment #{i+1}", list(ALIMENTS.keys()), key=f"{r}_alim_{i}")
            qte = st.number_input(f"{r} - Quantité (g/ml) #{i+1}", min_value=0.0, step=10.0, value=100.0, key=f"{r}_qte_{i}")
            sel[alim] = qte
        repas_selection[r] = sel

resume = []
total_jour_kJ = total_jour_kcal = 0
for r, sel in repas_selection.items():
    _, _, _, _, kcal_r, kJ_r = calcul_ration(sel)
    total_jour_kJ += kJ_r
    total_jour_kcal += kcal_r
    resume.append([r, round(kJ_r,1), round(kcal_r,1)])

df_repartition = pd.DataFrame(resume, columns=["Repas", "Total (kJ)", "Total (kcal)"])
st.table(df_repartition)

st.markdown("### ✅ Total journalier")
c1, c2 = st.columns(2)
c1.metric("Total énergie (kJ)", f"{total_jour_kJ:.1f}")
c2.metric("Total énergie (kcal)", f"{total_jour_kcal:.1f}")

# ---------------- TELECHARGEMENT PDF ----------------
st.markdown("---")
pdf = generate_pdf(df_ration, P, L, G, kcal, kJ, df_repartition, total_jour_kcal, total_jour_kJ)
st.download_button("🧾 Télécharger le rapport en PDF", data=pdf, file_name="rapport_dietetique.pdf", mime="application/pdf")

st.success("✅ Rapport complet généré avec succès !")



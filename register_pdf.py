# -*- coding: utf-8 -*-
"""
register_pdf.py
---------------
Génère le REGISTRE DE PAIE au format PDF (A4 paysage) : une ligne par
employé avec l'ensemble des éléments de paie (gains détaillés, retenues,
net, charges patronales, coût employeur), une ligne de TOTAUX, répétition
de l'en-tête de tableau sur chaque page, en-tête société (avec logo
éventuel) et pied de page paramétrables.

Aucune dépendance à Tkinter : ce module peut être testé seul.
"""

import base64
import datetime
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# (clé dans le résultat de compute_payslip, en-tête PDF, poids de largeur, est_un_montant)
# Les poids servent à répartir la largeur disponible ; "fixe_mm" pour les colonnes texte.
COLUMNS = [
    ("numero", "N°", 7, "fixe"),
    ("nom_prenoms", "Nom & Prénoms", 29, "fixe"),
    ("classification", "Classif.", 9, "fixe"),
    ("personnes_a_charge", "Pers.\ncharge", 8, "fixe"),
    ("salaire_base", "Salaire\nde base", 12, "montant"),
    ("prime_anciennete", "Prime\nanc.", 11, "montant"),
    ("heures_sup", "Heures\nsup.", 11, "montant"),
    ("sursalaire", "Sursa-\nlaire", 11, "montant"),
    ("gratification", "Gratif.", 11, "montant"),
    ("indemnite_caisse", "Ind.\ncaisse", 11, "montant"),
    ("indemnite_logement", "Ind.\nlogement", 12, "montant"),
    ("indemnite_fonction", "Ind.\nfonction", 12, "montant"),
    ("indemnite_transport", "Ind.\ntransport", 12, "montant"),
    ("remuneration_totale", "Rémuné-\nration totale", 13.5, "montant"),
    ("cnss_salariale", "CNSS\nsalariale", 11, "montant"),
    ("base_imposable", "Base\nimposable", 13.5, "montant"),
    ("iuts_net", "IUTS", 12, "montant"),
    ("retenue_obligatoire", "Retenue\noblig. 1%", 11, "montant"),
    ("retenue_pret", "Retenue\nprêt", 11, "montant"),
    ("net_percu", "NET\nPERÇU", 13.5, "montant"),
    ("cnss_patronale", "CNSS\npatronale", 12, "montant"),
    ("tpa_patronale", "TPA", 11, "montant"),
    ("cout_total_employeur", "Coût total\nemployeur", 13.5, "montant"),
]

MONEY_KEYS = [c[0] for c in COLUMNS if c[3] == "montant"]
PADDING_PT = 1.2


def _money(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    if f == 0:
        return "-"
    return f"{f:,.0f}".replace(",", " ")


def _column_widths_pt(page_width_pt, margin_pt):
    """Largeurs de colonnes en points : colonnes texte fixes, le reste de la
    largeur utile réparti proportionnellement aux poids des montants."""
    usable = page_width_pt - 2 * margin_pt
    fixed_total = sum(c[2] for c in COLUMNS if c[3] == "fixe") * mm
    weights_total = sum(c[2] for c in COLUMNS if c[3] == "montant")
    money_total = usable - fixed_total
    widths = []
    for key, _h, w, kind in COLUMNS:
        if kind == "fixe":
            widths.append(w * mm)
        else:
            widths.append(money_total * w / weights_total)
    return widths


def _truncate(text, font, size, max_width):
    text = str(text)
    if stringWidth(text, font, size) <= max_width:
        return text
    while text and stringWidth(text + ".", font, size) > max_width:
        text = text[:-1]
    return text + "."


def build_register_pdf(results, path, entete=None, pied="", period_text=""):
    """results : liste de dicts renvoyés par payroll_engine.compute_payslip.
    entete : dict (nom_entreprise, adresse, telephone, email, note_entete, logo_base64).
    pied : texte de pied de page. period_text : ex. 'Août 2026'."""
    entete = entete or {}
    results = sorted(results, key=lambda r: r.get("numero", 0))

    page = landscape(A4)
    margin = 8 * mm
    col_w = _column_widths_pt(page[0], margin)

    # ---- Données du tableau ------------------------------------------------
    header = [c[1] for c in COLUMNS]
    body = []
    for r in results:
        row = []
        for key, _h, _w, kind in COLUMNS:
            if kind == "montant":
                row.append(_money(r.get(key, 0)))
            else:
                row.append(str(r.get(key, "")))
        body.append(row)

    totals = {k: sum(float(r.get(k, 0) or 0) for r in results) for k in MONEY_KEYS}
    total_row = []
    for key, _h, _w, kind in COLUMNS:
        if key == "nom_prenoms":
            total_row.append(f"TOTAL ({len(results)})")
        elif kind == "montant":
            total_row.append(_money(totals[key]))
        else:
            total_row.append("")

    # ---- Taille de police : la plus grande qui fait tenir tous les chiffres ----
    font_size = 6.5
    for ci, (key, _h, _w, kind) in enumerate(COLUMNS):
        if kind != "montant":
            continue
        avail = col_w[ci] - 2 * PADDING_PT
        candidates = [(row[ci], "Helvetica") for row in body]
        candidates.append((total_row[ci], "Helvetica-Bold"))
        for line in header[ci].split("\n"):
            candidates.append((line, "Helvetica-Bold"))
        for text, font in candidates:
            w1 = stringWidth(text, font, 1)
            if w1 > 0:
                font_size = min(font_size, avail / w1)
    font_size = max(4.8, min(font_size, 6.5))

    # Noms trop longs : tronqués pour ne pas déborder sur la colonne voisine
    name_idx = [c[0] for c in COLUMNS].index("nom_prenoms")
    name_avail = col_w[name_idx] - 2 * PADDING_PT
    for row in body:
        row[name_idx] = _truncate(row[name_idx], "Helvetica", font_size, name_avail)

    data = [header] + body + [total_row]
    table = Table(data, colWidths=col_w, repeatRows=1)

    style = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), font_size),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 1.6),
        ("LEFTPADDING", (0, 0), (-1, -1), PADDING_PT),
        ("RIGHTPADDING", (0, 0), (-1, -1), PADDING_PT),
        ("TOPPADDING", (0, 1), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2.2),
        ("TOPPADDING", (0, 0), (-1, 0), 3),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8B8B8")),
        # alignements
        ("ALIGN", (0, 1), (0, -1), "CENTER"),            # N°
        ("ALIGN", (1, 1), (1, -1), "LEFT"),              # nom
        ("ALIGN", (2, 1), (3, -1), "CENTER"),            # classif, charges
        ("ALIGN", (4, 1), (-1, -1), "RIGHT"),            # montants
        # ligne de totaux
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#DCE6F1")),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
    ]
    # fond alterné, plus lisible sur beaucoup de lignes
    for i in range(1, len(data) - 1):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F8FB")))
    # colonne NET PERÇU mise en valeur
    net_idx = [c[0] for c in COLUMNS].index("net_percu")
    style.append(("FONTNAME", (net_idx, 1), (net_idx, -2), "Helvetica-Bold"))
    table.setStyle(TableStyle(style))

    # ---- En-tête / pied de page de chaque page -------------------------------
    logo_reader = None
    if entete.get("logo_base64"):
        try:
            logo_reader = ImageReader(io.BytesIO(base64.b64decode(entete["logo_base64"])))
        except Exception:
            logo_reader = None

    today_txt = datetime.date.today().strftime("%d/%m/%Y")
    nb_employes = len(results)

    def decorate(c, doc):
        w, h = page
        x = margin
        y = h - 11 * mm
        text_x = x
        bottom_y = y
        if logo_reader is not None:
            try:
                iw, ih = logo_reader.getSize()
                lh = 13 * mm
                lw = min(lh * (iw / ih) if ih else lh, 28 * mm)
                c.drawImage(logo_reader, x, h - 6 * mm - lh, width=lw, height=lh,
                            preserveAspectRatio=True, mask="auto")
                text_x = x + lw + 4 * mm
            except Exception:
                pass
        c.setFont("Helvetica-Bold", 11)
        c.drawString(text_x, y, entete.get("nom_entreprise") or "Mon Entreprise")
        coords = [v for v in (entete.get("adresse"), entete.get("telephone"), entete.get("email")) if v]
        if coords:
            c.setFont("Helvetica", 7.5)
            c.drawString(text_x, y - 4.3 * mm, "  •  ".join(coords))

        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(w / 2, h - 11 * mm, f"REGISTRE DE PAIE — {period_text.upper()}")
        c.setFont("Helvetica", 8)
        c.drawCentredString(w / 2, h - 15.5 * mm, f"Effectif : {nb_employes} salarié(s)")

        c.setFont("Helvetica", 8)
        c.drawRightString(w - margin, h - 11 * mm, f"Édité le {today_txt}")
        c.drawRightString(w - margin, h - 15.5 * mm, f"Page {doc.page}")

        c.setLineWidth(0.8)
        c.line(margin, h - 21 * mm, w - margin, h - 21 * mm)

        # pied de page
        c.setLineWidth(0.4)
        c.line(margin, 14 * mm, w - margin, 14 * mm)
        if pied:
            c.setFont("Helvetica-Oblique", 6.5)
            lines = simpleSplit(pied.replace("\n", " "), "Helvetica-Oblique", 6.5, w - 2 * margin)
            ty = 10.5 * mm
            for line in lines[:2]:
                c.drawString(margin, ty, line)
                ty -= 3 * mm

    doc = SimpleDocTemplate(
        path, pagesize=page,
        leftMargin=margin, rightMargin=margin,
        topMargin=24 * mm, bottomMargin=17 * mm,
        title=f"Registre de paie - {period_text}",
        author=entete.get("nom_entreprise") or "Paie Burkina",
    )
    doc.build([table], onFirstPage=decorate, onLaterPages=decorate)

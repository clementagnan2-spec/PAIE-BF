# -*- coding: utf-8 -*-
"""
payroll_engine.py
------------------
Reproduit fidèlement les formules du classeur Excel "Paie Burkina" :
  - Cotisation CNSS salariale (plafonnée)
  - Charges patronales (CNSS 16% + TPA 3%)
  - Abattement forfaitaire pour frais professionnels (CADRE / AUTRE)
  - Exonération des indemnités (Logement, Fonction, Transport)
  - Base imposable (arrondie au multiple de 100 inférieur)
  - IUTS par barème progressif (9 tranches)
  - Réduction de l'IUTS selon le nombre de personnes à charge
  - Salaire net, retenue obligatoire 1%, net perçu

Toutes les valeurs par défaut ci-dessous proviennent du fichier
"1-Paie_Burkina (date).xlsx" fourni (onglet "Paramètres").
"""

import math
from dataclasses import dataclass, field, asdict, replace
from typing import Optional


# ---------------------------------------------------------------------------
# Paramètres par défaut (identiques à l'onglet "Paramètres" du classeur)
# ---------------------------------------------------------------------------

DEFAULT_PARAMS = {
    "taux_cnss_salarie": 0.055,
    "plafond_cnss": 800000,
    "cnss_salariale_plafonnee": 44000,
    "taux_cnss_patronale": 0.16,
    "taux_tpa": 0.03,
    "taux_retenue_obligatoire": 0.01,

    "abattement_cadre": 0.2,
    "abattement_autre": 0.25,

    "taux_plafond_fiscal": 0.08,

    # indemnité: [taux_exonere, plafond_mensuel]
    "exo_logement": [0.2, 75000],
    "exo_fonction": [0.05, 50000],
    "exo_transport": [0.05, 30000],

    # tranches IUTS: (de, a, taux, montant_cumule_anterieur). "a"=None -> et plus
    "bareme_iuts": [
        (0, 10000, 0.0, 0),
        (10000, 20000, 0.0, 0),
        (20000, 30000, 0.0, 0),
        (30000, 50000, 0.121, 0),
        (50000, 80000, 0.139, 2420),
        (80000, 120000, 0.157, 6590),
        (120000, 170000, 0.184, 12870),
        (170000, 250000, 0.217, 22070),
        (250000, None, 0.25, 39430),
    ],

    # réduction IUTS selon personnes à charge: {0:1, 1:0.92, 2:0.9, 3:0.88, "4+":0.86}
    "reduction_charges": {"0": 1.0, "1": 0.92, "2": 0.9, "3": 0.88, "4+": 0.86},
}


@dataclass
class Employee:
    numero: int = 0
    nom_prenoms: str = ""
    classification: str = "AUTRE"     # "CADRE" ou "AUTRE"
    periode: str = ""                 # période de paie, format "AAAA-MM" (ex: "2026-08")
    salaire_base: float = 0.0
    prime_anciennete: float = 0.0
    heures_sup: float = 0.0
    sursalaire: float = 0.0
    gratification: float = 0.0
    indemnite_caisse: float = 0.0
    indemnite_logement: float = 0.0
    indemnite_fonction: float = 0.0
    indemnite_transport: float = 0.0
    personnes_a_charge: int = 0
    retenue_pret: float = 0.0
    date_saisie: str = ""             # date d'enregistrement dans le logiciel (audit), format ISO

    def to_dict(self):
        return asdict(self)


def _round(x, ndigits=0):
    """Reproduit ROUND() d'Excel (arrondi arithmétique, pas 'banker's rounding')."""
    if ndigits == 0:
        return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)
    factor = 10 ** ndigits
    return _round(x * factor) / factor


def _rounddown_to_hundred(x):
    """Reproduit ROUNDDOWN(x, -2) d'Excel : arrondi à la centaine inférieure."""
    return math.floor(x / 100.0) * 100.0


def _charge_key(n):
    n = int(n)
    if n >= 4:
        return "4+"
    return str(n)


def compute_iuts_brut(base_imposable, bareme):
    """Calcule l'IUTS brut par la formule en cascade du barème (identique à la
    formule Excel imbriquée IF...IF sur les 9 tranches)."""
    x = base_imposable
    for (de, a, taux, cumul) in bareme:
        if a is None or x < a:
            return (x - de) * taux + cumul
    # sécurité : dernière tranche si rien ne matche (ne devrait pas arriver)
    de, a, taux, cumul = bareme[-1]
    return (x - de) * taux + cumul


def _exoneration_indemnite(taux, plafond, indemnite_versee, salaire_brut):
    """Reproduit la formule Excel :
    =IF(taux*Brut<=Indem, IF(taux*Brut<=Plafond, taux*Brut, Plafond),
                          IF(Indem>=Plafond, Plafond, Indem))
    """
    seuil = taux * salaire_brut
    if seuil <= indemnite_versee:
        return seuil if seuil <= plafond else plafond
    else:
        return plafond if indemnite_versee >= plafond else indemnite_versee


def compute_payslip(emp: Employee, params: dict) -> dict:
    """Calcule un bulletin de paie complet pour un employé, selon les
    paramètres fournis (dict, même structure que DEFAULT_PARAMS)."""

    F = emp.salaire_base
    G = emp.prime_anciennete
    H = emp.heures_sup
    I = emp.sursalaire
    J = emp.gratification
    K = emp.indemnite_caisse
    L = emp.indemnite_logement
    M = emp.indemnite_fonction
    N = emp.indemnite_transport

    # O : Rémunération totale
    O = F + G + H + I + J + K + L + M + N

    # P : CNSS salariale
    if O <= params["plafond_cnss"]:
        P = _round(O * params["taux_cnss_salarie"])
    else:
        P = params["cnss_salariale_plafonnee"]

    # Q : Plafond fiscal (8% de Sal.Base+Prime anc+HS+Sursalaire)
    Q = params["taux_plafond_fiscal"] * (F + G + H + I)

    # R : Salaire brut
    R = O - Q if P >= Q else O - P
    R = _round(R)

    # S : Abattement forfaitaire
    base_abattement = F + G + H + I
    if emp.classification == "CADRE":
        S = _round(params["abattement_cadre"] * base_abattement)
    else:
        S = _round(params["abattement_autre"] * base_abattement)

    # T, U, V : exonérations des indemnités
    taux_log, plaf_log = params["exo_logement"]
    taux_fct, plaf_fct = params["exo_fonction"]
    taux_trp, plaf_trp = params["exo_transport"]

    T = _exoneration_indemnite(taux_log, plaf_log, L, R)
    U = _exoneration_indemnite(taux_fct, plaf_fct, M, R)
    V = _exoneration_indemnite(taux_trp, plaf_trp, N, R)

    # W : total des exonérations (abattement + indemnités exonérées)
    W = S + T + U + V

    # X : base imposable (arrondie à la centaine inférieure)
    X = _rounddown_to_hundred(R - W)

    # Y : personnes à charge
    Y = emp.personnes_a_charge

    # Z : IUTS brut (barème progressif)
    Z = compute_iuts_brut(X, params["bareme_iuts"])

    # AA : IUTS net (après réduction pour charges de famille)
    reduction = params["reduction_charges"].get(_charge_key(Y), 1.0)
    AA = _round(Z * reduction)

    # AB : Salaire net (avant retenue obligatoire et prêts)
    AB = O - P - AA

    # AC : Retenue obligatoire 1%
    AC = _round(AB * params["taux_retenue_obligatoire"])

    # AD : Retenue prêt/avance
    AD = emp.retenue_pret

    # AE : Net perçu
    AE = AB - AC - AD

    # AF, AG, AH : charges patronales
    AF = _round(O * params["taux_tpa"])          # TPA 3%
    AG = _round(O * params["taux_cnss_patronale"])  # CNSS patronale 16%
    AH = AF + AG

    # AI, AJ, AK
    AI = O + AH        # coût total employeur
    AJ = AG + P         # CNSS total (salariale + patronale)
    AK = AF + AA         # TPA + IUTS net

    return {
        "numero": emp.numero,
        "nom_prenoms": emp.nom_prenoms,
        "classification": emp.classification,
        # Détail des éléments de gain (utile pour l'affichage détaillé des
        # bulletins de paie)
        "salaire_base": F,
        "prime_anciennete": G,
        "heures_sup": H,
        "sursalaire": I,
        "gratification": J,
        "indemnite_caisse": K,
        "indemnite_logement": L,
        "indemnite_fonction": M,
        "indemnite_transport": N,
        "remuneration_totale": O,
        "cnss_salariale": P,
        "plafond_fiscal": Q,
        "salaire_brut": R,
        "abattement": S,
        "exo_logement": T,
        "exo_fonction": U,
        "exo_transport": V,
        "total_exonerations": W,
        "base_imposable": X,
        "personnes_a_charge": Y,
        "iuts_brut": Z,
        "iuts_net": AA,
        "salaire_net": AB,
        "retenue_obligatoire": AC,
        "retenue_pret": AD,
        "net_percu": AE,
        "tpa_patronale": AF,
        "cnss_patronale": AG,
        "total_charges_patronales": AH,
        "cout_total_employeur": AI,
        "cnss_total": AJ,
        "iuts_plus_tpa": AK,
    }


def find_base_for_target_net(emp_template: Employee, params: dict, target_net: float,
                              target_field: str = "net_percu",
                              lo: float = 0.0, hi: float = 5_000_000.0,
                              tol: float = 1.0, max_iter: int = 80):
    """Simulateur 'net -> base' : trouve, par dichotomie, le salaire de base
    (`salaire_base`) à appliquer à `emp_template` (les autres éléments —
    indemnités, primes, personnes à charge... — restant fixes) pour que le
    résultat calculé (par défaut le Net Perçu) atteigne `target_net`.

    S'appuie sur le fait que le Net Perçu est une fonction croissante (au
    sens large) du salaire de base : chaque franc de base supplémentaire
    produit toujours un peu plus de net, même une fois le plafond CNSS
    atteint ou dans la tranche IUTS la plus haute (taux marginal max 25%,
    donc toujours au moins 75% qui reste).

    Retourne (salaire_base_trouve, résultat_complet_compute_payslip).
    """

    def net_for(base):
        e = replace(emp_template, salaire_base=base)
        r = compute_payslip(e, params)
        return r[target_field], r

    # Élargit la borne haute si besoin pour être sûr d'encadrer la solution.
    net_hi, result_hi = net_for(hi)
    tries = 0
    while net_hi < target_net and tries < 12:
        hi *= 2
        net_hi, result_hi = net_for(hi)
        tries += 1

    net_lo, result_lo = net_for(lo)
    if net_lo >= target_net:
        return lo, result_lo
    if net_hi < target_net:
        # Même avec une base très élevée on n'atteint pas la cible (cas
        # limite improbable) : on renvoie le meilleur essai obtenu.
        return hi, result_hi

    result = result_hi
    mid = hi
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        net_mid, result = net_for(mid)
        if abs(net_mid - target_net) <= tol:
            break
        if net_mid < target_net:
            lo = mid
        else:
            hi = mid
    return mid, result

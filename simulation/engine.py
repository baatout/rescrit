"""Calculation engine — cotisations, IR, scenarios, optimizer."""

from __future__ import annotations

from scipy.optimize import minimize_scalar

from simulation.constants import (
    ABATTEMENT_10_PLAFOND,
    ABATTEMENT_10_PLANCHER,
    ASSIETTE_CSG_COEFF,
    CRDS_SALAIRE,
    CSG_DEDUCTIBLE,
    CSG_NON_DEDUCTIBLE,
    IR_BAREME,
    PASS,
    PARTS_BASE,
    PARTS_QF,
    PATRONALE_AF_PLEIN,
    PATRONALE_AF_REDUIT,
    PATRONALE_APPRENTISSAGE,
    PATRONALE_ATMP,
    PATRONALE_CEG_T1,
    PATRONALE_CEG_T2,
    PATRONALE_CSA,
    PATRONALE_FNAL,
    PATRONALE_FORMATION,
    PATRONALE_MALADIE_PLEIN,
    PATRONALE_MALADIE_REDUIT,
    PATRONALE_RC_T1,
    PATRONALE_RC_T2,
    PATRONALE_VIEILLESSE_DEPLAFONNEE,
    PATRONALE_VIEILLESSE_PLAFONNEE,
    PLAFOND_DEMI_PART,
    PLAFOND_T2,
    PS_CSG,
    PS_CSG_DEDUCTIBLE_IR,
    PS_CRDS,
    PS_SOLIDARITE,
    PS_TOTAL,
    SALARIALE_CEG_T1,
    SALARIALE_CEG_T2,
    SALARIALE_RC_T1,
    SALARIALE_RC_T2,
    SALARIALE_VIEILLESSE_DEPLAFONNEE,
    SALARIALE_VIEILLESSE_PLAFONNEE,
    SEUIL_AF,
    SEUIL_MALADIE,
)


# ---------------------------------------------------------------------------
# Cotisations patronales
# ---------------------------------------------------------------------------

def calc_patronales(gross: float) -> dict:
    """Compute employer contributions on gross salary. Returns breakdown + total."""
    maladie = gross * (PATRONALE_MALADIE_REDUIT if gross <= SEUIL_MALADIE else PATRONALE_MALADIE_PLEIN)
    vieillesse_p = min(gross, PASS) * PATRONALE_VIEILLESSE_PLAFONNEE
    vieillesse_d = gross * PATRONALE_VIEILLESSE_DEPLAFONNEE
    af = gross * (PATRONALE_AF_REDUIT if gross <= SEUIL_AF else PATRONALE_AF_PLEIN)
    atmp = gross * PATRONALE_ATMP
    rc_t1 = min(gross, PASS) * PATRONALE_RC_T1
    rc_t2 = max(0, min(gross, PLAFOND_T2) - PASS) * PATRONALE_RC_T2
    ceg_t1 = min(gross, PASS) * PATRONALE_CEG_T1
    ceg_t2 = max(0, min(gross, PLAFOND_T2) - PASS) * PATRONALE_CEG_T2
    csa = gross * PATRONALE_CSA
    fnal = min(gross, PASS) * PATRONALE_FNAL
    formation = gross * PATRONALE_FORMATION
    apprentissage = gross * PATRONALE_APPRENTISSAGE

    total = (maladie + vieillesse_p + vieillesse_d + af + atmp
             + rc_t1 + rc_t2 + ceg_t1 + ceg_t2 + csa + fnal
             + formation + apprentissage)

    return {
        "maladie": maladie,
        "vieillesse_plafonnee": vieillesse_p,
        "vieillesse_deplafonnee": vieillesse_d,
        "allocations_familiales": af,
        "atmp": atmp,
        "retraite_comp_t1": rc_t1,
        "retraite_comp_t2": rc_t2,
        "ceg_t1": ceg_t1,
        "ceg_t2": ceg_t2,
        "csa": csa,
        "fnal": fnal,
        "formation": formation,
        "apprentissage": apprentissage,
        "total": total,
    }


# ---------------------------------------------------------------------------
# Cotisations salariales
# ---------------------------------------------------------------------------

def calc_salariales(gross: float) -> dict:
    """Compute employee contributions. Returns breakdown, net_received, net_imposable."""
    vieillesse_p = min(gross, PASS) * SALARIALE_VIEILLESSE_PLAFONNEE
    vieillesse_d = gross * SALARIALE_VIEILLESSE_DEPLAFONNEE
    rc_t1 = min(gross, PASS) * SALARIALE_RC_T1
    rc_t2 = max(0, min(gross, PLAFOND_T2) - PASS) * SALARIALE_RC_T2
    ceg_t1 = min(gross, PASS) * SALARIALE_CEG_T1
    ceg_t2 = max(0, min(gross, PLAFOND_T2) - PASS) * SALARIALE_CEG_T2

    assiette_csg = gross * ASSIETTE_CSG_COEFF
    csg_ded = assiette_csg * CSG_DEDUCTIBLE
    csg_non_ded = assiette_csg * CSG_NON_DEDUCTIBLE
    crds = assiette_csg * CRDS_SALAIRE

    cotisations_hors_csg = vieillesse_p + vieillesse_d + rc_t1 + rc_t2 + ceg_t1 + ceg_t2
    total = cotisations_hors_csg + csg_ded + csg_non_ded + crds

    net_received = gross - total
    # Net imposable = gross - cotisations déductibles (tout sauf CSG non déductible et CRDS)
    net_imposable = gross - cotisations_hors_csg - csg_ded

    return {
        "vieillesse_plafonnee": vieillesse_p,
        "vieillesse_deplafonnee": vieillesse_d,
        "retraite_comp_t1": rc_t1,
        "retraite_comp_t2": rc_t2,
        "ceg_t1": ceg_t1,
        "ceg_t2": ceg_t2,
        "csg_deductible": csg_ded,
        "csg_non_deductible": csg_non_ded,
        "crds": crds,
        "total": total,
        "net_received": net_received,
        "net_imposable": net_imposable,
    }


# ---------------------------------------------------------------------------
# Net → Gross inversion (closed-form piecewise)
# ---------------------------------------------------------------------------

def _salariale_rate_below_pass() -> float:
    """Total salariale rate on gross for gross ≤ PASS."""
    return (SALARIALE_VIEILLESSE_PLAFONNEE + SALARIALE_VIEILLESSE_DEPLAFONNEE
            + SALARIALE_RC_T1 + SALARIALE_CEG_T1
            + ASSIETTE_CSG_COEFF * (CSG_DEDUCTIBLE + CSG_NON_DEDUCTIBLE + CRDS_SALAIRE))


def _salariale_rate_above_pass() -> float:
    """Marginal salariale rate on gross for the portion above PASS."""
    return (SALARIALE_VIEILLESSE_DEPLAFONNEE
            + SALARIALE_RC_T2 + SALARIALE_CEG_T2
            + ASSIETTE_CSG_COEFF * (CSG_DEDUCTIBLE + CSG_NON_DEDUCTIBLE + CRDS_SALAIRE))


def net_to_gross(net: float) -> float:
    """Convert net salary (after salariales) to gross. Closed-form piecewise inversion."""
    if net <= 0:
        return 0.0
    rate_low = _salariale_rate_below_pass()
    net_at_pass = PASS * (1 - rate_low)

    if net <= net_at_pass:
        return net / (1 - rate_low)

    rate_high = _salariale_rate_above_pass()
    return PASS + (net - net_at_pass) / (1 - rate_high)


# ---------------------------------------------------------------------------
# Prélèvements sociaux patrimoniaux (on BIC)
# ---------------------------------------------------------------------------

def calc_ps_patrimoine(bic: float) -> dict:
    """Social levies on BIC (patrimoine regime) at PS_TOTAL rate."""
    csg = bic * PS_CSG
    crds = bic * PS_CRDS
    solidarite = bic * PS_SOLIDARITE
    total = bic * PS_TOTAL
    csg_deductible = bic * PS_CSG_DEDUCTIBLE_IR
    return {
        "csg": csg,
        "crds": crds,
        "solidarite": solidarite,
        "total": total,
        "csg_deductible_ir": csg_deductible,
    }


# ---------------------------------------------------------------------------
# Impôt sur le revenu
# ---------------------------------------------------------------------------

def _ir_brut(revenu_imposable: float, parts: float) -> tuple[float, float, list[dict]]:
    """Compute IR before QF plafonnement. Returns (ir, quotient, tranches)."""
    quotient = revenu_imposable / parts if parts else 0
    impot_par_part = 0.0
    tranches = []
    prev = 0
    for seuil, taux in IR_BAREME:
        tranche = min(quotient, seuil) - prev
        if tranche <= 0:
            break
        impot_tranche = tranche * taux
        impot_par_part += impot_tranche
        tranches.append({"de": prev, "a": min(quotient, seuil), "taux": taux, "impot": impot_tranche})
        prev = seuil
    return impot_par_part * parts, quotient, tranches


def calc_ir(revenu_imposable: float, parts: float = PARTS_QF) -> dict:
    """Compute IR with QF plafonnement. Returns IR amount and details."""
    ir_avec_qf, quotient, tranches = _ir_brut(revenu_imposable, parts)
    ir_sans_qf, _, _ = _ir_brut(revenu_imposable, PARTS_BASE)

    demi_parts_sup = parts - PARTS_BASE  # 0.5 for 1 child
    plafond = demi_parts_sup * PLAFOND_DEMI_PART * 2  # each demi-part gives 1759€ max
    avantage = ir_sans_qf - ir_avec_qf

    if avantage > plafond:
        ir_final = ir_sans_qf - plafond
    else:
        ir_final = ir_avec_qf

    return {
        "revenu_imposable": revenu_imposable,
        "parts": parts,
        "quotient": quotient,
        "tranches": tranches,
        "ir_avant_plafonnement": ir_avec_qf,
        "ir_sans_qf": ir_sans_qf,
        "avantage_qf": avantage,
        "plafond_qf": plafond,
        "plafonne": avantage > plafond,
        "ir": max(ir_final, 0),
    }


def _abattement_10(salaire_net_imposable: float) -> float:
    """10% professional expenses deduction on salary, capped."""
    raw = salaire_net_imposable * 0.10
    return max(ABATTEMENT_10_PLANCHER, min(raw, ABATTEMENT_10_PLAFOND))


# ---------------------------------------------------------------------------
# Full scenarios
# ---------------------------------------------------------------------------

def scenario_no_salary(resultat: float) -> dict:
    """No salary: full BIC taxed at PS patrimoine + IR."""
    bic = resultat  # entire result = BIC for the foyer
    ps = calc_ps_patrimoine(bic)

    # IR: BIC - CSG déductible (6.8%)
    revenu_imposable = bic - ps["csg_deductible_ir"]
    ir = calc_ir(revenu_imposable)

    net_en_poche = resultat - ps["total"] - ir["ir"]
    total_prelev = ps["total"] + ir["ir"]

    return {
        "resultat": resultat,
        "salaire_net": 0,
        "salaire_brut": 0,
        "patronales": {"total": 0},
        "salariales": {"total": 0, "net_received": 0, "net_imposable": 0},
        "cout_total_salaire": 0,
        "bic": bic,
        "ps": ps,
        "ir": ir,
        "net_en_poche": net_en_poche,
        "total_prelevements": total_prelev,
        "taux_effectif": total_prelev / resultat if resultat > 0 else 0,
    }


def scenario_with_salary(resultat: float, net_salary: float) -> dict:
    """With salary: part goes to salary (with charges), rest is BIC."""
    if net_salary <= 0:
        return scenario_no_salary(resultat)

    gross = net_to_gross(net_salary)
    patronales = calc_patronales(gross)
    salariales = calc_salariales(gross)

    cout_total_salaire = gross + patronales["total"]

    # BIC résiduel = résultat - coût total du salaire pour la SAS
    bic = max(0, resultat - cout_total_salaire)

    # PS on BIC
    ps = calc_ps_patrimoine(bic)

    # IR calculation
    # Salary part: net_imposable with 10% abattement
    sal_net_imposable = salariales["net_imposable"]
    abattement = _abattement_10(sal_net_imposable)
    salaire_apres_abattement = sal_net_imposable - abattement

    # BIC part: BIC - CSG déductible patrimoine
    bic_imposable = bic - ps["csg_deductible_ir"]

    revenu_imposable = salaire_apres_abattement + bic_imposable
    ir = calc_ir(max(0, revenu_imposable))

    net_en_poche = salariales["net_received"] + bic - ps["total"] - ir["ir"]
    total_prelev = patronales["total"] + salariales["total"] + ps["total"] + ir["ir"]

    return {
        "resultat": resultat,
        "salaire_net": net_salary,
        "salaire_brut": gross,
        "patronales": patronales,
        "salariales": salariales,
        "cout_total_salaire": cout_total_salaire,
        "bic": bic,
        "ps": ps,
        "abattement_10": abattement,
        "salaire_apres_abattement": salaire_apres_abattement,
        "bic_imposable": bic_imposable,
        "ir": ir,
        "net_en_poche": net_en_poche,
        "total_prelevements": total_prelev,
        "taux_effectif": total_prelev / resultat if resultat > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def _max_feasible_net(resultat: float) -> float:
    """Max net salary such that BIC ≥ 0 (binary search for safety)."""
    lo, hi = 0, resultat
    for _ in range(60):
        mid = (lo + hi) / 2
        gross = net_to_gross(mid)
        cout = gross + calc_patronales(gross)["total"]
        if cout <= resultat:
            lo = mid
        else:
            hi = mid
    return lo


def find_optimal_salary(resultat: float) -> dict:
    """Find net salary that maximizes net_en_poche."""
    max_net = _max_feasible_net(resultat)
    if max_net <= 0:
        s = scenario_no_salary(resultat)
        return {"optimal_net_salary": 0, "scenario": s}

    def neg_net(x):
        return -scenario_with_salary(resultat, x)["net_en_poche"]

    result = minimize_scalar(neg_net, bounds=(0, max_net), method="bounded",
                             options={"xatol": 10, "maxiter": 200})
    opt_salary = result.x
    # Also check endpoints
    candidates = [
        (0, scenario_no_salary(resultat)["net_en_poche"]),
        (opt_salary, scenario_with_salary(resultat, opt_salary)["net_en_poche"]),
        (max_net, scenario_with_salary(resultat, max_net)["net_en_poche"]),
    ]
    best_salary, best_net = max(candidates, key=lambda c: c[1])
    scenario = scenario_with_salary(resultat, best_salary) if best_salary > 0 else scenario_no_salary(resultat)
    return {"optimal_net_salary": best_salary, "scenario": scenario}


def compute_curve(resultat: float, n_points: int = 200) -> list[dict]:
    """Compute net_en_poche for a range of salary values (for charting)."""
    max_net = _max_feasible_net(resultat)
    if max_net <= 0:
        return [{"salaire_net": 0, **scenario_no_salary(resultat)}]

    step = max_net / n_points
    points = []
    for i in range(n_points + 1):
        net_sal = i * step
        s = scenario_with_salary(resultat, net_sal) if net_sal > 0 else scenario_no_salary(resultat)
        points.append({
            "salaire_net": net_sal,
            "net_en_poche": s["net_en_poche"],
            "total_prelevements": s["total_prelevements"],
            "taux_effectif": s["taux_effectif"],
            "cotisations_sociales": s["patronales"]["total"] + s["salariales"]["total"] + s["ps"]["total"],
            "ir": s["ir"]["ir"],
        })
    return points

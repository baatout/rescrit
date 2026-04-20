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
    JEI_SALARY_CAP,
    JEI_RD_THRESHOLD,
    CIR_RATE,
    CIR_FORFAIT_FONCTIONNEMENT,
    PATRONALE_CHOMAGE,
    PATRONALE_AGS,
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


def calc_patronales_jei(gross: float) -> dict:
    """JEI: exempt maladie, vieillesse, AF on portion up to 4.5 SMIC cap."""
    normal = calc_patronales(gross)
    capped = min(gross, JEI_SALARY_CAP)

    # Exoneration amounts (same rate logic as normal, applied on capped portion)
    exo_maladie = capped * (PATRONALE_MALADIE_REDUIT if gross <= SEUIL_MALADIE else PATRONALE_MALADIE_PLEIN)
    exo_vieillesse_p = min(capped, PASS) * PATRONALE_VIEILLESSE_PLAFONNEE
    exo_vieillesse_d = capped * PATRONALE_VIEILLESSE_DEPLAFONNEE
    exo_af = capped * (PATRONALE_AF_REDUIT if gross <= SEUIL_AF else PATRONALE_AF_PLEIN)
    exoneration = exo_maladie + exo_vieillesse_p + exo_vieillesse_d + exo_af

    result = dict(normal)
    result["maladie"] -= exo_maladie
    result["vieillesse_plafonnee"] -= exo_vieillesse_p
    result["vieillesse_deplafonnee"] -= exo_vieillesse_d
    result["allocations_familiales"] -= exo_af
    result["exoneration_jei"] = exoneration
    result["total"] -= exoneration
    return result


def _add_chomage(pat: dict, gross: float) -> dict:
    """Add chômage + AGS to a patronales dict (for regular employees, not mandataires)."""
    result = dict(pat)
    result["chomage"] = gross * PATRONALE_CHOMAGE
    result["ags"] = gross * PATRONALE_AGS
    result["total"] += result["chomage"] + result["ags"]
    return result


def calc_patronales_employee(gross: float) -> dict:
    """Regular employee (not mandataire) — includes chômage + AGS."""
    return _add_chomage(calc_patronales(gross), gross)


def calc_patronales_employee_jei(gross: float) -> dict:
    """Regular employee with JEI exoneration — includes chômage + AGS."""
    return _add_chomage(calc_patronales_jei(gross), gross)


# ---------------------------------------------------------------------------
# CIR (Crédit d'Impôt Recherche)
# ---------------------------------------------------------------------------

def calc_cir(gross_rd: float, patronales_rd: dict) -> dict:
    """CIR on R&D personnel. Only CIR-eligible patronales (after JEI exoneration)."""
    # Eligible: AT/MP, RC T1/T2, CEG T1/T2, chômage, AGS
    # NOT eligible: CSA, FNAL, formation, apprentissage (nor maladie/vieillesse/AF — zeroed by JEI)
    eligible_keys = ["atmp", "retraite_comp_t1", "retraite_comp_t2",
                     "ceg_t1", "ceg_t2", "chomage", "ags"]
    eligible_pat = sum(patronales_rd.get(k, 0) for k in eligible_keys)
    base = gross_rd + eligible_pat
    forfait = base * CIR_FORFAIT_FONCTIONNEMENT
    cir = (base + forfait) * CIR_RATE
    return {
        "base_personnel": base,
        "eligible_patronales": eligible_pat,
        "forfait": forfait,
        "total_eligible": base + forfait,
        "cir": cir,
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


def _build_salary_scenario(resultat: float, net_salary: float, patronales_fn=calc_patronales) -> dict:
    """Core salary scenario logic, parametrized by patronales calculation."""
    if net_salary <= 0:
        return scenario_no_salary(resultat)

    gross = net_to_gross(net_salary)
    patronales = patronales_fn(gross)
    salariales = calc_salariales(gross)

    cout_total_salaire = gross + patronales["total"]
    bic = max(0, resultat - cout_total_salaire)
    ps = calc_ps_patrimoine(bic)

    sal_net_imposable = salariales["net_imposable"]
    abattement = _abattement_10(sal_net_imposable)
    salaire_apres_abattement = sal_net_imposable - abattement
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


def scenario_with_salary(resultat: float, net_salary: float) -> dict:
    """With salary: part goes to salary (with charges), rest is BIC."""
    return _build_salary_scenario(resultat, net_salary, calc_patronales)


def scenario_jei(resultat: float, net_salary: float) -> dict:
    """With salary + JEI: exempt maladie/vieillesse/AF on patronales."""
    return _build_salary_scenario(resultat, net_salary, calc_patronales_jei)


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def _max_feasible_net(resultat: float, patronales_fn=calc_patronales) -> float:
    """Max net salary such that BIC ≥ 0 (binary search for safety)."""
    lo, hi = 0, resultat
    for _ in range(60):
        mid = (lo + hi) / 2
        gross = net_to_gross(mid)
        cout = gross + patronales_fn(gross)["total"]
        if cout <= resultat:
            lo = mid
        else:
            hi = mid
    return lo


def _find_optimal(resultat: float, scenario_fn, patronales_fn) -> dict:
    """Find net salary that maximizes net_en_poche for a given scenario function."""
    max_net = _max_feasible_net(resultat, patronales_fn)
    if max_net <= 0:
        s = scenario_no_salary(resultat)
        return {"optimal_net_salary": 0, "scenario": s}

    def neg_net(x):
        return -scenario_fn(resultat, x)["net_en_poche"]

    result = minimize_scalar(neg_net, bounds=(0, max_net), method="bounded",
                             options={"xatol": 10, "maxiter": 200})
    opt_salary = result.x
    candidates = [
        (0, scenario_no_salary(resultat)["net_en_poche"]),
        (opt_salary, scenario_fn(resultat, opt_salary)["net_en_poche"]),
        (max_net, scenario_fn(resultat, max_net)["net_en_poche"]),
    ]
    best_salary, best_net = max(candidates, key=lambda c: c[1])
    scenario = scenario_fn(resultat, best_salary) if best_salary > 0 else scenario_no_salary(resultat)
    return {"optimal_net_salary": best_salary, "scenario": scenario}


def find_optimal_salary(resultat: float) -> dict:
    return _find_optimal(resultat, scenario_with_salary, calc_patronales)


def find_optimal_salary_jei(resultat: float) -> dict:
    return _find_optimal(resultat, scenario_jei, calc_patronales_jei)


def compute_curve(resultat: float, n_points: int = 200) -> list[dict]:
    """Compute net_en_poche for a range of salary values (for charting)."""
    max_net = _max_feasible_net(resultat)
    max_net_jei = _max_feasible_net(resultat, calc_patronales_jei)
    hi = max(max_net, max_net_jei)
    if hi <= 0:
        s = scenario_no_salary(resultat)
        return [{"salaire_net": 0, "net_en_poche": s["net_en_poche"],
                 "net_en_poche_jei": s["net_en_poche"],
                 "total_prelevements": s["total_prelevements"],
                 "cotisations_sociales": s["ps"]["total"], "ir": s["ir"]["ir"]}]

    step = hi / n_points
    points = []
    for i in range(n_points + 1):
        net_sal = i * step
        if net_sal <= 0:
            s = scenario_no_salary(resultat)
            s_jei = s
        else:
            s = scenario_with_salary(resultat, net_sal)
            s_jei = scenario_jei(resultat, net_sal)
        points.append({
            "salaire_net": net_sal,
            "net_en_poche": s["net_en_poche"],
            "net_en_poche_jei": s_jei["net_en_poche"],
            "total_prelevements": s["total_prelevements"],
            "taux_effectif": s["taux_effectif"],
            "cotisations_sociales": s["patronales"]["total"] + s["salariales"]["total"] + s["ps"]["total"],
            "ir": s["ir"]["ir"],
        })
    return points


# ---------------------------------------------------------------------------
# Split scenario: Amine (président, non-R&D) + Nesrine (salariée, 100% R&D)
# ---------------------------------------------------------------------------

_EMPTY_PAT = {"total": 0, "chomage": 0, "ags": 0}
_EMPTY_SAL = {"total": 0, "net_received": 0, "net_imposable": 0}


def scenario_split(resultat: float, net_amine: float, net_nesrine: float,
                   autres_charges: float = 0) -> dict:
    """Split salary: Amine (normal) + Nesrine (JEI + chômage). CIR on Nesrine."""
    # Amine — président, no chômage
    if net_amine > 0:
        gross_a = net_to_gross(net_amine)
        pat_a = calc_patronales(gross_a)
        sal_a = calc_salariales(gross_a)
        cout_a = gross_a + pat_a["total"]
        abat_a = _abattement_10(sal_a["net_imposable"])
    else:
        gross_a, pat_a, sal_a, cout_a, abat_a = 0, _EMPTY_PAT, _EMPTY_SAL, 0, 0

    # Nesrine — salariée, JEI, chômage + AGS
    if net_nesrine > 0:
        gross_n = net_to_gross(net_nesrine)
        pat_n = calc_patronales_employee_jei(gross_n)
        sal_n = calc_salariales(gross_n)
        cout_n = gross_n + pat_n["total"]
        abat_n = _abattement_10(sal_n["net_imposable"])
        cir = calc_cir(gross_n, pat_n)
    else:
        gross_n, pat_n, sal_n, cout_n, abat_n = 0, _EMPTY_PAT, _EMPTY_SAL, 0, 0
        cir = {"base_personnel": 0, "eligible_patronales": 0, "forfait": 0, "total_eligible": 0, "cir": 0}

    # JEI threshold: R&D cost / total charges déductibles
    total_charges = cout_a + cout_n + autres_charges
    rd_charges = cout_n  # Nesrine's full cost (actual, not forfait)
    jei_ratio = rd_charges / total_charges if total_charges > 0 else 0

    # BIC
    bic = max(0, resultat - cout_a - cout_n)
    ps = calc_ps_patrimoine(bic)

    # IR — both salaries get 10% abattement
    sal_imposable = 0
    if net_amine > 0:
        sal_imposable += sal_a["net_imposable"] - abat_a
    if net_nesrine > 0:
        sal_imposable += sal_n["net_imposable"] - abat_n
    bic_imposable = bic - ps["csg_deductible_ir"]
    revenu_imposable = max(0, sal_imposable + bic_imposable)
    ir = calc_ir(revenu_imposable)

    # CIR imputed on IR
    ir_before_cir = ir["ir"]
    ir_after_cir = max(0, ir_before_cir - cir["cir"])
    cir_used = ir_before_cir - ir_after_cir
    cir_restant = cir["cir"] - cir_used

    net_en_poche = (sal_a.get("net_received", 0) + sal_n.get("net_received", 0)
                    + bic - ps["total"] - ir_after_cir)
    total_prelev = (pat_a["total"] + sal_a["total"] + pat_n["total"] + sal_n["total"]
                    + ps["total"] + ir_after_cir)

    return {
        "resultat": resultat,
        "amine": {"net": net_amine, "gross": gross_a, "patronales": pat_a,
                  "salariales": sal_a, "cout": cout_a, "abattement": abat_a},
        "nesrine": {"net": net_nesrine, "gross": gross_n, "patronales": pat_n,
                    "salariales": sal_n, "cout": cout_n, "abattement": abat_n},
        "cir": cir,
        "cir_used": cir_used,
        "cir_restant": cir_restant,
        "jei_ratio": jei_ratio,
        "jei_qualified": jei_ratio >= JEI_RD_THRESHOLD,
        "autres_charges": autres_charges,
        "bic": bic,
        "ps": ps,
        "ir": ir,
        "ir_before_cir": ir_before_cir,
        "ir_after_cir": ir_after_cir,
        "net_en_poche": net_en_poche,
        "total_prelevements": total_prelev,
        "taux_effectif": total_prelev / resultat if resultat > 0 else 0,
    }


def find_optimal_split(resultat: float, net_amine: float,
                       autres_charges: float = 0) -> dict:
    """Optimize Nesrine's salary (Amine fixed) to maximize net_en_poche."""
    # Max feasible for Nesrine given Amine's cost
    if net_amine > 0:
        gross_a = net_to_gross(net_amine)
        cout_a = gross_a + calc_patronales(gross_a)["total"]
    else:
        cout_a = 0
    remaining = resultat - cout_a
    if remaining <= 0:
        return {"optimal_net_nesrine": 0,
                "scenario": scenario_split(resultat, net_amine, 0, autres_charges)}

    max_n = _max_feasible_net(remaining, calc_patronales_employee_jei)
    if max_n <= 0:
        return {"optimal_net_nesrine": 0,
                "scenario": scenario_split(resultat, net_amine, 0, autres_charges)}

    def neg_net(x):
        return -scenario_split(resultat, net_amine, x, autres_charges)["net_en_poche"]

    result = minimize_scalar(neg_net, bounds=(0, max_n), method="bounded",
                             options={"xatol": 10, "maxiter": 200})
    candidates = [
        (0, scenario_split(resultat, net_amine, 0, autres_charges)["net_en_poche"]),
        (result.x, scenario_split(resultat, net_amine, result.x, autres_charges)["net_en_poche"]),
        (max_n, scenario_split(resultat, net_amine, max_n, autres_charges)["net_en_poche"]),
    ]
    best_n, _ = max(candidates, key=lambda c: c[1])
    return {"optimal_net_nesrine": best_n,
            "scenario": scenario_split(resultat, net_amine, best_n, autres_charges)}


def compute_curve_split(resultat: float, net_amine: float,
                        autres_charges: float = 0, n_points: int = 200) -> list[dict]:
    """Sweep Nesrine's salary for charting (Amine fixed)."""
    if net_amine > 0:
        gross_a = net_to_gross(net_amine)
        cout_a = gross_a + calc_patronales(gross_a)["total"]
    else:
        cout_a = 0
    remaining = resultat - cout_a
    max_n = _max_feasible_net(max(0, remaining), calc_patronales_employee_jei) if remaining > 0 else 0

    points = []
    step = max_n / n_points if max_n > 0 else 0
    for i in range(n_points + 1):
        net_n = i * step
        s = scenario_split(resultat, net_amine, net_n, autres_charges)
        points.append({
            "salaire_nesrine": net_n,
            "net_en_poche": s["net_en_poche"],
            "ir_after_cir": s["ir_after_cir"],
            "cir": s["cir"]["cir"],
            "jei_ratio": s["jei_ratio"],
            "taux_effectif": s["taux_effectif"],
        })
    return points

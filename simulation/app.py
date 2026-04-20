"""Streamlit app — SAS IR salary optimization simulator."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go

import sys
from pathlib import Path

# Allow running via `streamlit run simulation/app.py` from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.engine import (
    calc_patronales_jei,
    compute_curve,
    compute_curve_split,
    find_optimal_salary,
    find_optimal_salary_jei,
    find_optimal_split,
    net_to_gross,
    scenario_jei,
    scenario_no_salary,
    scenario_split,
    scenario_with_salary,
    _max_feasible_net,
    _salariale_rate_below_pass,
    _salariale_rate_above_pass,
)
from simulation.constants import (
    PASS, ASSIETTE_CSG_COEFF, PS_CSG, PS_CRDS, PS_SOLIDARITE, PS_TOTAL,
    CIR_RATE, CIR_FORFAIT_FONCTIONNEMENT, JEI_RD_THRESHOLD,
)
from simulation.sankey import build_sankey_no_salary, build_sankey_with_salary

st.set_page_config(page_title="SAS IR — Simulateur", layout="wide")
st.title("SAS IR — Simulateur salaire / BIC")
st.caption("Beluga Paris — Optimisation rémunération président (2026)")

# Derived labels from constants (single source of truth)
PS_TOTAL_PCT = f"{PS_TOTAL:.1%}".replace(".", ",")
PS_CSG_PCT = f"{PS_CSG:.1%}".replace(".", ",")
PS_CRDS_PCT = f"{PS_CRDS:.1%}".replace(".", ",")
PS_SOL_PCT = f"{PS_SOLIDARITE:.1%}".replace(".", ",")

# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Paramètres")
    resultat = st.number_input(
        "Résultat avant rémunération (€)",
        min_value=0, max_value=1_000_000, value=112_000, step=1_000,
    )

    mode = st.radio("Mode", ["Salaire unique", "Split (Amine + Nesrine)"])
    split_mode = mode == "Split (Amine + Nesrine)"

    if split_mode:
        max_net = int(_max_feasible_net(resultat))
        net_amine = st.slider("Salaire net Amine (président, non-R&D)", min_value=0,
                              max_value=max(max_net, 1), value=0, step=500)
        net_nesrine = st.slider("Salaire net Nesrine (salariée, 100% R&D)", min_value=0,
                                max_value=max(max_net, 1), value=25_000, step=500)
        autres_charges = st.number_input("Autres charges annuelles (€)",
                                         min_value=0, max_value=500_000, value=10_000, step=1_000,
                                         help="Loyer, services, comptabilité… pour le seuil JEI 20%")
        run_optim = st.checkbox("Trouver le salaire optimal Nesrine", value=False)
        jei = True  # Split mode implies JEI
        salaire_net = 0  # Not used in split mode
    else:
        max_net = int(_max_feasible_net(resultat))
        salaire_net = st.slider(
            "Salaire net annuel avant IR (€)",
            min_value=0, max_value=max(max_net, 1), value=0, step=500,
        )
        run_optim = st.checkbox("Trouver le salaire optimal", value=False)
        jei = st.checkbox("JEI (Jeune Entreprise Innovante)", value=False)
        net_amine = 0
        net_nesrine = 0
        autres_charges = 0

# ---------------------------------------------------------------------------
# Compute scenarios
# ---------------------------------------------------------------------------
s_no_sal = scenario_no_salary(resultat)
s_with_sal = scenario_with_salary(resultat, salaire_net) if not split_mode else None
s_jei = scenario_jei(resultat, salaire_net) if jei and not split_mode else None
s_split = scenario_split(resultat, net_amine, net_nesrine, autres_charges) if split_mode else None

if run_optim:
    with st.spinner("Optimisation en cours..."):
        if split_mode:
            optim_split = find_optimal_split(resultat, net_amine, autres_charges)
            optim = None
            optim_jei = None
        else:
            optim = find_optimal_salary(resultat)
            optim_jei = find_optimal_salary_jei(resultat) if jei else None
            optim_split = None
else:
    optim = optim_jei = optim_split = None

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def fmt(v: float) -> str:
    return f"{v:,.0f} €".replace(",", " ")


def fmtn(v: float) -> str:
    """Format number without € sign."""
    return f"{v:,.0f}".replace(",", " ")


def pct(v: float) -> str:
    return f"{v:.1%}"


def metric_with_detail(label: str, value: str, detail_md: str, key: str):
    """Display a metric value with an expandable formula detail."""
    st.markdown(f"**{label}**")
    st.markdown(f"### {value}")
    with st.expander("Voir le calcul", expanded=False):
        st.markdown(detail_md)


def ir_detail(ir: dict) -> str:
    """Build markdown for IR barème breakdown."""
    lines = [
        f"**Revenu imposable** = {fmt(ir['revenu_imposable'])}",
        f"**Quotient familial** = {fmtn(ir['revenu_imposable'])} / {ir['parts']} parts = {fmtn(ir['quotient'])}",
        "",
        "| Tranche | Taux | Impôt |",
        "|---------|------|-------|",
    ]
    for t in ir["tranches"]:
        lines.append(f"| {fmtn(t['de'])} → {fmtn(t['a'])} | {t['taux']:.0%} | {fmt(t['impot'])} |")

    impot_par_part = sum(t["impot"] for t in ir["tranches"])
    lines.append(f"\n**Impôt par part** = {fmt(impot_par_part)}")
    lines.append(f"**× {ir['parts']} parts** = {fmt(ir['ir_avant_plafonnement'])}")

    if ir["plafonne"]:
        lines.append(f"\n*Plafonnement QF* : avantage = {fmt(ir['avantage_qf'])}, "
                      f"plafond = {fmt(ir['plafond_qf'])} → plafonné")
        lines.append(f"**IR final** = {fmt(ir['ir_sans_qf'])} - {fmt(ir['plafond_qf'])} = **{fmt(ir['ir'])}**")
    else:
        lines.append(f"\n*Plafonnement QF* : avantage = {fmt(ir['avantage_qf'])} "
                      f"≤ plafond {fmt(ir['plafond_qf'])} → non plafonné")
        lines.append(f"**IR final** = **{fmt(ir['ir'])}**")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_compare, tab_sankey, tab_optim, tab_doc, tab_plan = st.tabs(["Comparaison", "Diagramme Sankey", "Optimisation", "Documentation JEI & CIR", "Plan d'action"])

# --- Helper: render "sans salaire" column ---
def render_no_salary_col(s):
    st.subheader("Sans salaire")
    ps = s["ps"]
    ir = s["ir"]
    metric_with_detail("BIC (100%)", fmt(s["bic"]),
        f"= Résultat SAS = **{fmt(s['resultat'])}**", key="ns_bic")
    metric_with_detail(f"PS {PS_TOTAL_PCT}", fmt(ps["total"]),
        f"| Contribution | Taux | Montant |\n|---|---|---|\n"
        f"| CSG | {PS_CSG_PCT} | {fmt(ps['csg'])} |\n"
        f"| CRDS | {PS_CRDS_PCT} | {fmt(ps['crds'])} |\n"
        f"| Solidarité | {PS_SOL_PCT} | {fmt(ps['solidarite'])} |\n"
        f"| **Total** | **{PS_TOTAL_PCT}** | **{fmt(ps['total'])}** |", key="ns_ps")
    ir_formula = (f"**Rev. imposable** = BIC - CSG déd. = {fmt(s['bic'])} - {fmt(ps['csg_deductible_ir'])} "
                  f"= **{fmt(ir['revenu_imposable'])}**\n\n---\n\n" + ir_detail(ir))
    metric_with_detail("IR", fmt(ir["ir"]), ir_formula, key="ns_ir")
    metric_with_detail("Total prélevé", fmt(s["total_prelevements"]),
        f"= {fmt(ps['total'])} + {fmt(ir['ir'])} = **{fmt(s['total_prelevements'])}**", key="ns_total")
    metric_with_detail("Net en poche", fmt(s["net_en_poche"]),
        f"= {fmt(s['resultat'])} - {fmt(ps['total'])} - {fmt(ir['ir'])} = **{fmt(s['net_en_poche'])}**", key="ns_net")
    metric_with_detail("Taux effectif", pct(s["taux_effectif"]),
        f"= {fmt(s['total_prelevements'])} / {fmt(s['resultat'])}", key="ns_taux")


# --- Tab 1: Comparison ---
with tab_compare:
  if split_mode:
    # ---- SPLIT MODE ----
    col1, col2 = st.columns(2)
    with col1:
        render_no_salary_col(s_no_sal)

    with col2:
        sp = s_split
        st.subheader("Split JEI + CIR")

        # JEI threshold indicator
        ratio_pct = f"{sp['jei_ratio']:.1%}"
        if sp["jei_qualified"]:
            st.success(f"Seuil JEI : {ratio_pct} ≥ 20% des charges déductibles")
        else:
            st.warning(f"Seuil JEI : {ratio_pct} < 20% — JEI non qualifié !")

        # Amine
        a = sp["amine"]
        if net_amine > 0:
            metric_with_detail("Amine — salaire brut", fmt(a["gross"]),
                f"Net {fmt(net_amine)} → Brut {fmt(a['gross'])}\n\n"
                f"Patronales (président, pas de chômage) = **{fmt(a['patronales']['total'])}**\n\n"
                f"Coût total SAS = {fmt(a['cout'])}", key="sp_amine")
        else:
            st.markdown("**Amine** : pas de salaire")

        # Nesrine
        n = sp["nesrine"]
        if net_nesrine > 0:
            pat_n = n["patronales"]
            exo = pat_n.get("exoneration_jei", 0)
            metric_with_detail("Nesrine — salaire brut", fmt(n["gross"]),
                f"Net {fmt(net_nesrine)} → Brut {fmt(n['gross'])}\n\n"
                f"**Patronales JEI + chômage :**\n\n"
                f"| Cotisation | Montant |\n|---|---|\n"
                f"| ~~Maladie~~ (exo JEI) | {fmt(pat_n['maladie'])} |\n"
                f"| ~~Vieillesse~~ (exo JEI) | {fmt(pat_n['vieillesse_plafonnee'] + pat_n['vieillesse_deplafonnee'])} |\n"
                f"| ~~AF~~ (exo JEI) | {fmt(pat_n['allocations_familiales'])} |\n"
                f"| AT/MP | {fmt(pat_n['atmp'])} |\n"
                f"| Retraite comp. | {fmt(pat_n['retraite_comp_t1'] + pat_n['retraite_comp_t2'])} |\n"
                f"| CEG | {fmt(pat_n['ceg_t1'] + pat_n['ceg_t2'])} |\n"
                f"| Chômage | {fmt(pat_n.get('chomage', 0))} |\n"
                f"| AGS | {fmt(pat_n.get('ags', 0))} |\n"
                f"| Autres (CSA, FNAL, form., app.) | {fmt(pat_n['csa'] + pat_n['fnal'] + pat_n['formation'] + pat_n['apprentissage'])} |\n"
                f"| **Total** | **{fmt(pat_n['total'])}** |\n\n"
                f"Exonération JEI = **-{fmt(exo)}**\n\n"
                f"Coût total SAS = {fmt(n['cout'])}", key="sp_nesrine")
        else:
            st.markdown("**Nesrine** : pas de salaire")

        # CIR
        cir = sp["cir"]
        if cir["cir"] > 0:
            metric_with_detail("CIR (Crédit d'Impôt Recherche)", fmt(cir["cir"]),
                f"**Base** = Brut + patronales CIR-éligibles\n\n"
                f"= {fmt(n['gross'])} + {fmt(cir['eligible_patronales'])} = **{fmt(cir['base_personnel'])}**\n\n"
                f"**Forfait fonctionnement** = {fmt(cir['base_personnel'])} × 40% = **{fmt(cir['forfait'])}**\n\n"
                f"**Total éligible** = {fmt(cir['total_eligible'])}\n\n"
                f"**CIR** = {fmt(cir['total_eligible'])} × 30% = **{fmt(cir['cir'])}**",
                key="sp_cir")

        # BIC, PS, IR
        metric_with_detail("BIC résiduel", fmt(sp["bic"]),
            f"= {fmt(sp['resultat'])} - {fmt(a['cout'])} - {fmt(n['cout'])} = **{fmt(sp['bic'])}**",
            key="sp_bic")

        ps_sp = sp["ps"]
        metric_with_detail(f"PS {PS_TOTAL_PCT} (sur BIC)", fmt(ps_sp["total"]),
            f"= {fmt(sp['bic'])} × {PS_TOTAL_PCT} = **{fmt(ps_sp['total'])}**", key="sp_ps")

        ir_sp = sp["ir"]
        metric_with_detail("IR avant CIR", fmt(sp["ir_before_cir"]), ir_detail(ir_sp), key="sp_ir")

        if cir["cir"] > 0:
            metric_with_detail("IR après CIR", fmt(sp["ir_after_cir"]),
                f"= max(0, {fmt(sp['ir_before_cir'])} - {fmt(cir['cir'])}) = **{fmt(sp['ir_after_cir'])}**"
                + (f"\n\nCIR restant (report 3 ans) = **{fmt(sp['cir_restant'])}**" if sp["cir_restant"] > 0 else ""),
                key="sp_ir_after")

        metric_with_detail("Net en poche", fmt(sp["net_en_poche"]),
            f"= Salaires nets + BIC - PS - IR après CIR\n\n"
            f"= {fmt(a['salariales'].get('net_received', 0))} + {fmt(n['salariales'].get('net_received', 0))} "
            f"+ {fmt(sp['bic'])} - {fmt(ps_sp['total'])} - {fmt(sp['ir_after_cir'])}\n\n"
            f"= **{fmt(sp['net_en_poche'])}**", key="sp_net")

        metric_with_detail("Taux effectif", pct(sp["taux_effectif"]),
            f"= {fmt(sp['total_prelevements'])} / {fmt(sp['resultat'])}", key="sp_taux")

    # Delta
    delta_split = sp["net_en_poche"] - s_no_sal["net_en_poche"]
    color_sp = "green" if delta_split > 0 else "red"
    st.markdown(f"**Gain split JEI+CIR vs sans salaire : :{color_sp}[{fmt(delta_split)}]**")

    if run_optim and optim_split:
        st.divider()
        opt_n = optim_split["optimal_net_nesrine"]
        opt_sc = optim_split["scenario"]
        st.success(f"**Nesrine optimal** : **{fmt(opt_n)}** net → Net en poche : **{fmt(opt_sc['net_en_poche'])}** "
                   f"(CIR {fmt(opt_sc['cir']['cir'])}, taux effectif {pct(opt_sc['taux_effectif'])})")

  else:
    # ---- SINGLE SALARY MODE ----
    cols = st.columns(3 if jei else 2)
    col1, col2 = cols[0], cols[1]

    s = s_no_sal
    with col1:
        render_no_salary_col(s)

    sw = s_with_sal
    with col2:
        st.subheader(f"Avec salaire ({fmt(salaire_net)} net)")

        if salaire_net == 0:
            st.info("Identique au scénario sans salaire. Augmentez le salaire pour voir la comparaison.")
        else:
            gross = sw["salaire_brut"]
            rate_low = _salariale_rate_below_pass()
            if gross <= PASS:
                brut_formula = (
                    f"Taux salarial total (≤ PASS) = {rate_low:.4%}\n\n"
                    f"Brut = Net / (1 - {rate_low:.4%})\n\n"
                    f"= {fmt(salaire_net)} / {1 - rate_low:.4f} = **{fmt(gross)}**"
                )
            else:
                rate_high = _salariale_rate_above_pass()
                net_at_pass = PASS * (1 - rate_low)
                brut_formula = (
                    f"Brut > PASS ({fmt(PASS)}), calcul en 2 tranches :\n\n"
                    f"- Tranche 1 (≤ PASS) : taux salarial = {rate_low:.4%} → net au PASS = {fmt(net_at_pass)}\n"
                    f"- Tranche 2 (> PASS) : taux marginal = {rate_high:.4%}\n\n"
                    f"Brut = PASS + (Net - {fmtn(net_at_pass)}) / (1 - {rate_high:.4%})\n\n"
                    f"= {fmt(PASS)} + {fmt(salaire_net - net_at_pass)} / {1 - rate_high:.4f} = **{fmt(gross)}**"
                )
            metric_with_detail("Salaire brut", fmt(gross), brut_formula, key="ws_brut")

            pat = sw["patronales"]
            pat_lines = [
                "| Cotisation | Assiette | Taux | Montant |",
                "|---|---|---|---|",
                f"| Maladie | Brut | {'7%' if gross <= 54055 else '13%'} | {fmt(pat['maladie'])} |",
                f"| Vieillesse plaf. | min(Brut, PASS) | 8,55% | {fmt(pat['vieillesse_plafonnee'])} |",
                f"| Vieillesse déplaf. | Brut | 2,02% | {fmt(pat['vieillesse_deplafonnee'])} |",
                f"| Alloc. familiales | Brut | {'3,45%' if gross <= 75677 else '5,25%'} | {fmt(pat['allocations_familiales'])} |",
                f"| AT/MP | Brut | 1% | {fmt(pat['atmp'])} |",
                f"| Retraite comp. T1 | min(Brut, PASS) | 4,72% | {fmt(pat['retraite_comp_t1'])} |",
                f"| Retraite comp. T2 | Brut - PASS | 12,95% | {fmt(pat['retraite_comp_t2'])} |",
                f"| CEG T1 | min(Brut, PASS) | 1,29% | {fmt(pat['ceg_t1'])} |",
                f"| CEG T2 | Brut - PASS | 1,62% | {fmt(pat['ceg_t2'])} |",
                f"| CSA | Brut | 0,3% | {fmt(pat['csa'])} |",
                f"| FNAL | min(Brut, PASS) | 0,1% | {fmt(pat['fnal'])} |",
                f"| Formation | Brut | 0,55% | {fmt(pat['formation'])} |",
                f"| Apprentissage | Brut | 0,44% | {fmt(pat['apprentissage'])} |",
                f"| **Total** | | | **{fmt(pat['total'])}** |",
            ]
            metric_with_detail("Charges patronales", fmt(pat["total"]),
                f"Assiette : Brut = {fmt(gross)}, PASS = {fmt(PASS)}\n\n" + "\n".join(pat_lines),
                key="ws_pat")

            sal = sw["salariales"]
            assiette_csg = gross * ASSIETTE_CSG_COEFF
            sal_lines = [
                "| Cotisation | Assiette | Taux | Montant |",
                "|---|---|---|---|",
                f"| Vieillesse plaf. | min(Brut, PASS) | 6,90% | {fmt(sal['vieillesse_plafonnee'])} |",
                f"| Vieillesse déplaf. | Brut | 0,40% | {fmt(sal['vieillesse_deplafonnee'])} |",
                f"| Retraite comp. T1 | min(Brut, PASS) | 3,15% | {fmt(sal['retraite_comp_t1'])} |",
                f"| Retraite comp. T2 | Brut - PASS | 8,64% | {fmt(sal['retraite_comp_t2'])} |",
                f"| CEG T1 | min(Brut, PASS) | 0,86% | {fmt(sal['ceg_t1'])} |",
                f"| CEG T2 | Brut - PASS | 1,08% | {fmt(sal['ceg_t2'])} |",
                f"| CSG déductible | 98,25% × Brut = {fmtn(assiette_csg)} | 6,80% | {fmt(sal['csg_deductible'])} |",
                f"| CSG non déductible | 98,25% × Brut | 2,40% | {fmt(sal['csg_non_deductible'])} |",
                f"| CRDS | 98,25% × Brut | 0,50% | {fmt(sal['crds'])} |",
                f"| **Total** | | | **{fmt(sal['total'])}** |",
                f"\n**Net reçu** = Brut - Total = {fmt(gross)} - {fmt(sal['total'])} = **{fmt(sal['net_received'])}**",
                f"\n**Net imposable** = Brut - cotisations - CSG déd. = **{fmt(sal['net_imposable'])}**",
            ]
            metric_with_detail("Cotisations salariales", fmt(sal["total"]),
                "\n".join(sal_lines), key="ws_sal")

            metric_with_detail("BIC résiduel", fmt(sw["bic"]),
                f"= Résultat - Coût total salaire\n\n"
                f"= {fmt(sw['resultat'])} - (Brut + Patronales)\n\n"
                f"= {fmt(sw['resultat'])} - ({fmt(gross)} + {fmt(pat['total'])})\n\n"
                f"= {fmt(sw['resultat'])} - {fmt(sw['cout_total_salaire'])} = **{fmt(sw['bic'])}**",
                key="ws_bic")

            ps_w = sw["ps"]
            metric_with_detail(f"PS {PS_TOTAL_PCT} (sur BIC)", fmt(ps_w["total"]),
                f"Assiette = BIC résiduel = {fmt(sw['bic'])}\n\n"
                f"| Contribution | Taux | Montant |\n"
                f"|---|---|---|\n"
                f"| CSG | {PS_CSG_PCT} | {fmt(ps_w['csg'])} |\n"
                f"| CRDS | {PS_CRDS_PCT} | {fmt(ps_w['crds'])} |\n"
                f"| Prélèvement de solidarité | {PS_SOL_PCT} | {fmt(ps_w['solidarite'])} |\n"
                f"| **Total** | **{PS_TOTAL_PCT}** | **{fmt(ps_w['total'])}** |",
                key="ws_ps")

            ir_w = sw["ir"]
            abat = sw.get("abattement_10", 0)
            sal_apres = sw.get("salaire_apres_abattement", 0)
            bic_imp = sw.get("bic_imposable", 0)
            ir_w_formula = (
                f"**1. Salaire imposable**\n\n"
                f"Net imposable = {fmt(sal['net_imposable'])}\n\n"
                f"Abattement 10% = min(max({fmtn(sal['net_imposable'])} × 10%, 495), 14 171) = **{fmt(abat)}**\n\n"
                f"Salaire après abattement = {fmt(sal['net_imposable'])} - {fmt(abat)} = **{fmt(sal_apres)}**\n\n"
                f"**2. BIC imposable**\n\n"
                f"= BIC - CSG déductible patrimoine (6,8%)\n\n"
                f"= {fmt(sw['bic'])} - {fmt(ps_w['csg_deductible_ir'])} = **{fmt(bic_imp)}**\n\n"
                f"**3. Revenu imposable total**\n\n"
                f"= {fmt(sal_apres)} + {fmt(bic_imp)} = **{fmt(ir_w['revenu_imposable'])}**\n\n"
                f"---\n\n" + ir_detail(ir_w)
            )
            metric_with_detail("IR", fmt(ir_w["ir"]), ir_w_formula, key="ws_ir")

            metric_with_detail("Total prélevé", fmt(sw["total_prelevements"]),
                f"= Patronales + Salariales + PS + IR\n\n"
                f"= {fmt(pat['total'])} + {fmt(sal['total'])} + {fmt(ps_w['total'])} + {fmt(ir_w['ir'])}\n\n"
                f"= **{fmt(sw['total_prelevements'])}**",
                key="ws_total")

            metric_with_detail("Net en poche", fmt(sw["net_en_poche"]),
                f"= Salaire net reçu + BIC résiduel - PS - IR\n\n"
                f"= {fmt(sal['net_received'])} + {fmt(sw['bic'])} - {fmt(ps_w['total'])} - {fmt(ir_w['ir'])}\n\n"
                f"= **{fmt(sw['net_en_poche'])}**",
                key="ws_net")

            metric_with_detail("Taux effectif global", pct(sw["taux_effectif"]),
                f"= Total prélevé / Résultat\n\n"
                f"= {fmt(sw['total_prelevements'])} / {fmt(sw['resultat'])} = **{pct(sw['taux_effectif'])}**",
                key="ws_taux")

    # ---- JEI ----
    if jei and s_jei:
        sj = s_jei
        with cols[2]:
            st.subheader(f"JEI ({fmt(salaire_net)} net)")

            if salaire_net == 0:
                st.info("Identique au scénario sans salaire. L'exonération JEI ne s'applique que sur le salaire.")
            else:
                gross_j = sj["salaire_brut"]
                pat_j = sj["patronales"]
                exo = pat_j.get("exoneration_jei", 0)

                metric_with_detail("Salaire brut", fmt(gross_j),
                    f"Identique au scénario avec salaire = **{fmt(gross_j)}**",
                    key="jei_brut")

                metric_with_detail("Charges patronales", fmt(pat_j["total"]),
                    f"**Exonération JEI** : maladie, vieillesse, AF = **-{fmt(exo)}**\n\n"
                    f"| Cotisation | Montant |\n"
                    f"|---|---|\n"
                    f"| Maladie | {fmt(pat_j['maladie'])} |\n"
                    f"| Vieillesse plaf. | {fmt(pat_j['vieillesse_plafonnee'])} |\n"
                    f"| Vieillesse déplaf. | {fmt(pat_j['vieillesse_deplafonnee'])} |\n"
                    f"| Alloc. familiales | {fmt(pat_j['allocations_familiales'])} |\n"
                    f"| AT/MP | {fmt(pat_j['atmp'])} |\n"
                    f"| Retraite comp. T1 | {fmt(pat_j['retraite_comp_t1'])} |\n"
                    f"| Retraite comp. T2 | {fmt(pat_j['retraite_comp_t2'])} |\n"
                    f"| CEG T1 | {fmt(pat_j['ceg_t1'])} |\n"
                    f"| CEG T2 | {fmt(pat_j['ceg_t2'])} |\n"
                    f"| CSA | {fmt(pat_j['csa'])} |\n"
                    f"| FNAL | {fmt(pat_j['fnal'])} |\n"
                    f"| Formation | {fmt(pat_j['formation'])} |\n"
                    f"| Apprentissage | {fmt(pat_j['apprentissage'])} |\n"
                    f"| **Total** | **{fmt(pat_j['total'])}** |",
                    key="jei_pat")

                sal_j = sj["salariales"]
                metric_with_detail("Cotisations salariales", fmt(sal_j["total"]),
                    f"Identiques (JEI n'affecte pas les salariales) = **{fmt(sal_j['total'])}**",
                    key="jei_sal")

                metric_with_detail("BIC résiduel", fmt(sj["bic"]),
                    f"= {fmt(sj['resultat'])} - ({fmt(gross_j)} + {fmt(pat_j['total'])}) = **{fmt(sj['bic'])}**",
                    key="jei_bic")

                ps_j = sj["ps"]
                metric_with_detail(f"PS {PS_TOTAL_PCT} (sur BIC)", fmt(ps_j["total"]),
                    f"= {fmt(sj['bic'])} × {PS_TOTAL_PCT} = **{fmt(ps_j['total'])}**",
                    key="jei_ps")

                ir_j = sj["ir"]
                metric_with_detail("IR", fmt(ir_j["ir"]), ir_detail(ir_j), key="jei_ir")

                metric_with_detail("Total prélevé", fmt(sj["total_prelevements"]),
                    f"= {fmt(pat_j['total'])} + {fmt(sal_j['total'])} + {fmt(ps_j['total'])} + {fmt(ir_j['ir'])} = **{fmt(sj['total_prelevements'])}**",
                    key="jei_total")

                metric_with_detail("Net en poche", fmt(sj["net_en_poche"]),
                    f"= {fmt(sal_j['net_received'])} + {fmt(sj['bic'])} - {fmt(ps_j['total'])} - {fmt(ir_j['ir'])} = **{fmt(sj['net_en_poche'])}**",
                    key="jei_net")

                metric_with_detail("Taux effectif global", pct(sj["taux_effectif"]),
                    f"= {fmt(sj['total_prelevements'])} / {fmt(sj['resultat'])} = **{pct(sj['taux_effectif'])}**",
                    key="jei_taux")

    # Delta
    if salaire_net > 0:
        delta = sw["net_en_poche"] - s["net_en_poche"]
        color = "green" if delta > 0 else "red"
        st.markdown(f"**Différence net en poche (salaire vs sans) : :{color}[{fmt(delta)}]**")
    if jei and s_jei and salaire_net > 0:
        delta_jei = s_jei["net_en_poche"] - s["net_en_poche"]
        color_j = "green" if delta_jei > 0 else "red"
        st.markdown(f"**Différence net en poche (JEI vs sans) : :{color_j}[{fmt(delta_jei)}]**")

    if run_optim and optim:
        st.divider()
        opt_sal = optim["optimal_net_salary"]
        opt_net = optim["scenario"]["net_en_poche"]
        st.success(f"**Standard** — Salaire optimal : **{fmt(opt_sal)}** net → Net en poche : **{fmt(opt_net)}** "
                   f"(taux effectif {pct(optim['scenario']['taux_effectif'])})")
        if jei and optim_jei:
            opt_sal_j = optim_jei["optimal_net_salary"]
            opt_net_j = optim_jei["scenario"]["net_en_poche"]
            st.success(f"**JEI** — Salaire optimal : **{fmt(opt_sal_j)}** net → Net en poche : **{fmt(opt_net_j)}** "
                       f"(taux effectif {pct(optim_jei['scenario']['taux_effectif'])})")

# --- Tab 2: Sankey ---
with tab_sankey:
    st.subheader("Sans salaire")
    st.plotly_chart(build_sankey_no_salary(s_no_sal), use_container_width=True)

    if split_mode and s_split and (net_amine > 0 or net_nesrine > 0):
        st.subheader("Split JEI + CIR")
        st.info("Sankey non disponible en mode split — voir l'onglet Comparaison pour le détail.")
    elif not split_mode:
        if salaire_net > 0 and s_with_sal:
            st.subheader(f"Avec salaire ({fmt(salaire_net)} net)")
            st.plotly_chart(build_sankey_with_salary(s_with_sal), use_container_width=True)

            if jei and s_jei:
                st.subheader(f"Avec salaire + JEI ({fmt(salaire_net)} net)")
                st.plotly_chart(build_sankey_with_salary(s_jei), use_container_width=True)

# --- Tab 3: Optimization curve ---
with tab_optim:
  if split_mode:
    st.subheader("Net en poche selon le salaire de Nesrine")
    st.caption(f"Amine fixé à {fmt(net_amine)} net, autres charges = {fmt(autres_charges)}")

    with st.spinner("Calcul de la courbe..."):
        pts = compute_curve_split(resultat, net_amine, autres_charges)

    x_sp = [p["salaire_nesrine"] for p in pts]
    y_sp = [p["net_en_poche"] for p in pts]
    y_cir = [p["cir"] for p in pts]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_sp, y=y_sp, name="Net en poche (split JEI+CIR)",
                             line=dict(color="#8e44ad", width=3)))
    fig.add_trace(go.Scatter(x=x_sp, y=y_cir, name="CIR",
                             line=dict(color="#2980b9", width=2, dash="dot")))

    fig.add_hline(y=s_no_sal["net_en_poche"], line_dash="dash", line_color="gray",
                  annotation_text=f"Sans salaire: {fmt(s_no_sal['net_en_poche'])}")

    if net_nesrine > 0:
        fig.add_vline(x=net_nesrine, line_dash="dash", line_color="#3498db",
                      annotation_text=f"Nesrine actuel: {fmt(net_nesrine)}")

    if run_optim and optim_split:
        fig.add_vline(x=optim_split["optimal_net_nesrine"], line_dash="dash", line_color="#8e44ad",
                      annotation_text=f"Optimal: {fmt(optim_split['optimal_net_nesrine'])}")

    fig.update_layout(
        xaxis_title="Salaire net Nesrine (€)",
        yaxis_title="Montant (€)",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

  else:
    st.subheader("Net en poche selon le salaire")

    with st.spinner("Calcul de la courbe..."):
        points = compute_curve(resultat)

    x = [p["salaire_net"] for p in points]
    y_net = [p["net_en_poche"] for p in points]
    y_ir = [p["ir"] for p in points]
    y_cotis = [p["cotisations_sociales"] for p in points]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y_net, name="Net en poche", line=dict(color="#27ae60", width=3)))
    if jei:
        y_jei = [p["net_en_poche_jei"] for p in points]
        fig.add_trace(go.Scatter(x=x, y=y_jei, name="Net en poche (JEI)",
                                 line=dict(color="#8e44ad", width=3)))
    fig.add_trace(go.Scatter(x=x, y=y_ir, name="IR", line=dict(color="#e67e22", width=2, dash="dot")))
    fig.add_trace(go.Scatter(x=x, y=y_cotis, name="Cotisations sociales", line=dict(color="#e74c3c", width=2, dash="dot")))

    fig.add_hline(y=s_no_sal["net_en_poche"], line_dash="dash", line_color="gray",
                  annotation_text=f"Sans salaire: {fmt(s_no_sal['net_en_poche'])}")

    if salaire_net > 0:
        fig.add_vline(x=salaire_net, line_dash="dash", line_color="#3498db",
                      annotation_text=f"Salaire choisi: {fmt(salaire_net)}")

    if run_optim and optim:
        fig.add_vline(x=optim["optimal_net_salary"], line_dash="dash", line_color="#27ae60",
                      annotation_text=f"Optimal: {fmt(optim['optimal_net_salary'])}")
        if jei and optim_jei:
            fig.add_vline(x=optim_jei["optimal_net_salary"], line_dash="dash", line_color="#8e44ad",
                          annotation_text=f"Optimal JEI: {fmt(optim_jei['optimal_net_salary'])}")

    fig.update_layout(
        xaxis_title="Salaire net annuel (€)",
        yaxis_title="Montant (€)",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Tab 4: Documentation JEI & CIR ---
with tab_doc:
    st.header("JEI — Jeune Entreprise Innovante")

    st.subheader("Qu'est-ce que c'est ?")
    st.markdown("""
Le statut **JEI** (art. 44 sexies-0 A du CGI) est un dispositif fiscal et social
destiné aux jeunes PME qui investissent significativement en R&D. Il offre des
**exonérations de cotisations patronales** sur les salaires du personnel affecté à la recherche,
ainsi que des avantages fiscaux (exonération d'IS/IR les premières années, exonération de CFE/CVAE).

**Pour Beluga Paris (SAS à l'IR)**, l'intérêt principal est l'exonération de cotisations patronales
sur le salaire de Nesrine (100% R&D), qui réduit le coût employeur et augmente le BIC résiduel.
""")

    st.subheader("Conditions d'éligibilité")
    st.markdown(f"""
| Critère | Seuil | Beluga Paris |
|---------|-------|--------------|
| **Âge** | < 8 ans (date d'immatriculation) | A vérifier (SIREN 910 938 026) |
| **Taille** | < 250 salariés | ✅ |
| **CA ou bilan** | CA < 50 M€ ou bilan < 43 M€ | ✅ |
| **Indépendance** | Pas détenue à ≥ 25% par une grande entreprise | ✅ |
| **Dépenses R&D** | ≥ **{JEI_RD_THRESHOLD:.0%}** des charges fiscalement déductibles (depuis 2025) | Dépend du split salarial |
| **Activité nouvelle** | Ne pas être issue d'une restructuration/extension | ✅ |

**Point critique : le seuil de {JEI_RD_THRESHOLD:.0%}** — Les dépenses de R&D (salaire brut + charges patronales
de Nesrine) doivent représenter au moins {JEI_RD_THRESHOLD:.0%} des charges fiscalement déductibles totales
(salaires + charges + loyer + services + amortissements…). L'onglet *Comparaison* calcule ce ratio en temps réel.
""")

    st.subheader("Exonérations sociales JEI")
    st.markdown("""
L'exonération porte sur les **cotisations patronales** suivantes, pour le personnel affecté à la R&D
(≥ 50% de son temps) :

| Cotisation | Exonérée ? | Détail |
|------------|-----------|--------|
| Maladie (7% ou 13%) | ✅ Oui | Totalement exonérée |
| Vieillesse plafonnée (8,55%) | ✅ Oui | Totalement exonérée |
| Vieillesse déplafonnée (2,02%) | ✅ Oui | Totalement exonérée |
| Allocations familiales (3,45% ou 5,25%) | ✅ Oui | Totalement exonérée |
| AT/MP (1%) | ❌ Non | Reste due |
| Retraite complémentaire T1 (4,72%) | ❌ Non | Reste due |
| Retraite complémentaire T2 (12,95%) | ❌ Non | Reste due |
| CEG T1 (1,29%) / T2 (1,62%) | ❌ Non | Reste due |
| Chômage (4,05%) | ❌ Non | Reste due (salariée uniquement) |
| AGS (0,20%) | ❌ Non | Reste due |
| CSA (0,3%), FNAL (0,1%) | ❌ Non | Restent dues |
| Formation (0,55%), Apprentissage (0,44%) | ❌ Non | Restent dues |

**Plafonds** :
- Rémunération max par salarié : **4,5 × SMIC annuel** (~97 300 €/an)
- Exonération max par établissement : **5 × PASS** (235 500 €/an)
""")

    st.subheader("Comment obtenir le statut JEI ?")
    st.markdown(f"""
**Le JEI est un régime déclaratif** — il n'y a pas de dossier d'agrément préalable.

1. **Auto-qualification** : l'entreprise vérifie elle-même qu'elle remplit les conditions et
   applique les exonérations sur ses DSN (déclarations sociales)
2. **Rescrit fiscal (recommandé)** : demander à l'administration une prise de position formelle
   (art. L 80 B 1° du LPF) confirmant l'éligibilité — garantie contre un redressement ultérieur
3. **Rescrit social** : demander à l'URSSAF une prise de position sur l'exonération de cotisations

**Difficulté** : Le statut en lui-même est simple à obtenir si les conditions sont remplies.
La vraie difficulté est de **justifier la nature R&D** de l'activité (voir section CIR ci-dessous).
Pour de la programmation/consulting IT, il faut démontrer un **verrou technologique** :
un problème dont la solution n'est pas évidente pour un professionnel du domaine.

**Renouvellement** : pas de renouvellement formel — le statut s'applique tant que les conditions sont remplies,
dans la limite de 8 ans. Si le ratio R&D tombe sous {JEI_RD_THRESHOLD:.0%}, le statut est perdu pour l'exercice.
""")

    st.divider()
    st.header("CIR — Crédit d'Impôt Recherche")

    st.subheader("Qu'est-ce que c'est ?")
    st.markdown(f"""
Le **CIR** (art. 244 quater B du CGI) est un crédit d'impôt de **{CIR_RATE:.0%}** des dépenses de R&D éligibles
(jusqu'à 100 M€, 5% au-delà). C'est le dispositif le plus puissant de soutien à la R&D en France.

**Pour Beluga Paris (SAS à l'IR)** : le CIR est imputé sur l'IR des associés
proportionnellement à leurs parts (art. 199 ter B du CGI). Si le CIR dépasse l'IR,
**le reliquat est remboursable immédiatement** pour les PME (art. 199 ter B, I bis).
""")

    st.subheader("Calcul du CIR — dépenses de personnel")
    st.markdown(f"""
Pour le personnel R&D (Nesrine), le CIR se calcule ainsi :

```
Base personnel     = Salaire brut + Charges patronales CIR-éligibles
Forfait fonct.     = Base personnel × {CIR_FORFAIT_FONCTIONNEMENT:.0%}  (depuis fév. 2025, était 43%)
Total éligible     = Base personnel + Forfait fonctionnement
CIR                = Total éligible × {CIR_RATE:.0%}
```

**Charges patronales CIR-éligibles** (celles effectivement payées, après JEI) :

| Cotisation | CIR-éligible ? |
|------------|---------------|
| AT/MP | ✅ Oui |
| Retraite complémentaire T1/T2 | ✅ Oui |
| CEG T1/T2 | ✅ Oui |
| Chômage | ✅ Oui |
| AGS | ✅ Oui |
| Maladie, Vieillesse, AF | ❌ Non (exonérées JEI → pas payées → pas dans le CIR) |
| CSA, FNAL, Formation, Apprentissage | ❌ Non (hors périmètre CIR) |

**L'exonération JEI réduit la base CIR** : les charges exonérées ne sont pas payées,
donc pas déductibles. C'est un compromis, mais le gain net reste très favorable.
""")

    st.subheader("Autres dépenses CIR éligibles")
    st.markdown("""
Au-delà du personnel, d'autres dépenses peuvent entrer dans l'assiette du CIR :

| Type de dépense | Conditions |
|----------------|------------|
| **Amortissement matériel R&D** | Matériel dédié à la R&D (serveurs, licences logicielles…) |
| **Sous-traitance** | Organismes agréés CIR, plafonnée à 3× le montant des dépenses internes |
| **Brevets et COV** | Dépôt, maintenance et défense de brevets |
| **Veille technologique** | Plafonnée à 60 000 €/an |
| **Dotations aux amortissements** | Brevets acquis pour la R&D |

**Pour maximiser le CIR de Beluga Paris** :
- Investir dans du **matériel dédié R&D** (GPU, serveurs cloud pour entraîner des modèles…)
- Utiliser des **prestataires agréés CIR** pour la sous-traitance R&D
- Documenter la **veille technologique** (abonnements, conférences, publications)
""")

    st.subheader("Comment obtenir le CIR ?")
    st.markdown("""
**Le CIR est aussi déclaratif** — pas d'agrément préalable pour les dépenses internes.

**Déclarations à produire** :
1. **Formulaire 2069-A** : déclaration annuelle des dépenses de R&D (joint à la liasse fiscale)
2. **Dossier technique justificatif** : description des projets R&D, indicateurs de verrou technologique

**Sécurisation (fortement recommandé)** :
- **Rescrit CIR** (art. L 80 B 3° du LPF) : demande préalable à la DRFIP ou au MESRI pour valider
  l'éligibilité de vos travaux. Réponse sous 3 mois ; silence = acceptation.
- **Agrément sous-traitance** : si vous sous-traitez, le prestataire doit être agréé CIR.

**Difficulté** :
- **Faible si les projets sont vraiment de la R&D** : algorithmes nouveaux, IA, machine learning,
  résolution de problèmes techniques non triviaux
- **Risque de contrôle** : le MESRI (Ministère de la Recherche) peut auditer le dossier technique.
  En cas de redressement, le CIR est repris avec intérêts de retard.
- **Clé : documenter en continu** — ne pas attendre la fin de l'année pour constituer le dossier
""")

    st.subheader("Remboursement du CIR pour SAS à l'IR")
    st.markdown("""
**Cas de Beluga Paris** : SAS ayant opté pour l'IR (art. 239 bis AB du CGI).

1. Le CIR est calculé au niveau de la société (formulaire 2069-A)
2. Il est **imputé sur l'IR de chaque associé** au prorata de ses droits (50% chacun) —
   art. 199 ter B du CGI
3. Si le CIR > IR : **remboursement immédiat du reliquat** pour les PME communautaires
   (< 250 salariés, CA < 50 M€) — art. 199 ter B, I bis du CGI

Concrètement :
- Amine déclare 50% du CIR sur sa déclaration 2042 C PRO (case 8TK ou équivalent)
- Nesrine déclare 50% du CIR
- L'administration impute d'abord sur l'IR, puis rembourse l'excédent

**C'est un avantage majeur** : même si le CIR dépasse l'IR, la trésorerie est récupérée.
""")

    st.divider()
    st.header("Stratégie d'optimisation — Beluga Paris")

    st.subheader("Combo JEI + CIR : double avantage")
    st.markdown(f"""
L'articulation JEI + CIR est le levier principal d'optimisation :

| Mécanisme | Effet |
|-----------|-------|
| **JEI** | Réduit les patronales de ~60% → BIC résiduel plus élevé |
| **CIR** | Crédit d'impôt de {CIR_RATE:.0%} sur les dépenses R&D restantes → réduit l'IR (voire remboursement) |
| **Combo** | Le JEI réduit la base CIR, mais le gain en patronales économisées est supérieur à la perte de CIR |

**Attention** : le JEI exonère des charges qui ne sont PAS dans la base CIR de toute façon
(maladie, vieillesse, AF). Les charges CIR-éligibles (RC, CEG, chômage, AGS, AT/MP) restent dues.
→ Le combo est **quasi sans perte** sur le CIR.
""")

    st.subheader("Points de vigilance")
    st.markdown(f"""
1. **Seuil R&D {JEI_RD_THRESHOLD:.0%}** : si Amine prend un salaire élevé et Nesrine un salaire faible,
   le ratio R&D/charges totales peut tomber sous {JEI_RD_THRESHOLD:.0%} → perte du JEI.
   Utilisez l'onglet *Comparaison* pour vérifier en temps réel.

2. **Justification R&D** : la programmation/consulting IT classique n'est PAS de la R&D.
   Il faut un **verrou technologique** documenté :
   - Développement d'algorithmes nouveaux (pas juste de l'intégration)
   - IA/ML avec contribution originale (architecture, données, méthode)
   - Résolution de problèmes techniques dont la solution n'est pas connue de l'état de l'art

3. **Documentation continue** : tenir un **cahier de laboratoire** ou équivalent :
   - Description du verrou scientifique/technique
   - État de l'art et bibliographie
   - Hypothèses testées, échecs, résultats
   - Indicateurs de nouveauté (publications, brevets)

4. **Temps R&D de Nesrine** : pour l'exonération JEI, Nesrine doit consacrer
   **≥ 50% de son temps** à la R&D. Tenir un relevé de temps.

5. **Rescrit préventif** : demander un rescrit CIR (L 80 B 3°) **avant** de déclarer,
   pour sécuriser la position. Le rescrit JEI peut être demandé en parallèle.

6. **Contrôle MESRI** : en cas de contrôle, le Ministère de la Recherche envoie un expert.
   Avoir un dossier technique solide est la meilleure protection.
""")

    st.subheader("Levier supplémentaire : IP Box (à explorer)")
    st.markdown("""
Si Beluga Paris développe un **logiciel original ou un brevet**, le régime de l'IP Box
(art. 238 du CGI) permet une imposition à **10% au lieu du barème** sur les revenus
de cession ou concession de propriété intellectuelle.

Conditions :
- Actif de PI qualifiant (brevet, logiciel original protégé par le droit d'auteur)
- Ratio nexus : les dépenses R&D internes doivent être prépondérantes
- Applicable sur les revenus de licence/cession, pas sur les prestations de service

**Non intégré dans la simulation** — à étudier si Beluga Paris produit un logiciel
commercialisable ou sous licence.
""")

# --- Tab 5: Plan d'action ---
with tab_plan:
    st.header("Plan d'action — JEI & CIR LegalTech AI")
    st.caption("Beluga Paris — Assistant AI juridique (RAG + Adversarial)")

    # -----------------------------------------------------------------------
    # Timeline overview
    # -----------------------------------------------------------------------
    st.markdown("""
> **Objectif** : obtenir les statuts JEI et CIR pour l'exercice clos le 30 sept. 2027,
> en lançant un produit LegalTech AI crédible avec un premier gros client (éditeur juridique).
""")

    st.subheader("Vue d'ensemble")

    timeline_data = {
        "Phase": [
            "M0 — Fondations R&D",
            "M1 — Dossier JEI + CIR",
            "M2 — Prototype RAG",
            "M3 — Module adversarial",
            "M4 — Rescrit + BPI",
            "M5 — Démo publique",
            "M6 — POC éditeur",
            "M7-M9 — Pilote",
            "M10-M12 — Contrat + SaaS",
            "M12+ — Scaling",
        ],
        "Période": [
            "Avril 2026",
            "Mai 2026",
            "Juin 2026",
            "Juil. 2026",
            "Août 2026",
            "Sept. 2026",
            "Oct.-Nov. 2026",
            "Déc. 2026 — Fév. 2027",
            "Mars — Mai 2027",
            "Juin 2027+",
        ],
        "Effort Nesrine": [
            "100%", "50%", "100%", "100%", "30%", "80%", "100%", "100%", "80%", "60%",
        ],
        "Effort Amine": [
            "20%", "50%", "20%", "30%", "70%", "50%", "50%", "30%", "50%", "40%",
        ],
        "Livrable clé": [
            "Cahier de labo, archi, repo GitHub",
            "Dossiers rescrit JEI + CIR déposés",
            "RAG juridique fonctionnel (Légifrance)",
            "Simulation adversariale avocat vs fisc",
            "Rescrits envoyés + dossier BPI",
            "Demo live + articles LinkedIn",
            "POC intégré chez Lefebvre Dalloz",
            "Beta testée par ~50 utilisateurs",
            "Licence signée + SaaS lancé",
            "Nouveaux clients + extension domaines",
        ],
    }
    st.dataframe(timeline_data, use_container_width=True, hide_index=True)

    # -----------------------------------------------------------------------
    # M0 — Fondations
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("M0 — Fondations R&D (Avril 2026)")
    st.markdown("**Objectif** : poser les bases techniques et documentaires pour qualifier en JEI/CIR.")

    st.markdown("""
##### Semaine 1 : Architecture & état de l'art
| Tâche | Qui | Effort | Livrable |
|-------|-----|--------|----------|
| Rédiger l'**état de l'art** RAG juridique (papers, produits existants, limites) | Nesrine | 3j | Document 5-10 pages |
| Identifier les **verrous technologiques** (hiérarchie des normes, hallucinations, adversarial) | Nesrine | 2j | Section dans cahier de labo |
| Définir l'**architecture technique** (stack, modèles, infra) | Amine + Nesrine | 2j | Schéma archi + ADR |
| Créer le **repo GitHub** (open core : moteur RAG + adversarial en Apache 2.0) | Amine | 0.5j | Repo public avec README |
| Initialiser le **cahier de laboratoire** (Notion, Git, ou papier daté) | Nesrine | 0.5j | Template + 1ère entrée |

##### Semaine 2 : Infrastructure & données
| Tâche | Qui | Effort | Livrable |
|-------|-----|--------|----------|
| Pipeline d'ingestion **Légifrance** (API PISTE : lois, décrets, BOI, jurisprudence) | Nesrine | 3j | Script ETL fonctionnel |
| Choix et setup du **vector store** (Qdrant, Weaviate, ou pgvector) | Nesrine | 1j | Instance déployée |
| Stratégie de **chunking juridique** (par article, par alinéa, hiérarchie) | Nesrine | 2j | Doc technique + benchmark |
| Setup **CI/CD** (tests, linting, déploiement auto) | Amine | 1j | GitHub Actions |
| **Enveloppe Soleau** numérique (INPI) pour antériorité des algorithmes | Amine | 0.5j | Récépissé INPI |

##### Semaine 3-4 : Premier prototype RAG
| Tâche | Qui | Effort | Livrable |
|-------|-----|--------|----------|
| Implémentation **retrieval de base** (embedding + recherche sémantique) | Nesrine | 5j | Module fonctionnel |
| **Évaluation quantitative** (recall@k, precision sur 50 questions juridiques) | Nesrine | 3j | Benchmark documenté |
| Comparer **3 stratégies de chunking** (résultats dans cahier de labo) | Nesrine | 2j | Tableau comparatif |
| Rédiger les **hypothèses R&D** testées et résultats (cahier de labo) | Nesrine | continu | Entrées datées |

**Livrables M0 pour le dossier CIR** :
- Cahier de laboratoire avec état de l'art, verrous, hypothèses, résultats
- Repo GitHub avec commits datés (preuve d'antériorité)
- Enveloppe Soleau déposée
- Relevé de temps Nesrine (100% R&D)
""")

    # -----------------------------------------------------------------------
    # M1 — Dossier JEI + CIR
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("M1 — Dossier JEI + CIR (Mai 2026)")
    st.markdown("**Objectif** : rédiger et déposer les demandes de rescrit JEI et CIR.")

    st.markdown("""
##### Semaine 1-2 : Rédaction des dossiers
| Tâche | Qui | Effort | Livrable |
|-------|-----|--------|----------|
| **Rescrit JEI** (art. L 80 B 1° LPF) : rédiger la demande | Amine | 3j | Lettre + pièces jointes |
| — Prouver < 8 ans, PME, indépendance, R&D ≥ 20% | Amine | inclus | Annexes chiffrées |
| — Décrire l'activité R&D (verrous technologiques) | Nesrine | 2j | Annexe technique |
| **Rescrit CIR** (art. L 80 B 3° LPF) : rédiger la demande | Amine | 3j | Lettre + dossier technique |
| — Description des **projets R&D** (RAG juridique, adversarial) | Nesrine | 3j | Fiche projet format MESRI |
| — **Indicateurs de verrou** : état de l'art, incertitudes, démarche expérimentale | Nesrine | 2j | Section dédiée |
| Faire relire par un **consultant CIR** (optionnel mais recommandé, ~1-2k€) | Amine | 1j | Dossier validé |

##### Semaine 3 : Envoi
| Tâche | Qui | Effort | Livrable |
|-------|-----|--------|----------|
| Envoyer rescrit JEI à la **DRFIP IDF** (LRAR) | Amine | 0.5j | AR postal |
| Envoyer rescrit CIR à la **DRFIP IDF** ou au **MESRI** | Amine | 0.5j | AR postal |
| Envoyer rescrit social JEI à l'**URSSAF IDF** | Amine | 0.5j | AR postal |
| Calendrier : réponse sous **3 mois** (silence = acceptation) | — | — | Relance à M+2.5 si silence |

##### Semaine 3-4 : Nesrine continue la R&D
| Tâche | Qui | Effort | Livrable |
|-------|-----|--------|----------|
| Implémentation **re-ranking juridique** (cross-encoder fine-tuné) | Nesrine | 5j | Module + benchmark |
| Gestion de la **hiérarchie des normes** (loi > décret > circulaire > BOI) | Nesrine | 3j | Algorithme documenté |
| Gestion des **versions temporelles** (texte en vigueur à date X) | Nesrine | 2j | Module versionning |

**Destinataires des rescrits** :

| Rescrit | Destinataire | Adresse | Délai |
|---------|-------------|---------|-------|
| JEI fiscal | DRFIP IDF, Pôle Contrôle et Expertise Paris 1er-2e | 16, rue Notre-Dame des Victoires, 75081 Paris Cedex 02 | 3 mois |
| CIR | DRFIP IDF (même adresse) ou MESRI (1 rue Descartes, 75231 Paris Cedex 05) | Au choix | 3 mois |
| JEI social | URSSAF IDF | TSA 93104, 93104 Montreuil Cedex | 3 mois |

*Astuce : envoyer au MESRI pour le CIR si le projet est très technique — ils ont des experts scientifiques.*
""")

    # -----------------------------------------------------------------------
    # M2 — Prototype RAG
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("M2 — Prototype RAG juridique (Juin 2026)")
    st.markdown("**Objectif** : RAG fonctionnel sur le corpus fiscal français, benchmarké.")

    st.markdown("""
| Tâche | Qui | Effort | Livrable |
|-------|-----|--------|----------|
| **Corpus complet** : ingestion Légifrance (CGI, LPF, CSS, BOI-IF, BOI-IR, BOI-BIC) | Nesrine | 5j | ~500k documents indexés |
| **Jurisprudence** : CE, CC, CAA via API Judilibre | Nesrine | 3j | ~100k décisions indexées |
| **Hybrid search** : sémantique + BM25 + filtres (date, source, hiérarchie) | Nesrine | 5j | Module + éval |
| **Détection d'hallucinations** : vérification des citations (article, jurisprudence) | Nesrine | 5j | Module + métriques |
| **Benchmark v2** : 100 questions juridiques, comparaison avec ChatGPT/Perplexity | Nesrine | 3j | Rapport chiffré |
| **API REST** : endpoint de recherche juridique | Amine | 2j | FastAPI documentée |
| Cahier de labo : résultats, échecs, pivots | Nesrine | continu | Entrées datées |

**Verrou technologique clé** : la détection d'hallucinations juridiques. Un avocat qui cite un article
inexistant commet une faute professionnelle. Ce problème n'est pas résolu par l'état de l'art
(réf. : [Magesh et al. 2024, "Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools"]).
""")

    # -----------------------------------------------------------------------
    # M3 — Module adversarial
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("M3 — Module adversarial (Juillet 2026)")
    st.markdown("**Objectif** : simulation contradictoire avocat vs administration fiscale.")

    st.markdown("""
| Tâche | Qui | Effort | Livrable |
|-------|-----|--------|----------|
| **Architecture adversariale** : 2 agents LLM (contribuable vs fisc) avec RAG partagé | Nesrine | 5j | Design doc + proto |
| **Prompt engineering** : personas juridiques (avocat fiscaliste, inspecteur des impôts) | Nesrine | 3j | Prompt library |
| **Chaîne d'argumentation** : chaque argument sourcé (article + jurisprudence) | Nesrine | 5j | Module de génération |
| **Scoring d'arguments** : probabilité de succès basée sur jurisprudence similaire | Nesrine | 5j | Modèle de scoring |
| **Cas test** : reproduire le rescrit Beluga Paris (PS 7,5%) en mode adversarial | Amine + Nesrine | 3j | Démo fonctionnelle |
| **UI Streamlit** : interface de simulation interactive | Amine | 3j | App déployée |
| Cahier de labo : design decisions, benchmarks | Nesrine | continu | Entrées datées |
""")

    # -----------------------------------------------------------------------
    # M4 — Rescrit + BPI
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("M4 — Rescrits + BPI (Août 2026)")
    st.markdown("**Objectif** : sécuriser JEI/CIR + lancer une demande de financement BPI.")

    st.markdown("""
| Tâche | Qui | Effort | Livrable |
|-------|-----|--------|----------|
| **Suivi rescrits** : relancer DRFIP/MESRI/URSSAF si pas de réponse (silence M+3 = acceptation) | Amine | 1j | Courrier de relance |
| **DSN** : première paie de Nesrine avec exonération JEI (si rescrit positif ou silence) | Amine | 2j | DSN déposée |
| **Bourse French Tech** BPI : dossier de candidature (30k€ subvention) | Amine | 5j | Dossier déposé |
| — Business plan, budget prévisionnel, pitch deck | Amine | inclus | Documents |
| — Description R&D (réutiliser dossier CIR) | Nesrine | 1j | Annexe |
| **Aide à l'innovation BPI** : pré-dossier (subvention jusqu'à 50% des dépenses R&D) | Amine | 3j | Pré-dossier |
| Nesrine continue R&D : **fine-tuning** modèle sur jurisprudence fiscale | Nesrine | 15j | Modèle v1 |

**Calendrier financement BPI** :

| Dispositif | Montant | Délai réponse | Conditions |
|-----------|---------|---------------|------------|
| Bourse French Tech | 30 000 € (subvention) | 2-3 mois | < 1 an, innovant, pas de CA |
| Aide à l'innovation | 50-500k€ (50% subvention) | 3-4 mois | Projet R&D, PME |
| Prêt d'honneur | 10-50k€ (taux 0) | 1-2 mois | Via réseau Initiative/Réseau Entreprendre |
| Concours i-Nov | 500k-2M€ | 6 mois | Deeptech, très sélectif |
""")

    # -----------------------------------------------------------------------
    # M5 — Démo publique
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("M5 — Démo publique (Septembre 2026)")
    st.markdown("**Objectif** : visibilité pour attirer le gros client.")

    st.markdown("""
| Tâche | Qui | Effort | Livrable |
|-------|-----|--------|----------|
| **Landing page** : site web avec démo interactive limitée | Amine | 3j | Site en ligne |
| **Article LinkedIn #1** : "Comment l'IA a rédigé notre rescrit fiscal" (cas Beluga Paris anonymisé) | Amine | 2j | Publication |
| **Article LinkedIn #2** : "RAG juridique : pourquoi ChatGPT hallucine sur le droit fiscal" | Nesrine | 2j | Publication |
| **Démo live** sur le cas du PS 7,5% (adversarial : contribuable vs DGFIP) | Amine + Nesrine | 3j | Vidéo + lien démo |
| **Contact Lefebvre Dalloz** : identifier le directeur innovation, envoyer la démo | Amine | 2j | Email + relance |
| **Contact LexisNexis** : même approche (plan B) | Amine | 1j | Email + relance |
| **Meetup/conférence LegalTech** : présenter à Paris Legal Hackers ou Legal Geek | Amine | 2j | Talk de 15 min |
""")

    # -----------------------------------------------------------------------
    # M6-M12 — High level
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("M6 → M12+ — Phases suivantes (haute altitude)")

    st.markdown("""
#### M6 — POC éditeur (Oct.-Nov. 2026)
- Signer un **accord de POC** avec Lefebvre Dalloz (ou LexisNexis)
- Intégration du moteur RAG dans un environnement de test éditeur
- Accès au corpus propriétaire (Navis Fiscal, Mémento)
- KPI définis : precision, recall, satisfaction utilisateur, gain de temps
- **Effort** : Nesrine 100% (intégration technique), Amine 50% (relation commerciale)

#### M7-M9 — Pilote (Déc. 2026 — Fév. 2027)
- Beta ouverte à **~50 utilisateurs** (avocats fiscalistes, experts-comptables)
- Itérations sur les retours utilisateurs (UX, pertinence, edge cases)
- Mesure quantitative : temps de recherche avant/après, taux d'adoption
- **Formulaire 2069-A** : préparer la déclaration CIR pour l'exercice (clôture 30 sept. 2027)
- **Effort** : Nesrine 100% R&D, Amine 30% (suivi + consulting parallèle)

#### M10-M12 — Contrat + SaaS (Mars — Mai 2027)
- Convertir le POC en **licence annuelle** (objectif : 200-500k€/an)
- Lancer le **SaaS en accès direct** (avocats individuels, 99-199€/mois)
- Marketing : études de cas, témoignages, SEO juridique
- **Effort** : Amine bascule 50% sur le commercial, Nesrine 80% R&D + 20% support

#### M12+ — Scaling (Juin 2027+)
- Extension à d'autres domaines : droit social, droit des sociétés, RGPD, droit pénal
- Recrutement : 1 dev + 1 juriste annotateur
- Nouveaux clients directs (cabinets, directions juridiques)
- Candidature **concours i-Nov** (500k-2M€) pour accélérer
- Objectif fin 2027 : **ARR 300-500k€**, 5-10 clients, JEI + CIR actifs
""")

    # -----------------------------------------------------------------------
    # Budget prévisionnel
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("Budget prévisionnel — 12 premiers mois")

    budget = {
        "Poste": [
            "Salaire Nesrine (net 25k€/an, 100% R&D)",
            "Charges patronales Nesrine (JEI)",
            "Infra cloud (GPU, vector DB, hosting)",
            "API LLM (OpenAI / Anthropic)",
            "Consultant CIR (relecture dossier)",
            "Enveloppe Soleau + frais INPI",
            "Frais BPI (dossier, déplacements)",
            "Divers (domaine, outils, conférences)",
            "**Total dépenses**",
            "",
            "CIR (30% dépenses R&D éligibles)",
            "Bourse French Tech (si obtenue)",
            "**Total aides**",
            "",
            "**Coût net après aides**",
        ],
        "Montant annuel": [
            "25 000 €",
            "~4 200 € (après exo JEI)",
            "3 000 — 6 000 €",
            "2 000 — 5 000 €",
            "1 500 €",
            "15 €",
            "500 €",
            "2 000 €",
            "**~38 000 — 44 000 €**",
            "",
            "~14 000 € (personnel uniquement)",
            "30 000 €",
            "**~44 000 €**",
            "",
            "**~0 € (couvert par CIR + BPI)**",
        ],
    }
    st.dataframe(budget, use_container_width=True, hide_index=True)

    st.info("Le CIR + Bourse French Tech couvrent quasi intégralement le coût de la première année. "
            "Le consulting IT d'Amine finance le reste en trésorerie.")

    # -----------------------------------------------------------------------
    # Checklist JEI/CIR
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("Checklist JEI & CIR — documents à préparer")

    col_jei, col_cir = st.columns(2)
    with col_jei:
        st.markdown("##### Dossier JEI")
        st.markdown("""
- [ ] Extrait Kbis (< 3 mois)
- [ ] Statuts à jour (objet social mentionne R&D)
- [ ] Liasse fiscale dernier exercice
- [ ] Organigramme + CV dirigeants
- [ ] Description activité R&D (verrous technologiques)
- [ ] Budget R&D vs charges totales (ratio ≥ 20%)
- [ ] Attestation sur l'honneur : indépendance, pas de restructuration
- [ ] Contrat de travail Nesrine (mention 100% R&D)
- [ ] Relevé de temps R&D (≥ 50% pour chaque chercheur)
- [ ] Lettre de demande de rescrit (LRAR)
""")

    with col_cir:
        st.markdown("##### Dossier CIR")
        st.markdown("""
- [ ] **Dossier technique** (format MESRI) :
  - [ ] Contexte et objectifs du projet
  - [ ] État de l'art et bibliographie
  - [ ] Verrous scientifiques/techniques identifiés
  - [ ] Démarche expérimentale (hypothèses, tests, résultats)
  - [ ] Indicateurs de nouveauté / amélioration substantielle
- [ ] **Dossier financier** :
  - [ ] Salaires bruts du personnel R&D
  - [ ] Charges patronales effectivement payées
  - [ ] Calcul du forfait fonctionnement (40%)
  - [ ] Autres dépenses éligibles (matériel, sous-traitance)
- [ ] **Pièces justificatives** :
  - [ ] Fiches de paie Nesrine
  - [ ] Relevés de temps R&D
  - [ ] Cahier de laboratoire (daté, signé)
  - [ ] Enveloppe Soleau (récépissé INPI)
  - [ ] Commits GitHub (preuve d'activité R&D datée)
- [ ] Formulaire **2069-A** (à joindre à la liasse fiscale)
- [ ] Lettre de demande de rescrit CIR (LRAR)
""")

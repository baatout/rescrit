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
    find_optimal_salary,
    find_optimal_salary_jei,
    net_to_gross,
    scenario_jei,
    scenario_no_salary,
    scenario_with_salary,
    _max_feasible_net,
    _salariale_rate_below_pass,
    _salariale_rate_above_pass,
)
from simulation.constants import PASS, ASSIETTE_CSG_COEFF, PS_CSG, PS_CRDS, PS_SOLIDARITE, PS_TOTAL
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

    max_net = int(_max_feasible_net(resultat))
    salaire_net = st.slider(
        "Salaire net annuel avant IR (€)",
        min_value=0, max_value=max(max_net, 1), value=0, step=500,
    )

    run_optim = st.checkbox("Trouver le salaire optimal", value=False)
    jei = st.checkbox("JEI (Jeune Entreprise Innovante)", value=False)

# ---------------------------------------------------------------------------
# Compute scenarios
# ---------------------------------------------------------------------------
s_no_sal = scenario_no_salary(resultat)
s_with_sal = scenario_with_salary(resultat, salaire_net)
s_jei = scenario_jei(resultat, salaire_net) if jei else None

if run_optim:
    with st.spinner("Optimisation en cours..."):
        optim = find_optimal_salary(resultat)
        optim_jei = find_optimal_salary_jei(resultat) if jei else None

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
tab_compare, tab_sankey, tab_optim = st.tabs(["Comparaison", "Diagramme Sankey", "Optimisation"])

# --- Tab 1: Comparison ---
with tab_compare:
    cols = st.columns(3 if jei else 2)
    col1, col2 = cols[0], cols[1]

    # ---- Sans salaire ----
    s = s_no_sal
    with col1:
        st.subheader("Sans salaire")

        metric_with_detail("BIC (100%)", fmt(s["bic"]),
            f"= Résultat SAS = **{fmt(s['resultat'])}**\n\n"
            f"Pas de salaire → tout le résultat est BIC pour le foyer.",
            key="ns_bic")

        ps = s["ps"]
        metric_with_detail(f"PS {PS_TOTAL_PCT}", fmt(ps["total"]),
            f"Assiette = BIC = {fmt(s['bic'])}\n\n"
            f"| Contribution | Taux | Montant |\n"
            f"|---|---|---|\n"
            f"| CSG | {PS_CSG_PCT} | {fmt(ps['csg'])} |\n"
            f"| CRDS | {PS_CRDS_PCT} | {fmt(ps['crds'])} |\n"
            f"| Prélèvement de solidarité | {PS_SOL_PCT} | {fmt(ps['solidarite'])} |\n"
            f"| **Total** | **{PS_TOTAL_PCT}** | **{fmt(ps['total'])}** |",
            key="ns_ps")

        ir = s["ir"]
        ir_formula = (
            f"**Revenu imposable** = BIC - CSG déductible (6,8%)\n\n"
            f"= {fmt(s['bic'])} - {fmt(ps['csg_deductible_ir'])} = **{fmt(ir['revenu_imposable'])}**\n\n"
            f"---\n\n" + ir_detail(ir)
        )
        metric_with_detail("IR", fmt(ir["ir"]), ir_formula, key="ns_ir")

        metric_with_detail("Total prélevé", fmt(s["total_prelevements"]),
            f"= PS + IR\n\n"
            f"= {fmt(ps['total'])} + {fmt(ir['ir'])} = **{fmt(s['total_prelevements'])}**",
            key="ns_total")

        metric_with_detail("Net en poche", fmt(s["net_en_poche"]),
            f"= Résultat - PS - IR\n\n"
            f"= {fmt(s['resultat'])} - {fmt(ps['total'])} - {fmt(ir['ir'])} = **{fmt(s['net_en_poche'])}**",
            key="ns_net")

        metric_with_detail("Taux effectif global", pct(s["taux_effectif"]),
            f"= Total prélevé / Résultat\n\n"
            f"= {fmt(s['total_prelevements'])} / {fmt(s['resultat'])} = **{pct(s['taux_effectif'])}**",
            key="ns_taux")

    # ---- Avec salaire ----
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
    delta = sw["net_en_poche"] - s["net_en_poche"]
    if salaire_net > 0:
        color = "green" if delta > 0 else "red"
        st.markdown(f"**Différence net en poche (salaire vs sans) : :{color}[{fmt(delta)}]**")
    if jei and s_jei and salaire_net > 0:
        delta_jei = s_jei["net_en_poche"] - s["net_en_poche"]
        color_j = "green" if delta_jei > 0 else "red"
        st.markdown(f"**Différence net en poche (JEI vs sans) : :{color_j}[{fmt(delta_jei)}]**")

    if run_optim:
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

    if salaire_net > 0:
        st.subheader(f"Avec salaire ({fmt(salaire_net)} net)")
        st.plotly_chart(build_sankey_with_salary(s_with_sal), use_container_width=True)

        if jei and s_jei:
            st.subheader(f"Avec salaire + JEI ({fmt(salaire_net)} net)")
            st.plotly_chart(build_sankey_with_salary(s_jei), use_container_width=True)

# --- Tab 3: Optimization curve ---
with tab_optim:
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

    # Baseline no-salary
    fig.add_hline(y=s_no_sal["net_en_poche"], line_dash="dash", line_color="gray",
                  annotation_text=f"Sans salaire: {fmt(s_no_sal['net_en_poche'])}")

    # Current salary marker
    if salaire_net > 0:
        fig.add_vline(x=salaire_net, line_dash="dash", line_color="#3498db",
                      annotation_text=f"Salaire choisi: {fmt(salaire_net)}")

    # Optimal markers
    if run_optim:
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

"""Plotly Sankey diagram builders for salary vs no-salary scenarios."""

from __future__ import annotations

import plotly.graph_objects as go


def _fmt(v: float) -> str:
    return f"{v:,.0f} €".replace(",", " ")


def build_sankey_no_salary(scenario: dict) -> go.Figure:
    """Sankey for the no-salary scenario."""
    r = scenario["resultat"]
    ps = scenario["ps"]
    ir_val = scenario["ir"]["ir"]
    net = scenario["net_en_poche"]

    labels = [
        f"Résultat SAS\n{_fmt(r)}",        # 0
        f"PS CSG\n{_fmt(ps['csg'])}",       # 1
        f"PS CRDS\n{_fmt(ps['crds'])}",     # 2
        f"PS Solidarité\n{_fmt(ps['solidarite'])}",  # 3
        f"IR\n{_fmt(ir_val)}",              # 4
        f"Net en poche\n{_fmt(net)}",       # 5
    ]

    source = [0, 0, 0, 0, 0]
    target = [1, 2, 3, 4, 5]
    value = [ps["csg"], ps["crds"], ps["solidarite"], ir_val, net]
    colors = ["#e74c3c", "#e74c3c", "#e74c3c", "#e67e22", "#27ae60"]

    node_colors = ["#3498db", "#e74c3c", "#e74c3c", "#e74c3c", "#e67e22", "#27ae60"]

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20, thickness=25, line=dict(color="black", width=0.5),
            label=labels, color=node_colors,
        ),
        link=dict(source=source, target=target, value=value, color=colors),
    ))
    fig.update_layout(
        title_text="Flux financier — Sans salaire",
        font_size=13, height=450,
    )
    return fig


def build_sankey_with_salary(scenario: dict) -> go.Figure:
    """Sankey for the with-salary scenario."""
    r = scenario["resultat"]
    gross = scenario["salaire_brut"]
    pat = scenario["patronales"]["total"]
    sal = scenario["salariales"]
    sal_total = sal["total"]
    sal_net = sal["net_received"]
    bic = scenario["bic"]
    ps = scenario["ps"]
    ir_val = scenario["ir"]["ir"]
    net = scenario["net_en_poche"]

    # Nodes
    labels = [
        f"Résultat SAS\n{_fmt(r)}",              # 0
        f"Charges patronales\n{_fmt(pat)}",       # 1
        f"Salaire brut\n{_fmt(gross)}",           # 2
        f"BIC résiduel\n{_fmt(bic)}",             # 3
        f"Cotisations salariales\n{_fmt(sal_total)}",  # 4
        f"Salaire net\n{_fmt(sal_net)}",          # 5
        f"PS CSG\n{_fmt(ps['csg'])}",             # 6
        f"PS CRDS\n{_fmt(ps['crds'])}",           # 7
        f"PS Solidarité\n{_fmt(ps['solidarite'])}",  # 8
        f"IR\n{_fmt(ir_val)}",                    # 9
        f"Net en poche\n{_fmt(net)}",             # 10
    ]

    source = [0,  0,  0,   2,  2,   3,  3,  3,   5,  3,   ]
    target = [1,  2,  3,   4,  5,   6,  7,  8,   10, 10,   ]
    value =  [pat, gross, bic, sal_total, sal_net, ps["csg"], ps["crds"], ps["solidarite"], sal_net, bic - ps["total"]]

    # Subtract IR from net flows
    if ir_val > 0:
        source.append(10)  # from "net en poche" node — conceptually IR comes from the foyer
        target.append(9)
        value.append(ir_val)

    # Avoid negative values in edge cases
    value = [max(0, v) for v in value]

    link_colors = [
        "#e74c3c",   # patronales
        "#3498db",   # gross
        "#3498db",   # bic
        "#e74c3c",   # salariales
        "#27ae60",   # sal net
        "#e74c3c",   # PS csg
        "#e74c3c",   # PS crds
        "#e74c3c",   # PS solidarité
        "#27ae60",   # sal net → pocket
        "#27ae60",   # bic net → pocket
    ]
    if ir_val > 0:
        link_colors.append("#e67e22")  # IR

    node_colors = [
        "#3498db",  # resultat
        "#e74c3c",  # patronales
        "#3498db",  # brut
        "#3498db",  # bic
        "#e74c3c",  # salariales
        "#27ae60",  # sal net
        "#e74c3c",  # PS csg
        "#e74c3c",  # PS crds
        "#e74c3c",  # PS solidarité
        "#e67e22",  # IR
        "#27ae60",  # net en poche
    ]

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20, thickness=25, line=dict(color="black", width=0.5),
            label=labels, color=node_colors,
        ),
        link=dict(source=source, target=target, value=value, color=link_colors),
    ))
    fig.update_layout(
        title_text="Flux financier — Avec salaire",
        font_size=13, height=500,
    )
    return fig

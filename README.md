# Rescrit fiscal — Beluga Paris SAS

Simulateur de rémunération pour SAS à l'IR (régime 2026) avec scénarios JEI + CIR.

## Simulation

### Prérequis

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets recommandé)

### Installation

```bash
uv sync
```

### Lancer l'application

```bash
uv run streamlit run simulation/app.py
```

L'application s'ouvre sur `http://localhost:8501`.

### Onglets disponibles

| Onglet | Contenu |
|--------|---------|
| **Comparaison** | Scénarios côte à côte : sans salaire / avec salaire / JEI / Split Amine+Nesrine |
| **Diagramme Sankey** | Flux de revenus → prélèvements → net |
| **Optimisation** | Courbe net en poche selon le salaire, avec optimum calculé |
| **Documentation JEI & CIR** | Règles, conditions, calculs, stratégie |
| **Plan d'action** | Jalons détaillés, budget, checklist dossiers JEI/CIR |

### Mode Split (Amine + Nesrine)

Activez le mode **Split (Amine + Nesrine)** dans la barre latérale pour simuler :
- Amine : salaire non-R&D (président, pas de chômage)
- Nesrine : salaire 100% R&D avec exonérations JEI + CIR calculé automatiquement

Le champ **Autres charges annuelles** permet de renseigner loyer, services, etc.
pour le calcul du ratio R&D ≥ 20% (seuil JEI).

### Structure

```
simulation/
├── app.py          # Interface Streamlit
├── engine.py       # Moteur de calcul (cotisations, IR, CIR)
├── constants.py    # Taux 2026 (source unique)
└── sankey.py       # Diagrammes Sankey Plotly
```

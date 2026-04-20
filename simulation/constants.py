"""2025 fiscal and social parameters — single source of truth."""

from math import inf

# --- Plafonds ---
PASS = 47_100  # Plafond annuel de la sécurité sociale
SMIC_ANNUEL = 21_622  # SMIC brut annuel (151.67h × 11.88€ × 12)
SEUIL_MALADIE = 2.5 * SMIC_ANNUEL  # ~54,055 — taux réduit maladie
SEUIL_AF = 3.5 * SMIC_ANNUEL  # ~75,677 — taux réduit allocations familiales
PLAFOND_T2 = 8 * PASS  # 376,800 — plafond tranche 2 retraite complémentaire

# --- Cotisations patronales (employeur) ---
# Maladie: 7% si gross ≤ 2.5 SMIC, 13% sinon (appliqué sur totalité, pas marginal)
PATRONALE_MALADIE_REDUIT = 0.07
PATRONALE_MALADIE_PLEIN = 0.13
# Vieillesse
PATRONALE_VIEILLESSE_PLAFONNEE = 0.0855  # jusqu'au PASS
PATRONALE_VIEILLESSE_DEPLAFONNEE = 0.0202  # sur totalité
# Allocations familiales: 3.45% si gross ≤ 3.5 SMIC, 5.25% sinon
PATRONALE_AF_REDUIT = 0.0345
PATRONALE_AF_PLEIN = 0.0525
# AT/MP (approximation)
PATRONALE_ATMP = 0.01
# Retraite complémentaire AGIRC-ARRCO
PATRONALE_RC_T1 = 0.0472  # tranche 1 (jusqu'au PASS)
PATRONALE_RC_T2 = 0.1295  # tranche 2 (PASS → 8×PASS)
# CEG (Contribution d'Équilibre Général)
PATRONALE_CEG_T1 = 0.0129
PATRONALE_CEG_T2 = 0.0162
# Autres
PATRONALE_CSA = 0.003  # Contribution solidarité autonomie
PATRONALE_FNAL = 0.001  # FNAL <50 salariés (sur PASS)
PATRONALE_FORMATION = 0.0055  # Formation professionnelle <11 salariés
PATRONALE_APPRENTISSAGE = 0.0044  # Taxe d'apprentissage

# --- Cotisations salariales (employé) ---
SALARIALE_VIEILLESSE_PLAFONNEE = 0.069  # jusqu'au PASS
SALARIALE_VIEILLESSE_DEPLAFONNEE = 0.004  # sur totalité
SALARIALE_RC_T1 = 0.0315
SALARIALE_RC_T2 = 0.0864
SALARIALE_CEG_T1 = 0.0086
SALARIALE_CEG_T2 = 0.0108
# CSG/CRDS sur salaire (assiette = 98.25% du brut)
ASSIETTE_CSG_COEFF = 0.9825
CSG_DEDUCTIBLE = 0.068  # déductible de l'IR
CSG_NON_DEDUCTIBLE = 0.024  # non déductible
CRDS_SALAIRE = 0.005  # non déductible
# Pas de chômage pour président de SAS
# Chômage patronale (salariée classique, pas mandataire social)
PATRONALE_CHOMAGE = 0.0405
PATRONALE_AGS = 0.0020

# --- Prélèvements sociaux patrimoniaux (LFSS 2026) ---
# CSG patrimoine: 10.6% pour revenus du capital (BIC SAS IR inclus)
# dont +1.4% = contribution financière pour l'autonomie (CFA), non déductible
PS_CSG = 0.106
PS_CRDS = 0.005
PS_SOLIDARITE = 0.075
PS_TOTAL = PS_CSG + PS_CRDS + PS_SOLIDARITE  # 0.186
PS_CSG_DEDUCTIBLE_IR = 0.068  # inchangé — le +1.4% est non déductible

# --- JEI (Jeune Entreprise Innovante) ---
JEI_SALARY_CAP = 4.5 * SMIC_ANNUEL  # plafond rémunération annuelle pour exonération (~97 300 €)
JEI_EXONERATION_CAP = 5 * PASS  # plafond annuel exonération par établissement (235 500 €)
JEI_RD_THRESHOLD = 0.20  # 20% des charges déductibles (depuis 2025)

# --- CIR (Crédit d'Impôt Recherche) ---
CIR_RATE = 0.30  # 30% jusqu'à 100M€
CIR_FORFAIT_FONCTIONNEMENT = 0.40  # 40% forfait (depuis fév. 2025, était 43%)

# --- Impôt sur le revenu (barème 2026 sur revenus 2025) ---
IR_BAREME = [
    (11_600, 0.00),
    (29_579, 0.11),
    (84_577, 0.30),
    (181_917, 0.41),
    (inf, 0.45),
]

# Quotient familial
PARTS_QF = 2.5  # couple marié + 1 enfant
PARTS_BASE = 2.0  # couple sans enfant (pour calcul plafonnement)
PLAFOND_DEMI_PART = 1_759  # avantage max par demi-part supplémentaire

# Abattement 10% frais professionnels sur salaire
ABATTEMENT_10_PLANCHER = 495
ABATTEMENT_10_PLAFOND = 14_171

# Recours décision 17,2 %

---

## Résumé exécutif

### Situation personnelle

- Bénéficiaire **ARE** depuis **décembre 2024** (échéance estimée **juin 2026**)
- **Micro-entreprise** (BIC — vente de produits digitaux) — chiffre d'affaires 2025 de 3 000 €
- Président non salarié d'une **SAS Beluga Paris**

### Beluga Paris SAS

- **Création :** mars 2022 — **Clôture d'exercice :** 30 septembre
- **Régime fiscal :** option **Impôt sur le Revenu (IR)** depuis **septembre 2024**
- **Dirigeant :** président **non salarié**, **50 %** des parts
- **Associée :** conjointe, **50 %** des parts, **sans mandat social**
- **Activité dominante (exercice en cours) :** programmation / consulting informatique (devient majoritaire pour la 1ʳᵉ fois en 2025)
- **Immobilisation :** véhicule de société amorti sur **5 ans** → **avantage en nature** à traiter
- **Prévision fin d'exercice (30/09) :** CA 123 k€, charges 11 k€ (hors salaires) → résultat 112 k€ (avant rémunération et IR)

---

## Contexte fiscal / social

- À la suite d'un **rescrit fiscal**, il m'a été indiqué que **17,2 %** de prélèvements sociaux seraient applicables pour la prochaine déclaration, compte tenu de mon statut de président non salarié.
- Ce rescrit est **problématique** car mon premier courrier de demande de rescrit a été auto-généré par mon cabinet comptable et manquait des informations importantes : bénéficiaire ARE + auto-entrepreneur sur une activité complètement différente.
- Le délais de recours de deux mois est déjà passé

---

## Objectifs

1. **URGENT :** Faire un rescrit pour défendre ma position en 2025
2. Que faire pour blinder ma position en 2026 et éviter ce piège de 17,2 % ? (exemple : est-ce que le versement d'un salaire est suffisant ?)

---

## Tâches

- Renommer les documents
- Validation lecture PDF
- Validation lecture Légifrance
- Création de deux prompts :
  - Premier prompt pour un agent Claude qui agit comme mon avocat
  - Deuxième prompt pour un agent Claude qui agit comme représentant officiel de la Direction régionale des finances publiques d'Île-de-France et de Paris (DRFIP), et qui essaie de contrer les arguments du premier agent

## Sys Prompt

- Help me create two prompts:
   1. Premier prompt pour un agent Claude qui agit comme mon avocat. 
   2. Deuxième prompt pour un agent Claude qui agit comme représentant officiel de la Direction régionale des finances publiques d'Île-de-France et de Paris (DRFIP), et qui essaie de contrer les arguments du premier agent

- Each of the prompts will be in the format of a CLAUDE.md
- First prompt will live under avocat/ and the second will live under fisc/
- Each agent will have access to documents in its own folder + documents in the debat/ folder
- Both agents will communicate through the debat/ folder in a document called conversation.md that will be initiated by a letter from the "avocat" agent then a response from "fisc" so on so forth
- Every time an agent mentions an attached document, it needs to move it from its own folder and make it available for the other agent in the debat/ folder
- Same thing for a law or document from the internet: if an agent mentions it, it has to download it and put it as an attachment in the debat/ folder
- Agents can use poppler or any other tool to read pdfs
- Agents can read laws from Légifrance or any official source. In the likely case that an agent cannot read from Légifrance, it should ask the user (me) to download the document / law for it
- We reserve the "#" headers in conversation.md to mark the different sections of letters from avocat and responses from fisc
- conversation.md will be in french

Wdyt of this mechanism ? Any area of improvement or things I didn't think of ? Should the CLAUDE.md prompts be in french or english
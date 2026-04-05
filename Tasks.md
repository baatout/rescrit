# Tasks

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
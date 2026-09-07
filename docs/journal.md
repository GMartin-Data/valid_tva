# Journal de bord

## J1 — 2026-09-07

### Matinée — lecture du brief, exploration du référentiel

- Lecture méticuleuse du brief ; deux incohérences signalées au formateur et
  amendées (fichier Excel non fourni, « module fourni » → module de validation
  structurelle à écrire nous-mêmes).
- Exploration du CSV **avant tout code de production**
  (`exploration/01_explore_csv.py`). Constats clés sur 10 000 lignes :
  - 15 « pays » déclarés : 10 pays UE légitimes, 3 codes fantaisistes
    (ZZ 115, QQ 109, XX 87), et GB 104 + UK 104 (piège Brexit : hors VIES).
  - **261 lignes vides sous 6 formes**, dont un `NU.LL` (id 5937) qui ne se
    révèle qu'après normalisation. Leçon : détecter le vide aussi *après*
    nettoyage.
  - 1 698 lignes (17 %) avec bruit de saisie (espaces, tirets, points,
    minuscules) → sauvées par la normalisation, pas invalides.
  - 532 lignes sans préfixe pays ; `pays_declare` fiable (100 % renseigné,
    zéro discordance avec les préfixes existants).
  - Doublons : 438 lignes en excès sur clé normalisée (135 seulement sur clé
    brute) — la déduplication doit suivre la normalisation.

### Décisions prises (détail : docs/architecture.md à venir)

- **D1** — Sans préfixe : reconstruction via `pays_declare`, tracée
  (`prefix_added`). Options rejet / indéterminé écartées (critère « bruit de
  saisie ≠ invalide » du brief ; catégorie indéterminé réservée aux cas
  réellement intranchables).
- **D2** — Doublon : clé canonique = (pays, numéro normalisé) après
  reconstruction. Aucune ligne supprimée ; le verdict s'attache au numéro
  distinct. Raison sociale hors clé (divergences signalées au rapport).
- **D3** — GB/UK : **différé** en attente d'une donnée identifiée — le
  comportement réel de VIES sur un préfixe GB (appels manuels J2).
  Différer n'est pas fuir : on sait exactement quelle information on attend.

### Mesure VIES (`exploration/02_vies_timing.py`)

- 10 appels réels (1 par pays UE du référentiel), endpoint REST
  `check-vat-number`. Latence **bimodale** : min 33 ms, médiane 0,39 s,
  moyenne 1,85 s, max 8,6 s — VIES relaie vers chaque administration
  nationale, la lenteur dépend de l'État membre (FR 8,6 s, SE/BE ~4 s,
  IT/NL/PL ~33 ms).
- **Extrapolation naïve sur 10 000 numéros : de ~1,1 h (médiane seule) à
  ~5,1 h (moyenne observée), hors retries.** La réduction du volume n'est pas
  cosmétique, elle conditionne la faisabilité de la campagne.
- Sondes : `GB...` et `ZZ...` reçoivent la même réponse
  `actionSucceed=false / INVALID_INPUT` — VIES **refuse l'entrée** (hors
  périmètre) au lieu de répondre invalide. Un numéro GB ne peut être ni
  validé ni invalidé par VIES → donnée qui débloque la décision D3.
- Les 10 numéros testés sont tous `valid=False` ; conventions de « pas
  d'info » variables selon l'État (`name` = `'---'` ou `''`).

### Blocages / points d'attention

- Hook de permissions local : écriture de `.env.example` refusée (règle
  `.env*`) → valeurs par défaut documentées dans le README, le compose
  porte ses propres défauts. Sans impact.

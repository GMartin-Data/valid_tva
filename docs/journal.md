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

### Garde-fous qualité (workflow main-direct)

- Constat : commits directs sur `main` ≠ absence de CI — on a écarté la
  cérémonie PR, pas le contrôle qualité. Mise en place : **pre-commit**
  (ruff check + format, format Conventional Commits) + **GitHub Actions**
  (ruff + pytest à chaque push, badge dans le README). Le job pytest
  devient bloquant dès le premier fichier de test.

### Module structurel (test-first) et entonnoir chiffré

- Suite rouge d'abord (91 tests, commit `test:`), puis implémentation en
  trois paliers jusqu'au vert : normalisation (D1/D2), tamis pays+format,
  clés de contrôle des 10 pays. Oracle `python-stdnum` (tests uniquement) :
  accord complet sur 21 ancres réelles et ~200 mutations systématiques.
- **Entonnoir sur les 10 000 lignes** (`exploration/03_funnel.py`) :
  261 MISSING, 311 UNKNOWN_COUNTRY, 208 NON_EU_COUNTRY, 1 264 BAD_FORMAT,
  1 332 BAD_CHECK_DIGIT, puis 313 doublons parmi les 6 624 candidats →
  **6 311 appels VIES au lieu de 10 000 (−36,9 %)**.
- Enseignements : le tamis clé économise à lui seul 1 332 appels (valide la
  stratégie B/D4) ; les 532 préfixes reconstruits (D1) sont tous candidats ;
  les doublons « candidats » (313) diffèrent des doublons bruts (438) car
  une partie des doublons est d'abord rejetée structurellement — l'ordre
  des tamis conditionne les comptages.

### Schéma PostgreSQL et chargeur idempotent (test-first)

- Schéma 2 tables (`sql/schema.sql`) : `referential_rows` (reçu + déduit) /
  `vat_numbers` (numéros canoniques, futur porteur de l'observé VIES).
  Invariants en CHECK : candidat ⇔ motif NULL ; lien vat_number ⇒ candidat.
- Contrat testé avant implémentation (8 tests d'intégration, base jetable
  `tva_test`, skip propre sans Docker — mécanique détaillée en note 06) :
  rechargement sans doublon ET sans écrasement des verdicts VIES acquis
  (« on écrase le recalculable, on protège le périssable »).
- Chargement réel : 10 000 lignes, 6 624 candidats, 6 311 numéros distincts ;
  la requête SQL de répartition recoupe l'entonnoir à l'unité près ;
  double chargement vérifié sans dérive. **Résultat testable J1 atteint.**
- CI renforcée : service PostgreSQL (même image/port que le compose) — les
  tests d'intégration tournent aussi sur GitHub, symétrie local/CI.

### Blocages / points d'attention

- Hook de permissions local : écriture de `.env.example` refusée (règle
  `.env*`) → valeurs par défaut documentées dans le README, le compose
  porte ses propres défauts. Sans impact.
- **Premier run CI rouge (`EXE001`)** alors que le lint passait en local.
  Cause racine : aucune config ruff versionnée dans le repo — en local,
  ruff retombait silencieusement sur la config utilisateur
  (`~/.config/ruff/`), la CI appliquait ses règles par défaut (qui
  incluent EXE001 : shebang sur fichier non exécutable). Résolution :
  config `[tool.ruff]` committée dans `pyproject.toml` (source de vérité
  unique local/hooks/CI) + `chmod +x` des scripts à shebang. Leçon : une
  config de lint non versionnée rend le lint non reproductible — la CI
  l'a révélé dès son premier run.

## J2 — 2026-09-08

### Matinée — lire VIES sur pièces, trancher D5

- Sondes manuelles (`exploration/04_vies_manual_probes.py`, détail note 08) :
  bon (`valid=true` + nom/adresse réels), clé fausse, numéro inventé à clé
  correcte. Lecture fine : la clé fausse répond en 35 ms avec `name='---'`
  (tranchée sans consulter le registre), l'inventé bien formé subit la latence
  de consultation et revient avec `name=''` — VIES distingue les deux cas en
  creux.
- **Découverte non anticipée : `MS_MAX_CONCURRENT_REQ`** — saturation des
  requêtes simultanées vers un État membre, renvoyée en **HTTP 200** avec un
  corps d'erreur (`actionSucceed=false`), comme `INVALID_INPUT` en J1. Le
  numéro Saint-Gobain des tutoriels y bute systématiquement ; pattern
  « erreur applicative sous HTTP 200 » : un client qui ne lit que le statut
  HTTP fabriquerait des faux invalides.
- Salve de 40 appels réels (`exploration/05_vies_burst.py`) : 29 `false`,
  2 `true` (le référentiel synthétique contient de vrais numéros !),
  **9 saturations (22,5 %)** réparties sur DK/BE/NL/FR — phénomène de charge
  en heure de pointe européenne, pas une spécificité française. Latence par
  issue : saturation = rejet rapide, `valid=true` jusqu'à 11,9 s → le timeout
  de campagne reste généreux (30 s) sous peine de perdre les valides.
- En-têtes HTTP : `cache-control: no-store`, pas d'ETag — **aucune indication
  de fraîcheur protocolaire** ; seul `requestDate` (corps) horodate un verdict.
- **D5 tranchée** (détail note 02) : fraîcheur *exposée*, pas de péremption —
  l'API renvoie toujours le verdict stocké + son âge (jamais de re-appel VIES
  à la requête), `stale: true` au-delà de 7 jours (paramètre assumé
  arbitraire, cadence de re-campagne hebdomadaire). Périmètre : verdicts VIES
  uniquement — le structurel est déterministe (pas de TTL), l'indéterminé est
  une absence de verdict (retry, pas TTL).
- Timeline recalée : rendu effectif vendredi soir → run complet planifié
  jeudi soir (creux de charge, fraîcheur maximale au rendu) ; une sonde
  horaire de charge viendra le confirmer en fin de J2 — sans orchestrateur,
  un cron suffit.

### Campagne de vérification — contrat rouge

- Contrat d'intégration commité avant l'implémentation (9 tests,
  `tests/test_campaign.py`) : sélection (jamais vérifié + `unknown` toujours
  rejouable + périmé > 7 j ; ordre déterministe ; `limit` = mode échantillon),
  mapping des corps réels de la note 08 (`errorWrappers` → `unknown`, jamais
  `invalid`), reprise après interruption (commit par numéro).
- Client VIES **injectable** : les tests rejouent les corps observés le matin
  même, aucun réseau dans la suite. Fixtures de base jetable mutualisées dans
  `tests/conftest.py` au passage.

### Campagne — du rouge au vert, et le client réel

- Implémentation `src/valid_tva/campaign.py` : vert du premier coup
  (108 tests). Sélection SQL, mapping (`'---'`/`''` → NULL), commit par
  numéro — la reprise après interruption découle de ce choix, elle n'est pas
  un mécanisme ajouté. Journalisation structlog.
- Client réel `ViesClient` (httpx, timeout 30 s justifié par la salve du
  matin, connexion réutilisée) + CLI `python -m valid_tva.campaign --limit N`.
  Corps non-JSON (page HTML d'un proxy) → `{"raw": ...}` tronqué à 500
  caractères : diagnostic humain seulement, lignes de log bornées — gestion
  d'erreur à la frontière réelle qu'est un service externe.

### Incident : le cache ruff qui mentait (écho de la leçon J1)

- Push du jalon → **CI rouge** (`I001`, imports mal triés dans
  `tests/test_campaign.py`) alors que pre-commit et lint local affichaient
  « Passed ».
- Diagnostic par élimination : versions ruff identiques (v0.16.6 partout),
  pas d'exclude, pas de gitignore en cause… jusqu'à `--no-cache` : **échec
  identique à la CI**. Cause racine en deux temps : (1) un `ruff check
  --fix` antérieur avait lui-même produit le mauvais tri (classification
  first-party de `valid_tva` instable pendant le fix) et écrit « 0
  diagnostic » dans `.ruff_cache` ; (2) tous les contrôles locaux suivants
  — pre-commit compris, même cache — relisaient cette entrée empoisonnée
  en 0,01 s sans analyser.
- Réparation en trois couches : le symptôme (tri corrigé), la cause
  (`known-first-party = ["valid_tva"]` épinglé dans `pyproject.toml` — plus
  d'inférence), la vérification (`ruff clean` + lint/format/tests à froid,
  CI verte).
- Leçon, jumelle de l'`EXE001` de J1 : **un lint caché peut mentir ; la CI
  à froid est l'arbitre.** Après un `--fix` au résultat surprenant,
  revérifier avec `--no-cache` ; et ne pas laisser un linter *inférer* une
  frontière (first-party vs third-party) qu'on peut déclarer.

### Échantillons de campagne : mesure → correctif → re-mesure (×4,5)

- Run 1 (200 numéros, 12h01) : **56,5 % d'indéterminés**. Diagnostic :
  `ORDER BY vat_number` regroupe par pays → 9 minutes à marteler le seul
  registre belge, face à une limite de saturation *par État membre*. Effet
  secondaire de charge d'un choix fait pour la prévisibilité — révélé
  uniquement par le run réel, invisible dans les tests.
- Lacune corrigée au passage : le log `wrapped_error` n'embarquait pas le
  code d'erreur brut (réflexe pourtant noté le matin même dans la fiche
  « erreur applicative sous HTTP 200 » — l'écart entre savoir et appliquer).
- Correctif test-first : contrat d'ordre mis à jour (round-robin par pays,
  toujours déterministe donc toujours reprenable), rouge → vert, 108 tests.
- Run 2 (200 numéros, 12h21) : **12,5 % d'indéterminés** (tous
  `MS_MAX_CONCURRENT_REQ`, désormais prouvé par les logs) ; ~75 % des
  `unknown` belges repris convergent au second essai — le retry par
  re-éligibilité fonctionne sans mécanisme dédié. Cadence ~1,55 s/numéro →
  run complet estimé ≈ 2 h 40, compatible avec la fenêtre de jeudi soir.
- 380 numéros distincts touchés (262 verdicts déterminés, 118 `unknown`
  rejouables) — comptage vérifié en base, recoupé à l'unité près.

### Après-midi — API REST (test-first) et Swagger

- Contrat rouge de 12 tests avant toute implémentation : verdict + origine
  (`structural` / `vies` / `never_checked`) + fraîcheur D5 (`stale` au-delà
  de 7 j, verdict toujours servi), bruit normalisé, `?country=` (pendant
  API de D1), tout verdict en HTTP 200. App factory injectable
  (`create_app(get_conn)`) : les tests pointent la base jetable, même
  philosophie que le client VIES injectable de la campagne.
- **L'API ne parle jamais à VIES** (conséquence directe de D5) : structurel
  recalculé à la volée (déterministe), observé lu en base. Le cas « VIES
  injoignable » du brief est absorbé par l'architecture au lieu d'être géré.
- Piège technique du jour : `from __future__ import annotations` +
  dépendance FastAPI définie en closure → la forme `Annotated[...,
  Depends(db)]` devient une chaîne irrésoluble (ForwardRef vers un nom
  local). Retour à la forme `= Depends(db)` avec `noqa: B008` documenté.
- Deux erreurs dans mes propres données de test, débusquées par le rouge et
  le smoke test : un numéro PT inventé structurellement faux (l'API avait
  raison de le rejeter), et l'étiquette « Amazon = valide en base » alors
  qu'il est hors référentiel (`never_checked` correct). Le smoke test réel
  (uvicorn + curl, 4 familles de réponses, cas nominal NV PLUTO) reste
  irremplaçable même avec un contrat vert.
- OpenAPI enrichi (vérifié sur le document généré) : résumé et description
  d'endpoint, paramètres documentés, 9 champs de `Verdict` décrits avec les
  sémantiques clés (« unknown ≠ mauvais numéro », « stale : servi, signalé,
  au consommateur de juger »), exemple complet.

### Fin J2 — sonde horaire de charge (la fenêtre de tir devient une mesure)

- `exploration/06` : 3 appels/heure vers FR, BE, DK (témoins les plus
  saturés), une ligne CSV par mesure, série accumulée jusqu'à jeudi.
  Installée en cron (minute 17 ; chemin absolu vers uv — PATH minimal de
  cron ; sortie vers un .log, pas /dev/null). Chaîne validée en
  environnement cron simulé (`env -i`).
- **Critère de décision fixé avant les données** : fenêtre de lancement =
  début de la plage contiguë ≥ 3 h au taux de saturation minimal sur ~48 h
  de mesures, départage par latence médiane ; cas dégradé (pas de creux
  net) = lancement jeudi ~22h quand même, les `unknown` se rejouant
  vendredi matin. La sonde optimise le premier passage, elle ne
  conditionne pas la faisabilité.

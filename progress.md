# Progress — valid_tva

## Dernière mise à jour
Date : 2026-09-08 15:25
Session : 4d6c8de5-20a3-43e5-923a-2d614571f436

## Tâches complétées
- Sondes VIES manuelles + salve de 40 (exploration/04-05, note 08) :
  taxonomie complète des réponses, MS_MAX_CONCURRENT_REQ (HTTP 200 !),
  distinction clé-fausse/inexistant, aucune indication de fraîcheur
  protocolaire — fiche générique « erreur applicative sous HTTP 200 »
  dans ~/explain/concepts/
- D5 tranchée (fraîcheur exposée, jamais de péremption, stale > 7 j)
- Campagne de vérification test-first (9 tests) : sélection en base
  (NULL + unknown + périmé), verdict commité par numéro (reprise par
  conception), client VIES injectable, structlog, CLI --limit
- Deux runs échantillon de 200 : piège de l'ordre alphabétique découvert
  (56,5 % unknown) et corrigé test-first par entrelacement des pays
  (12,5 %) ; 380 numéros distincts en base (262 verdicts, 118 unknown)
- API REST test-first (12 tests) : GET /vat/{numero}, verdict + origine +
  fraîcheur, jamais d'appel VIES live, ?country= (D1), tout verdict = 200 ;
  smoke test réel ; Swagger enrichi (champs, params, exemple) ; README
  (campagne + API)
- Sonde horaire de charge installée (cron minute 17, exploration/06) :
  FR/BE/DK, CSV ../brief_valid_tva/vies-load-probe.csv, validée de bout
  en bout (tir autonome 15h17 confirmé)
- Incident résolu : cache ruff empoisonné par un --fix instable (CI rouge,
  lint local menteur) → tri corrigé, known-first-party épinglé, leçon dans
  lessons-inbox (dotfiles) ; suite = 120 tests verts, CI verte
- Fixtures d'intégration mutualisées (conftest.py : test_db, conn, seed)

## En cours
- Sonde horaire : accumulation autonome jusqu'à jeudi (machine allumée !)
- Rien d'autre en suspens — coupe volontaire sur jalon J2 complet

## Prochaines étapes
1. Jeudi ~17h : exploitation de la sonde (one-shot exploration/07 :
   agrégation par heure × pays) — critère FIXÉ A PRIORI : fenêtre contiguë
   ≥ 3 h au taux de saturation minimal, départage latence médiane ;
   dégradé = lancement 22h quand même
2. Jeudi soir : run complet (~6 050 numéros, ≈ 2 h 40), nohup, Docker up
3. Vendredi matin : reprise/2ᵉ passage sur les unknown résiduels
4. Vendredi : rapport de réconciliation reproductible en une commande
   (la requête de répartition des verdicts rejoint sql/)
5. Vendredi : note d'architecture 1 page (inclure : pourquoi pas de retry
   in-run — mauvais étage/échelle de temps ; D5 ; fenêtre mesurée)
6. Finalisation : test reclonage README, lien repo sur la plateforme
7. Révision pédagogique des notes (feynman-mentor, instance fraîche,
   ../brief_valid_tva/)

## Écarts vs PRD
- Pas de PRD (brief amendé fait foi) ; timeline recalée : rendu effectif
  vendredi soir (J1-J2 du brief = squelette complet, fin de semaine =
  consolidation)

## Décisions prises
- Track léger (sans ADR), en plus de D1-D4 (voir bloc J1) :
  - D5 : fraîcheur exposée sans péremption, stale > 7 j, TTL = cadence de
    re-campagne — détail note 02 § D5, résumé CLAUDE.md → décidé
  - Sélection de campagne entrelacée par pays (contrat de test) — motivée
    par la saturation par État membre, mesurée avant/après → décidé
  - Pas de retry in-run (tenacity) : mauvaise échelle de temps pour une
    erreur de capacité ; re-éligibilité en base = le retry au bon étage ;
    tenacity en réserve si erreurs transport au run complet → décidé
  - Critère de fenêtre de tir défini avant les données (voir étape 1)
  - known-first-party épinglé dans pyproject (plus d'inférence isort)

## Blocages
- Aucun. Points d'attention : machine allumée jusqu'à jeudi (sonde) et
  jeudi soir (run) ; port 8000 local occupé par une autre app (API servie
  sur 8321 en démo) ; Docker à démarrer en début de session

---

# Historique — J1

## Dernière mise à jour (J1)
Date : 2026-09-07 15:27
Session : 949d9450-0d8d-49b9-8cc6-4d97c39a953d

## Tâches complétées
- Brief lu et amendé (Excel absent, « module fourni » → module maison)
- Exploration CSV sans code de production (exploration/01) : 15 pays dont
  ZZ/QQ/XX/GB/UK, 261 vides sous 6 formes (dont NU.LL), 17 % de bruit,
  532 sans préfixe, doublons — chiffres en notes 01 et journal
- Mesure VIES (exploration/02) : latence bimodale 33 ms–8,6 s,
  naïf = 1,1–5,1 h ; sondes GB/ZZ → INVALID_INPUT (débloque D3)
- Module structurel test-first : 91 tests rouges validés puis verts
  (normalize/structural/keys), oracle python-stdnum (accord complet,
  ~200 mutations), 3 familles d'algorithmes pour 10 pays
- Entonnoir complet (exploration/03) : 10 000 → 6 311 appels VIES (−36,9 %)
- Schéma PostgreSQL 2 tables + chargeur idempotent (8 tests d'intégration,
  base jetable tva_test) ; chargement réel vérifié + rechargement sans dérive
- Résultat testable J1 : ATTEINT (commande unique, verdicts en base,
  requête de répartition, réduction chiffrée)
- Outillage : repo GitHub public (GMartin-Data/valid_tva), pre-commit
  (ruff + conventional commits), CI GitHub Actions avec service PostgreSQL
  (99 passed, 0 skip), paths-ignore docs, projet uv installable
- Documentation : README (lancement complet J1), journal de bord à jour,
  note d'architecture amorcée (références officielles 3 niveaux),
  notes d'atelier 01–07 dans ../brief_valid_tva/notes/

## En cours
- Rien de suspendu — coupe volontaire sur jalon J1 propre

## Prochaines étapes
1. ~~Sondes VIES manuelles + salve de 40~~ FAIT (note 08, exploration/04-05)
2. ~~Trancher D5~~ FAIT (note 02 § D5, CLAUDE.md)
3. Campagne de vérification : mode échantillon (~200), temporisation,
   journalisation (structlog), reprise après interruption (test-first)
4. J2 après-midi : API REST FastAPI (verdict + origine + fraîcheur,
   cas « VIES injoignable et rien en mémoire »), OpenAPI
4bis. Fin J2 (rendu réel = vendredi soir) : sonde horaire de charge VIES
   (cron, ~3 appels/h, réutilise exploration/04) pour cartographier la
   période creuse ; run complet jeudi soir (nohup, machine allumée),
   reprise vendredi matin si besoin — PAS d'orchestrateur
5. Rapport de réconciliation reproductible par une commande
6. Finalisation : note d'architecture (1 page), test du reclonage README,
   lien du repo sur la plateforme
- Révision pédagogique des notes : instance fraîche dans
  ../brief_valid_tva/ en mode candide (feynman-mentor) — notes/07 en appui

## Écarts vs PRD
- Pas de PRD (le brief amendé fait foi : ../brief_valid_tva/brief-valid-tva.md)

## Décisions prises
- Track léger, sans ADR — source : notes/02-decisions-preparation.md
  (résumé dans CLAUDE.md projet) :
  - D1 reconstruction des préfixes (tracée) → décidé
  - D2 doublon = pays + numéro normalisé → décidé
  - D3 GB/UK invalide NON_EU_COUNTRY → décidé
  - D4 validation format + clés maison, oracle stdnum → décidé
  - D5 fraîcheur exposée sans péremption, stale > 7 j, TTL = cadence de
    re-campagne (jamais de re-appel VIES à la requête) → décidé (J2)
- Workflow : commits directs sur main (exemption déclarée CLAUDE.md),
  garde-fous pre-commit + CI ; pas de trailers de co-authoring

## Blocages
- Aucun (hooks .env* : contourné par défauts convergents compose/db.py ;
  Docker Desktop à démarrer manuellement en début de session)

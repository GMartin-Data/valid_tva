# Progress — valid_tva

## Dernière mise à jour
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
1. J2 matin : 3 appels VIES à la main (bon / clé fausse / inventé), lire
   TOUTES les réponses — matière pour D5 (TTL) ; puis quelques dizaines
   d'appels d'affilée en observant les cas non passants
2. Trancher D5 (durée de validité d'un verdict) — note 02 § D5
3. Campagne de vérification : mode échantillon (~200), temporisation,
   journalisation (structlog), reprise après interruption (test-first)
4. J2 après-midi : API REST FastAPI (verdict + origine + fraîcheur,
   cas « VIES injoignable et rien en mémoire »), OpenAPI
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
  - D5 TTL verdict VIES → DIFFÉRÉ (info attendue : réponses VIES réelles J2)
- Workflow : commits directs sur main (exemption déclarée CLAUDE.md),
  garde-fous pre-commit + CI ; pas de trailers de co-authoring

## Blocages
- Aucun (hooks .env* : contourné par défauts convergents compose/db.py ;
  Docker Desktop à démarrer manuellement en début de session)

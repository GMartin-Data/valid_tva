# valid_tva — Conventions projet

## Contexte
Brief pédagogique de 2 jours (voir `../brief_valid_tva/brief-valid-tva.md`) :
qualifier 10 000 numéros de TVA intracommunautaire (valide / invalide /
indéterminé) via normalisation, validation structurelle, puis vérification VIES,
et exposer une API REST (verdict + origine + fraîcheur).

## Dérogations aux conventions globales
- **Commits directs sur `main`** (exemption au workflow branche → PR) :
  projet solo de 2 jours, évalué sur la lisibilité et la régularité de
  l'historique — la cérémonie PR sans relecteur n'apporte rien ici.

## Conventions
- Python géré par `uv` ; lancer tout via `uv run`.
- Code de production dans `src/valid_tva/` ; scripts one-shot conservés dans
  `exploration/` (traçabilité pédagogique, pas de garantie de qualité prod).
- SQL brut versionné dans `sql/` (pas d'ORM : deux tables, lisibilité évaluateur).
- Livrables documentaires dans `docs/` (journal de bord, note d'architecture)
  et `README.md` — alimentés au fil de l'eau, en français ; code, commentaires
  et commits en anglais.
- Les notes d'atelier (non livrables) vivent hors repo :
  `../brief_valid_tva/notes/`.

## Décisions structurantes (résumé — détail dans docs/architecture.md)
- D1 : numéros sans préfixe pays → reconstruction via `pays_declare`, tracée
  (`prefix_added`).
- D2 : doublon = même couple (pays, numéro normalisé) après reconstruction ;
  aucune ligne supprimée, verdict porté par le numéro distinct.
- D3 : GB/UK → invalide structurel, motif `NON_EU_COUNTRY` (distinct de
  `UNKNOWN_COUNTRY` pour ZZ/QQ/XX) ; jamais envoyé à VIES — VIES répond
  INVALID_INPUT (hors périmètre), il n'invalide pas.
- D4 : validation structurelle = format par pays (regex) + clés de contrôle
  implémentées à la main, testées contre `python-stdnum` (oracle en tests
  uniquement, jamais en prod). Incrémentale : format d'abord, clés pays par
  pays, dégradation gracieuse si le temps manque.

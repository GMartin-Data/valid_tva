# valid_tva — Validation de numéros de TVA intracommunautaire

![CI](https://github.com/GMartin-Data/valid_tva/actions/workflows/ci.yml/badge.svg)

Qualification d'un référentiel de 10 000 numéros de TVA (Meridian Distribution) :
**valide / invalide / indéterminé**, via normalisation, validation structurelle,
vérification VIES, et une API REST consultée avant chaque facturation hors taxe.

> Brief pédagogique — formation Data Engineer, 2026. Auteur : Greg Martin.

## Technologies

| Outil | Rôle | Pourquoi |
|---|---|---|
| Python 3.13 + [uv](https://docs.astral.sh/uv/) | pipeline & outillage | reproductibilité (lockfile), rapidité |
| PostgreSQL 16 (Docker) | référentiel + verdicts | fourni par le kit ; schéma SQL versionné |
| httpx | client VIES (API REST) | timeouts explicites, client moderne |
| FastAPI | API de vérification | OpenAPI générée automatiquement |
| ruff, pytest | qualité | lint + tests ciblés |

## Lancement depuis zéro

```bash
# 1. Prérequis : Docker + uv installés
git clone <repo> && cd valid_tva

# 2. Base PostgreSQL (port 5435 ; identifiants par défaut meridian/meridian/tva,
#    surchargeables via variables d'environnement POSTGRES_*)
docker compose up -d --wait

# 3. Dépendances Python
uv sync

# 4. Chargement du référentiel (idempotent : rejouable sans doublon,
#    et sans écraser les verdicts VIES déjà acquis)
uv run python -m valid_tva.load

# Répartition des verdicts structurels par motif
docker exec -i meridian_tva_db psql -U meridian -d tva -f - < sql/motive_distribution.sql

# 5. Campagne de vérification VIES (rejouable : les indéterminés et les
#    verdicts périmés sont repris à chaque passage ; --limit = mode échantillon)
uv run python -m valid_tva.campaign --limit 200

# Rapport de réconciliation : entonnoir et doublons, motifs de rejet, état
# de campagne, qualification des 10 000 lignes (verdict × origine,
# vocabulaire de l'API)
docker exec -i meridian_tva_db psql -U meridian -d tva -f - < sql/verdict_reconciliation.sql

# 6. API de vérification
uv run uvicorn --factory valid_tva.api:app
```

Tout-en-un — la pile complète (base attendue saine, dépendances, chargement,
API) en une commande :

```bash
docker compose up -d --wait && uv sync && uv run python -m valid_tva.load && uv run uvicorn --factory valid_tva.api:app
```

Les variables `POSTGRES_*` (host, port, user, password, db) surchargent les
défauts si besoin — aucun fichier d'environnement n'est requis.

## API

`GET /vat/{numero}` accepte un numéro même bruité (`fi 2660-63.69`), avec
`?country=XX` pour reconstruire un préfixe pays manquant. Tout verdict est un
`200` — « invalide » est une réponse, pas une erreur. Documentation interactive
sur `/docs` (OpenAPI sur `/openapi.json`).

```bash
curl http://127.0.0.1:8000/vat/BE0415621046
```

```json
{
    "input": "BE0415621046",
    "vat_number": "BE0415621046",
    "verdict": "valid",
    "origin": "vies",
    "motive": null,
    "checked_at": "2026-09-08T10:06:52.095000Z",
    "stale": false,
    "name": "NV PLUTO",
    "address": "Merellaan 46\n9400 Ninove"
}
```

- `verdict` : `valid` / `invalid` / `unknown` (l'indéterminé du brief).
- `origin` : `structural` (rejeté avant VIES, `motive` renseigné), `vies`
  (verdict observé en campagne), `never_checked` (aucune tentative encore).
- Fraîcheur : `checked_at` (horodatage VIES) + `stale: true` au-delà de
  7 jours — le verdict est toujours servi, jamais retenu (décision D5) ;
  l'API ne contacte jamais VIES elle-même.

## Structure

```
data/          référentiel source (CSV, 10 000 lignes)
exploration/   scripts one-shot d'exploration (traçabilité, hors production)
src/valid_tva/ code du pipeline et de l'API
sql/           schéma PostgreSQL et rapports SQL versionnés
docs/          journal de bord, note d'architecture
```

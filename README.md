# valid_tva — Validation de numéros de TVA intracommunautaire

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
docker compose up -d

# 3. Dépendances Python
uv sync
```

*(sections à venir : chargement du référentiel, campagne VIES, API, rapport)*

## Structure

```
data/          référentiel source (CSV, 10 000 lignes)
exploration/   scripts one-shot d'exploration (traçabilité, hors production)
src/valid_tva/ code du pipeline et de l'API
sql/           schéma PostgreSQL versionné
docs/          journal de bord, note d'architecture
```

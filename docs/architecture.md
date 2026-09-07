# Note d'architecture — valid_tva

> Livrable final : 1 page. Sections chiffrées complétées au fil du projet.

## Décisions structurantes

- **D1 — Numéros sans préfixe pays** (532 lignes) : reconstruction depuis
  `pays_declare` (champ fiable : 100 % renseigné, 0 discordance observée),
  déduction tracée (`prefix_added`).
- **D2 — Doublon** : clé canonique = (pays + numéro normalisé) après
  reconstruction. Aucune ligne supprimée ; le verdict s'attache au numéro
  distinct.
- **D3 — GB/UK** (208 lignes) : invalide structurel, motif `NON_EU_COUNTRY` —
  VIES répond `INVALID_INPUT` (question hors périmètre), il n'invalide pas ;
  la question métier (autoliquidation intra-UE) est tranchée définitivement.
- **D4 — Validation structurelle** : tamis emboîtés (vide → pays → format →
  clé de contrôle), motif du premier tamis qui arrête. Clés implémentées à la
  main, vérifiées contre `python-stdnum` (oracle de tests, ~200 mutations,
  accord complet — jamais utilisé en production).

## Réduction des appels VIES

*(chiffres définitifs après chargement)* — Extrapolation naïve mesurée :
10 000 appels séquentiels = 1,1 h à 5,1 h selon la latence observée
(min 33 ms, médiane 0,39 s, moyenne 1,85 s, max 8,6 s — latence dépendante
de l'État membre interrogé).

## Durée de validité d'un verdict et traitement des indéterminés

*(à décider en J2, avec la campagne)*

## Références

### Cadre officiel (UE)

- VIES on-the-Web (service et FAQ) — Commission européenne :
  <https://ec.europa.eu/taxation_customs/vies/>
- API REST VIES (endpoint `check-vat-number`, sans inscription) :
  <https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number>
- « VAT identification numbers » — Commission européenne (chaque État membre
  définit son propre format ; base légale art. 214 de la directive TVA) :
  <https://taxation-customs.ec.europa.eu/taxation/vat/vat-directive/vat-identification-numbers_en>
- Directive 2006/112/CE (directive TVA), art. 214-216 — EUR-Lex :
  <https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:32006L0112>

### Spécifications des clés de contrôle (nationales)

Les algorithmes de clé ne sont PAS publiés par la Commission : chaque
administration nationale définit et documente le sien (ex. FR : clé de la
TVA intracommunautaire dérivée du SIREN, INSEE / impots.gouv.fr ; BE :
numéro d'entreprise BCE, SPF Économie ; NL : btw-id, Belastingdienst,
double régime depuis 2020). Familles mathématiques : modulo auto-référent
(BE 97, LU 89, FR 97), Luhn (IT, SE), somme pondérée mod 11 (DK, FI, NL,
PL, PT) — normes de la famille ISO 7064 pour NL post-2020.

### Référence technique croisée (oracle de tests)

- `python-stdnum` — implémentation de référence, chaque module citant sa
  source nationale : <https://arthurdejong.org/python-stdnum/>
  Utilisée exclusivement comme oracle dans `tests/test_oracle.py`.

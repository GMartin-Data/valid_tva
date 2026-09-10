# Note d'architecture — valid_tva

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

Approche naïve mesurée : 10 000 appels séquentiels = 1,1 h à 5,1 h selon la
latence observée (min 33 ms, médiane 0,39 s, moyenne 1,85 s, max 8,6 s —
latence dépendante de l'État membre interrogé).

Entonnoir structurel (mesuré sur le référentiel complet) :

| Étape | Lignes écartées | Motif |
|---|---|---|
| Vide (y c. déguisé) | 261 | `MISSING` |
| Pays inexistant (ZZ/QQ/XX) | 311 | `UNKNOWN_COUNTRY` |
| GB/UK post-Brexit | 208 | `NON_EU_COUNTRY` |
| Format impossible | 1 264 | `BAD_FORMAT` |
| Clé de contrôle fausse | 1 332 | `BAD_CHECK_DIGIT` |
| Doublons parmi les candidats | 313 | dédup (pays + numéro normalisé) |

**10 000 lignes → 6 311 appels VIES (−36,9 %, soit 3 689 appels évités).**
Le tamis clé à lui seul économise 1 332 appels (~40 min à la latence
moyenne) — il justifie l'implémentation des algorithmes nationaux (D4).
Les 532 numéros à préfixe reconstruit (D1) sont tous devenus candidats.

## Campagne VIES : reprise par conception, retry au bon étage

- **Verdict commité par numéro** : une interruption (crash, coupure) ne perd
  rien — relancer la commande reprend exactement où le run s'est arrêté.
- **Sélection entrelacée par pays** : la saturation VIES est par État membre
  (`MS_MAX_CONCURRENT_REQ`, renvoyé sous HTTP 200). Un parcours alphabétique
  concentre les appels sur un même État et s'auto-sature : 56,5 %
  d'indéterminés mesurés, ramenés à 12,5 % par entrelacement.
- **Pas de retry in-run** (pas de `tenacity`) : une erreur de capacité ne se
  résout pas à l'échelle de la seconde — réessayer immédiatement entretient
  la saturation même. Le retry vit un étage au-dessus : l'indéterminé reste
  éligible en base et le passage suivant de la campagne le reprend.
- **Fenêtre de tir mesurée, critère fixé avant les données** : sonde horaire
  (~44 h, FR/BE/DK) ; fenêtre contiguë ≥ 3 h à saturation minimale, départage
  latence médiane. Verdict de la sonde : l'hypothèse « nuit creuse » est
  réfutée (BE saturé en continu, 83 % d'échecs à minuit) ; la fenêtre en tête
  est 09h–12h — le run complet y a été lancé.

## D5 — Fraîcheur exposée, jamais de péremption

L'API sert toujours le verdict stocké accompagné de son âge — jamais de
re-appel VIES à la requête (latence jusqu'à 8,6 s et saturation du service :
le référentiel est fait pour être consulté, pas re-vérifié en ligne).
`stale: true` au-delà de 7 jours — paramètre assumé arbitraire qui documente
la cadence de re-campagne hebdomadaire. Ne concerne que les verdicts VIES :
le verdict structurel est déterministe (pas de TTL), et l'indéterminé n'est
pas un verdict mais une re-éligibilité (retry, pas TTL).

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

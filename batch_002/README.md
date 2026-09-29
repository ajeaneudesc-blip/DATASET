# Corrigés du lot batch_002

Ce dossier contient les **réponses attendues** des 20 tâches de `05_OUTPUTS/batch_002`
(branche principale du dépôt). Un modèle qui y aurait accès (entraînement, recherche web)
connaîtrait les solutions : ne pas fusionner cette branche avec les énoncés, et tenir compte
de son existence si le lot sert à évaluer des modèles.

## Contenu

| Élément | Rôle | Contient la solution ? |
|---|---|---|
| `SCENARIOS.md` | Scénario donné aux rédacteurs pour T003 à T020 : mécanisme caché, ordres de grandeur, pistes trompeuses | Oui |
| `relectures/B002-T0xx.md` | Rapport de relecture de chaque tâche (20) : chiffres vérifiés, fuites corrigées, pourquoi la cause reste découvrable | Oui (le plus fiable) |
| `sources_yaml/` | Sources YAML des 20 tâches (version finale), d'où sont générés les JSON | Non (identiques aux énoncés) |
| `processus/` | Guide de rédaction, guide de relecture et `build.py` (YAML → JSON), réutilisables pour les prochains lots | Non |
| `verification/` | Scripts de calcul des rédacteurs et relecteurs (encodage/décodage du bloc de T005, hachage des shards de T004, simulation de T019) | Partiellement |

## À savoir pour noter une réponse

- **Les rapports de relecture font foi**, pas les scénarios. Les rédacteurs ont assumé des écarts
  par rapport au scénario (chiffres recalculés, mécanismes ajoutés), puis les relecteurs ont encore
  corrigé la tâche. Chaque rapport décrit l'état final.
- **T001 et T002** n'ont pas de scénario écrit : leur mécanisme est décrit dans
  `relectures/B002-T001.md` et `relectures/B002-T002.md`.
- Ces documents décrivent la cause et les indices, pas une solution de référence complète
  (architecture, code, plan de déploiement). Plusieurs solutions sont acceptables pour chaque tâche ;
  une grille de notation par tâche reste à écrire si le lot sert d'évaluation.

## Régénérer un JSON après modification d'une source

`processus/build.py` attend les YAML dans le même dossier que lui et le lot dans
`/home/user/DATASET/05_OUTPUTS/batch_002` : adapter les deux chemins en tête du script
(`HERE`, `BATCH`) avant usage, puis `python3 build.py B002-T007`.

# Guide de rédaction — lot batch_002

Projet : `/home/user/DATASET` (dataset d'énoncés techniques très difficiles, en français,
60 % Problem Solving / 40 % Machine Learning, niveau Distinguished / Principal / Research Engineer).
Lire avant d'écrire :
- `01_PROMPTS/MASTER_SUPERPROMPT.md`, `06_DOCS/QUALITY_GATE.md`, `06_DOCS/FOCUS_GUIDE.md`, `06_DOCS/DATA_SCHEMA.md`
- les deux tâches de référence déjà rédigées, **à imiter pour le ton, la densité et la forme** :
  `SCRATCH/b002/B002-T001.yaml` et `SCRATCH/b002/B002-T002.yaml`
  (rendu JSON : `05_OUTPUTS/batch_002/tasks/B002-T001.json`, `B002-T002.json`)
- ta fiche dans `05_OUTPUTS/batch_002/generated_cards.jsonl` et le scénario prévu dans
  `SCRATCH/b002/SCENARIOS.md`

`SCRATCH` = `/tmp/claude-0/-home-user-DATASET/cfe3fe85-3a5c-52d8-91c0-84ca72a1b82e/scratchpad`

## Production

1. Écrire `SCRATCH/b002/<task_id>.yaml` (même structure que B002-T001.yaml) :
   `title`, `constraints` (mapping **label exact de la fiche → détail chiffré**, dans l'ordre de la fiche),
   `context`, `existing_architecture`, `problem`, `evidence` (liste), `objectives`, `deliverables`,
   `success_criteria`, `metadata` (`requires_code`, `requires_architecture`).
   Les axes (domaine, langage, charge, incident…) viennent de la fiche : ne pas les recopier.
2. Construire : `cd SCRATCH/b002 && python3 build.py <task_id>` (seulement tes tâches).
3. Valider : `cd /home/user/DATASET && python3 07_SCRIPTS/validate_tasks.py --kind task --single 05_OUTPUTS/batch_002/tasks/<task_id>.json`
   → 0 erreur, 0 avertissement attendu.
4. Ne rien committer, ne modifier aucun autre fichier que tes propres `<task_id>.yaml` / `.json`.

Pièges YAML : utiliser des blocs `|-` pour les textes et toute preuve multi-ligne ; mettre entre
guillemets doubles les éléments de liste d'une seule ligne (un « : » non protégé crée un mapping).
Utiliser les guillemets français « » à l'intérieur des chaînes entre guillemets doubles.

## Exigences de fond (Quality Gate)

- **Réaliste et plausible** : organisation fictive (nom inventé, jamais une entreprise réelle),
  produit, équipe, historique de changements daté, dépendances. Dates cohérentes autour de
  septembre–octobre 2026.
- **Chiffres cohérents** entre eux et avec le niveau de charge de la fiche
  (prototype ≈ 10 req/s / 10 Go ; small-production ≈ 500 req/s / 500 Go ; production ≈ 10 k req/s / 10 To ;
  high-scale ≈ 100 k req/s / 100 To ; extreme-scale ≈ 1 M+ req/s / 1 Po+). Refaire les calculs
  (débits × durées, pourcentages, tailles mémoire, coûts) avant de les écrire.
- **La difficulté vient des interactions** entre composants, données, contraintes et incident,
  pas de la longueur. Viser : context 900–1 600 caractères, existing_architecture 600–1 200,
  problem 400–900, 4 à 6 preuves dont au moins 2 techniques (logs, métriques, code, config, schéma,
  données), 3–4 objectifs, 4–6 livrables, 4–6 critères de réussite **mesurables**.
- **Preuves** : de vrais extraits (code crédible dans le langage imposé, logs horodatés, tableaux de
  métriques, configurations). Elles doivent rendre l'investigation possible (indices réels) et
  contenir au moins une piste trompeuse plausible. Les blocs de code sont dans des fences ```lang.
- **Ne jamais révéler la cause racine ni la solution** : pas de phrase qui l'énonce, pas de
  commentaire de code qui la désigne. Éviter les tournures « la cause racine est », « la solution
  consiste » (détectées par le validateur). Le mécanisme caché décrit dans SCENARIOS.md sert à
  rendre les preuves cohérentes, il ne doit pas apparaître tel quel.
- **Inconnues identifiables** : laisser 1 à 3 informations manquantes réalistes, que le candidat
  doit savoir nommer (et, si utile, le dire explicitement dans une preuve : « non disponible »).
- **Plusieurs solutions raisonnables** et un vrai compromis (coût, latence, risque, délai…).
- **Le langage imposé influence réellement la solution** (modèle mémoire, GC, runtime, outillage,
  bibliothèque standard, contraintes de plateforme).
- **Sécurité** : défensif uniquement (audit, détection, remédiation) ; aucune procédure offensive.
- **Raisonnement** : ne jamais demander de chaîne de pensée ; demander hypothèses, décisions,
  preuves, invariants, tests, mesures, justifications.
- **Diversité** : ne pas réutiliser les noms d'entreprise, les formulations ni la structure de
  phrases des autres tâches (le validateur signale les textes trop proches).

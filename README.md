# Extreme AI Dataset Lab

Projet prêt à utiliser avec Claude Desktop pour générer des problèmes techniques
réalistes et très difficiles, centré sur le **Problem Solving** et le **Machine Learning**, avec une répartition cible d'environ 60/40 et des variations contrôlées de :

- domaine Problem Solving / ML ;
- langage ;
- niveau de charge ;
- contraintes ;
- type d'incident ;
- profondeur de raisonnement ;
- mode de tâche.

Le projet est conçu pour produire des **énoncés de tâches et des métadonnées**.
Il ne demande pas de révéler une chaîne de pensée interne : les réponses attendues
doivent fournir des hypothèses, décisions, preuves, tests et justifications techniques.

## Utilisation

1. Ouvre ce dossier dans Claude Desktop / Claude Code.
2. Lis `01_PROMPTS/MASTER_SUPERPROMPT.md`.
3. Utilise `04_SEEDS/seed_tasks.jsonl` comme base (35 seeds : 21 Problem Solving / 14 ML).
4. Demande à Claude de générer des variantes en changeant simplement :
   - domaine ;
   - langage ;
   - charge ;
   - contraintes ;
   - incident.
5. Les prompts générés par le script apparaissent dans `05_OUTPUTS/`.

## Générateur local

Les scripts Python ne contactent aucun service externe. Ils fabriquent des fiches
à partir des catalogues du projet.

### Windows

```powershell
python 07_SCRIPTS/generate_prompt.py --count 20
```

ou :

```powershell
py 07_SCRIPTS/generate_prompt.py --count 20
```

Le résultat sera enregistré dans :

- `05_OUTPUTS/generated_prompts.md` : fiches lisibles, à copier dans Claude ;
- `05_OUTPUTS/generated_cards.jsonl` : les mêmes fiches en JSON.

Garanties du générateur :

- répartition exacte Problem Solving / ML (`--ps-ratio 0.6` : 12/8 sur 20) ;
- chaque axe est tiré parmi les valeurs les moins utilisées du lot (couverture maximale) ;
- chaque fiche a un type de problème (`problem_solving_types.json` ou `ml_types.json`) ;
- combinaisons incohérentes exclues via `02_TAXONOMY/compatibility.json` ;
- chaque fiche diffère d'au moins 4 axes de toutes les précédentes (`--min-diff`).

Options utiles : `--seed`, `--id-prefix B002-T`, `--out-dir 05_OUTPUTS/batch_002`.

### Validation et assemblage

```powershell
python 07_SCRIPTS/validate_tasks.py --kind seed 04_SEEDS/seed_tasks.jsonl
python 07_SCRIPTS/validate_tasks.py --kind task 05_OUTPUTS/batch_001/tasks
python 07_SCRIPTS/assemble_batch.py 05_OUTPUTS/batch_001
```

Le validateur contrôle le schéma, les valeurs des catalogues, la cohérence des
combinaisons, la répartition 60/40, la diversité entre tâches, les doublons et
signale les fuites de solution probables. L'assembleur produit `tasks.jsonl` et
`tasks.md` pour un lot.

## Lots générés

- `05_OUTPUTS/batch_001/` : 20 tâches (12 Problem Solving / 8 Machine Learning),
  relues par trois relecteurs indépendants (réalisme chiffré, Quality Gate,
  solveur adversarial) puis par une critique de lot.

## Structure

- `00_CONFIG/` : paramètres du projet
- `01_PROMPTS/` : superprompts prêts à copier
- `02_TAXONOMY/` : catalogues de variation (`domains.json` est séparé par piste,
  `compatibility.json` contient les règles de cohérence)
- `03_TEMPLATES/` : structures d'énoncés
- `04_SEEDS/` : scénarios initiaux
- `05_OUTPUTS/` : sorties générées
- `06_DOCS/` : règles de qualité et schéma
- `07_SCRIPTS/` : scripts locaux (`generate_prompt.py`, `validate_tasks.py`,
  `assemble_batch.py`, `taxonomy.py` partagé)

## Règle de qualité

La difficulté doit venir des interactions réelles entre composants et contraintes,
pas d'un texte inutilement long. Les problèmes doivent être plausibles,
évaluables et suffisamment complets pour permettre une vraie analyse technique.

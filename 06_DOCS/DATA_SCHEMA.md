# DATA SCHEMA

Chaque tâche doit pouvoir être représentée en JSON avec (voir `03_TEMPLATES/task_schema.json`) :

task_id
track                 problem_solving | machine_learning
title
domain                02_TAXONOMY/domains.json (doit appartenir à la piste `track`)
subtype               02_TAXONOMY/problem_solving_types.json ou ml_types.json selon la piste
language              02_TAXONOMY/languages.json
load_level            nom d'un niveau de 02_TAXONOMY/load_levels.json
architecture_style    02_TAXONOMY/architecture_styles.json
incident_type         02_TAXONOMY/incidents.json
failure_mode          02_TAXONOMY/failure_modes.json
task_mode             02_TAXONOMY/task_modes.json
constraints[]         « label — détail chiffré », label issu de 02_TAXONOMY/constraints.json (3 minimum)
context
existing_architecture
problem
evidence[]            3 minimum (logs, métriques, traces, code, configs, schémas, données)
objectives[]          2 minimum
deliverables[]        3 minimum
success_criteria[]    3 minimum
metadata{
  difficulty,         "extreme"
  requires_code,
  requires_architecture,
  requires_tradeoffs,
  requires_multistep_reasoning,
  solution_included   toujours false
}

Les combinaisons incohérentes (ex. incident « dérive de modèle ML » sur une tâche
Problem Solving, Bash pour du deep learning) sont définies dans
`02_TAXONOMY/compatibility.json`.

Vérification automatique : `python 07_SCRIPTS/validate_tasks.py --kind task <fichier|dossier>`.

# WORKFLOW CLAUDE DESKTOP

1. Ouvrir le dossier du projet.
2. Donner `MASTER_SUPERPROMPT.md` comme règle principale.
3. Lui demander de lire `02_TAXONOMY/`.
4. Générer les fiches d'un lot :
   `python 07_SCRIPTS/generate_prompt.py --count 20 --id-prefix B002-T --out-dir 05_OUTPUTS/batch_002`
   (ou partir de `04_SEEDS/`).
5. Rédiger une tâche par fiche dans `05_OUTPUTS/<lot>/tasks/<task_id>.json`, par petits lots.
6. Valider : `python 07_SCRIPTS/validate_tasks.py --kind task 05_OUTPUTS/<lot>/tasks`.
7. Relire chaque tâche avec `QUALITY_GATE.md` (réalisme, Quality Gate, tentative de résolution).
8. Écarter les doublons.
9. Assembler : `python 07_SCRIPTS/assemble_batch.py 05_OUTPUTS/<lot>` → `tasks.jsonl` + `tasks.md`.
10. Conserver les métadonnées.
11. Ne pas mélanger train et test si le projet sert ensuite à un benchmark.
12. Conserver la provenance et la licence des sources utilisées.

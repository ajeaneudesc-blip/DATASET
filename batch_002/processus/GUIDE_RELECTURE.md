# Guide de relecture — lot batch_002

Tu relis des tâches **que tu n'as pas écrites**. Objectif : qu'une tâche sorte ACCEPTÉE au sens de
`/home/user/DATASET/06_DOCS/QUALITY_GATE.md`, ou soit corrigée jusqu'à l'être.
Lire d'abord : `GUIDE_REDACTION.md` (même dossier), `QUALITY_GATE.md`, `FOCUS_GUIDE.md`, et le
scénario de chaque tâche dans `SCENARIOS.md` (T001 et T002 n'y figurent pas : leur mécanisme se
déduit de leurs preuves).

`SCRATCH` = `/tmp/claude-0/-home-user-DATASET/cfe3fe85-3a5c-52d8-91c0-84ca72a1b82e/scratchpad`

## Trois passes par tâche

1. **Réalisme chiffré** — refaire les calculs : débits × durées, volumes, pourcentages,
   mémoire, coûts, latences, dates et heures, offsets, cohérence avec le niveau de charge de la
   fiche. Vérifier que le code est crédible et compile « à l'œil » dans le langage imposé, que les
   logs et configs sont plausibles, que l'architecture tient debout.
2. **Quality Gate** — pas générique ; difficulté issue des interactions (pas de la longueur) ;
   contexte suffisant pour démarrer ; inconnues identifiables ; plusieurs solutions raisonnables ;
   critères de réussite vérifiables et atteignables (pas contradictoires entre eux ni avec les
   contraintes) ; le langage pèse réellement ; aucune chaîne de pensée demandée ; sécurité
   défensive uniquement.
3. **Solveur adversarial** — tente de résoudre la tâche en 10 minutes comme un très bon candidat.
   - Si la cause racine ou la solution se lit directement (phrase explicite, commentaire de code
     qui désigne le bug, preuve qui conclut à la place du candidat) → **fuite** : reformuler pour
     que l'indice reste présent mais demande un raisonnement.
   - Si la tâche est impossible à résoudre faute d'indice (mécanisme caché sans aucune trace
     dans les preuves) → **sous-spécifiée** : ajouter l'indice manquant.
   - Si une seule réponse artificielle existe → ouvrir l'espace de solutions.

## Corrections

- Corrige directement dans `SCRATCH/b002/<task_id>.yaml` (jamais le JSON à la main), puis
  `cd SCRATCH/b002 && python3 build.py <task_id>` et
  `cd /home/user/DATASET && python3 07_SCRIPTS/validate_tasks.py --kind task --single 05_OUTPUTS/batch_002/tasks/<task_id>.json`
  (0 erreur, 0 avertissement).
- Corrections ciblées : garder la voix et la structure du rédacteur, ne pas réécrire pour le
  plaisir. Ne pas changer les axes de la fiche ni les labels de contraintes.
- Ne modifie que les tâches qui te sont attribuées. Aucun commit git.

## Rapport (à écrire dans `SCRATCH/b002/review/<task_id>.md`, puis résumé final)

Pour chaque tâche, en français, sans révéler la cause racine ni la solution :
```
# <task_id> — <titre>
Verdict : ACCEPTÉE | ACCEPTÉE APRÈS CORRECTIONS | À REJETER (motif)
Réalisme chiffré : <constats et corrections>
Quality Gate : <constats et corrections>
Solveur adversarial : <difficulté perçue, fuites ou manques corrigés>
```
Le résumé final de ton travail (réponse à l'orchestrateur) liste pour chaque tâche le verdict et
les corrections faites en une ou deux lignes.

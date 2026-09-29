# Relecture du lot batch_002

20 tâches : 12 Problem Solving / 8 Machine Learning. Énoncés uniquement : ce document ne
contient ni cause racine ni solution.

## Processus

1. **Fiches** : `generate_prompt.py --count 20 --id-prefix B002-T --out-dir 05_OUTPUTS/batch_002 --against 05_OUTPUTS`
   (graine par défaut 20260928), avec la taxonomie enrichie des incidents et failure modes ML
   (`generated_cards.jsonl`, `generated_prompts.md`).
2. **Rédaction** : B002-T001 et B002-T002 servent de tâches de référence. T003 à T020 ont été
   réparties entre six rédacteurs (3 tâches chacun), qui disposaient d'un guide de rédaction
   commun et d'un scénario par tâche (mécanisme caché, ordres de grandeur, pistes trompeuses).
   Chaque rédacteur a validé ses tâches (`validate_tasks.py --single`) et recalculé ses chiffres.
3. **Relecture indépendante** : sept relecteurs, aucun n'a relu ses propres tâches. Chaque tâche
   est passée par trois passes, avec corrections directes dans les sources :
   - **réalisme chiffré** : débits, volumes, mémoire, coûts, dates, loi de Little, code crédible
     dans le langage imposé ;
   - **Quality Gate** (`06_DOCS/QUALITY_GATE.md`) ;
   - **solveur adversarial** : tentative de résolution rapide pour repérer les fuites de solution
     et les indices manquants.
4. **Critique de lot** : validation complète contre les autres lots, conformité des axes aux
   fiches, similarité textuelle, couverture (section ci-dessous).

## Verdicts

Toutes les tâches sont **ACCEPTÉES APRÈS CORRECTIONS**. Le validateur donne 0 erreur et
0 avertissement, tâche par tâche comme sur le lot entier.

| Tâche | Piste | Langage | Nature des corrections de relecture |
|---|---|---|---|
| B002-T001 | ML | Go | Tableau de dépenses rendu cohérent ; une preuve, un livrable et un critère trop directs reformulés |
| B002-T002 | PS | C | Offsets et proportions recalculés ; énoncé du problème et livrable de code rendus neutres |
| B002-T003 | PS | JavaScript | Livrable et critères reformulés (pistes trompeuses à examiner, mention trop explicite retirée) |
| B002-T004 | ML | Kotlin | Exemples recalculés avec la graine de hachage du code ; volumes, échantillonnage et horodatages recalés |
| B002-T005 | PS | Rust | Vidage hexadécimal décodé indépendamment (exact) ; code compilable sur les deux architectures ; formulations neutres |
| B002-T006 | ML | Swift | Taille d'extraction corrigée ; objectif reformulé ; critère de robustesse ciblé |
| B002-T007 | PS | Java | Métriques de file et offsets rendus cohérents ; livrable qui tranchait une piste reformulé ; critère borné |
| B002-T008 | PS | TypeScript | Horodatages et CPU recalés ; commentaire de code trop explicite remplacé |
| B002-T009 | ML | Python | Vérifiée strictement défensive ; chronologie d'alerte et positions de blocs rendues cohérentes |
| B002-T010 | ML | C++ | Taux de hit du cache compatible avec le p99 ; dump gdb et code alignés |
| B002-T011 | ML | Python | Livrable qui désignait la correction reformulé ; critère de puissance précisé |
| B002-T012 | PS | SQL | Trafic réseau recalculé (la piste trompeuse était trop favorisée) ; coûts et dates recalés |
| B002-T013 | PS | C# | Profil de trafic compatible avec le CPU observé ; tableau d'incident conforme à la loi de Little ; distinction avec T014 |
| B002-T014 | PS | C# | Horaires cohérents avec les snapshots ; phrase qui nommait le mécanisme retirée |
| B002-T015 | ML | Python | Volume d'audio et critères statistiques (taille d'échantillon, calibration) corrigés ; phrase trop directe retirée |
| B002-T016 | PS | Bash | Heure de retour en service rendue cohérente |
| B002-T017 | PS | JavaScript | Chronologie des tentatives et autoscaling corrigés ; trace trop explicite retirée ; espace de solutions rouvert |
| B002-T018 | PS | Kotlin | Ligne de journal techniquement impossible remplacée |
| B002-T019 | PS | Rust | Nombre de candidats au p50 rendu compatible avec la latence (vérifié par simulation) |
| B002-T020 | ML | C++ | Chiffres qui livraient la conclusion remplacés par des données brutes ; taille d'index et de bucket recalculées |

## Critique de lot

- **Conformité** : les axes et les labels de contraintes de chaque tâche sont identiques à ceux
  de sa fiche ; répartition 12/8 exacte.
- **Diversité** : 20 incidents et 20 types de problème distincts, 18 domaines, 13 langages sur 13,
  11 architectures sur 11, 5 niveaux de charge, 15 failure modes, 13 modes de tâche,
  18 contraintes sur 18. Chaque paire de tâches diffère sur au moins 4 axes.
- **Reformulations** : similarité textuelle maximale entre deux tâches de 0,004 (seuil d'alerte 0,25).
- **Code** : chaque tâche contient au moins un extrait de code dans son langage imposé.
- **Points d'attention** :
  - la structure est homogène (5 à 6 preuves, 3 à 4 objectifs, 5 livrables, 5 critères), héritée des
    tâches de référence ; un lot futur peut varier davantage la forme ;
  - C#, JavaScript, Kotlin, Rust et C++ apparaissent deux fois chacun, Python trois fois ;
  - la difficulté n'a pas été mesurée empiriquement contre des modèles, et les chiffres ont été vérifiés
    par les relecteurs, pas par des experts de chaque domaine.
- **Non versionné** : les scénarios (mécanismes cachés) et les rapports détaillés des relecteurs, qui
  constituent de fait des corrigés. Ils ne doivent pas être publiés avec les énoncés si le lot sert
  d'évaluation.

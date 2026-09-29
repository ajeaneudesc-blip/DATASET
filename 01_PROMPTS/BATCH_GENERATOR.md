# BATCH GENERATOR PROMPT

Génère un lot de tâches en changeant à chaque fois :
- domaine ;
- langage ;
- charge ;
- contraintes ;
- incident ;
- architecture ;
- failure mode ;
- mode de tâche.

Interdiction de produire de simples reformulations.

Pour chaque nouvelle tâche, modifie au moins quatre dimensions par rapport aux tâches
précédentes.

Toutes les tâches doivent respecter le MASTER SUPERPROMPT.

Retourne uniquement les énoncés + métadonnées, sans solution.


## Répartition recommandée

Sur 20 tâches :
- 12 tâches Problem Solving ;
- 8 tâches Machine Learning.

Dans les tâches Problem Solving, varie :
- optimisation ;
- diagnostic ;
- planification ;
- raisonnement sous contraintes ;
- contre-exemples ;
- algorithmes ;
- systèmes de décision.

Dans les tâches ML, varie :
- données ;
- entraînement ;
- architecture ;
- évaluation ;
- robustesse ;
- production ;
- retrieval ;
- multimodal ;
- forecasting ;
- recommandation ;
- RL.

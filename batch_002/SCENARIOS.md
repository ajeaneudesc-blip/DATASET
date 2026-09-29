# Scénarios prévus — batch_002 (T003 à T020)

Chaque scénario respecte exactement les axes de la fiche. « Mécanisme caché » = ce qui rend les
preuves cohérentes : **ne jamais l'écrire tel quel dans la tâche**. Les chiffres indiqués sont des
ordres de grandeur à vérifier et affiner ; le rédacteur peut enrichir tant qu'il reste cohérent.

---
## B002-T003 — PS · problem solving algorithmique · choix entre plusieurs stratégies · JavaScript · high-scale · serverless · régression après déploiement · version mixte pendant migration · implémentation multi-fichiers
Contraintes : faible consommation mémoire, déploiement progressif, rollback obligatoire.

Évaluation de feature flags / affectation d'expériences A/B dans des fonctions edge serverless en
JavaScript (isolates V8, 128 Mo par isolate, ~10 ms CPU par requête), ~100 k req/s, 312 PoPs.
Migration de l'évaluateur v1 (parcours linéaire des règles de ciblage, première règle qui matche)
vers v2 (règles « compilées » en index de bitsets par attribut/valeur pour aller plus vite).
Déploiement progressif par PoP (1 %, 10 %, 50 %, 100 % sur 5 jours) → v1 et v2 coexistent.
Symptômes : 3 expériences en Sample Ratio Mismatch (p < 1e-6), des utilisateurs voient plusieurs
variantes ; mémoire des isolates v2 proche de 118 Mo pour le plus gros tenant (14 200 règles,
2,1 M valeurs d'attributs distinctes) → évictions, cold starts +40 ms.
Mécanisme caché : (1) le compilateur v2 trie les règles par spécificité (nombre de conditions)
pour court-circuiter plus tôt, ce qui change la sémantique « première règle qui matche » pour les
utilisateurs qui satisfont plusieurs règles qui se chevauchent ; (2) un utilisateur qui alterne
entre PoPs v1 et v2 est réaffecté ; (3) l'index en bitsets explose en mémoire sur les attributs à
forte cardinalité. Preuves : tableau SRM, analyse des utilisateurs « flippés » (forte proportion
matchant ≥ 2 règles), métriques mémoire/évictions par version, extrait de `compiler/compile.js` v2
(le tri, avec un commentaire de performance neutre) et de l'évaluateur v1.
Attendu : comparer ≥ 3 stratégies (scan linéaire optimisé, index bitset avec priorité préservée,
diagramme de décision / trie, compilation paresseuse par tenant…) en temps/mémoire ; code
multi-fichiers (compilateur, évaluateur, bucketing, shim de migration) + tests d'équivalence v1/v2 ;
plan de migration et de rollback sans réaffecter un utilisateur déjà exposé.

---
## B002-T004 — ML · MLOps et training pipelines · ranking · Kotlin · production · multi-région actif/passif · hotspot sur une partition · perte d'un worker GPU en cours d'entraînement · refactorisation legacy
Contraintes : auditabilité complète, réseau partiellement instable, compatibilité API stricte.

Pipeline quotidien de learning-to-rank (ranker neuronal listwise) d'une marketplace e-commerce,
orchestré par un monolithe Kotlin de 9 ans (`ltr-pipeline`) : export des logs de clics → shards
d'entraînement partitionnés par hash de la requête normalisée (64 shards, les groupes listwise
d'une même requête doivent rester ensemble) → entraînement distribué 8 workers GPU → évaluation
NDCG@10 → publication d'un modèle avec piste d'audit (obligation réglementaire de transparence du
classement : lien modèle ↔ données ↔ config ↔ rapport d'évaluation, conservé 5 ans). Région active
entraîne, région passive reçoit les artefacts (9,2 Go) sur un lien instable (≈ 1 upload sur 6 échoue).
API publique `POST /v1/pipelines/{id}/runs` utilisée par 3 équipes (schéma de réponse figé).
Incident : SLA de 6 h manqué 4 jours sur 10 ; shard 17 de 41,8 Go vs médiane 1,1 Go ; la perte
d'un worker (préemption) relance l'époque entière (ex. worker-5 perdu au pas 18 400/24 000, run de 7 h 52).
Mécanisme caché : la normalisation des requêtes (minuscules + suppression des accents et de la
ponctuation) produit la chaîne vide pour les pages de navigation sans requête et les requêtes
uniquement emoji/ponctuation → toutes hachées dans le même shard (61 % des lignes du shard 17 ont
normalized_query = ""). Piste trompeuse : on accuse une requête populaire (« iphone »).
Arbitrage ML : rééquilibrer sans casser les groupes listwise ; sous-échantillonner la tête change
la distribution (essai : NDCG@10 global 0,412 → 0,409, +0,8 % sur requêtes de tête, −2,1 % sur les
pages de navigation). Inconnues : le framework (version figée) supporte-t-il l'élasticité ? quel
poids métier entre navigation et recherche ?
Attendu : plan de refactorisation (strangler) qui préserve l'API ; partitionnement avec intégrité
des groupes et borne sur le plus gros shard ; reprise sur checkpoint ; conception de l'audit ;
protocole d'évaluation par segment ; code Kotlin + tests.

---
## B002-T005 — PS · debugging et root-cause analysis · analyse de cause racine · Rust · prototype · monolithe modulaire · corruption logique de données · déploiement partiel · optimisation de performance
Contraintes : forte croissance des données, équipe réduite, multi-région.

Moteur de séries temporelles IoT d'une startup (prototype, Rust, monolithe modulaire), ingestion
≈ 10 req/s de lots de points, ≈ 9 Go compressés. Deux régions (eu-west, us-east) ingèrent
indépendamment le même flux Kafka et encodent chacune leurs blocs (compression type Gorilla :
delta-of-delta des timestamps + XOR des flottants). La PR « encodeur SIMD » (débit ×3,1) n'est
déployée qu'en eu-west (déploiement partiel). Depuis, 0,02 % des blocs donnent des valeurs
différentes entre régions pour une même série ; le CRC (calculé sur les octets compressés) passe ;
le job d'anti-entropie qui comparait les CRC entre régions a été désactivé « à cause de faux
positifs depuis v0.9 » (puisque les octets diffèrent désormais par construction).
Mécanisme caché : le nouvel encodeur range les delta-of-delta dans le seau 7 bits pour l'intervalle
[-63, 64] en complément à deux, alors que le décodeur (partagé, inchangé depuis v0.4) étend le
signe sur 7 bits ([-64, 63]) → une valeur exactement +64 est relue −64, décalant les timestamps
suivants du bloc ; n'arrive que sur échantillonnage irrégulier (ex. intervalle de 124 s après un
pas de 60 s). Le format de bloc n'a pas changé de version (format_version reste 3). Comme −64 n'est
jamais produit par le nouvel encodeur dans ce seau, la réparation déterministe est possible pour
les blocs écrits par v0.9 — à condition de savoir les identifier (inconnue : pas de version
d'encodeur dans l'en-tête ; il faut s'appuyer sur la région et la date d'écriture).
Preuves : extrait de la fonction de choix de seau du nouvel encodeur et du décodeur partagé, hexdump
+ décodage d'un bloc dans les deux régions (divergence à un index précis, à calculer),
stats d'écarts, message de désactivation de l'anti-entropie, benchmark.
Attendu : RCA rigoureuse, périmètre des blocs touchés, réparation, correctif qui conserve le gain
de performance, tests de propriété (aller-retour encode/décode sur distributions adverses),
garde-fous (version d'encodeur, anti-entropie sémantique) ; équipe de 2 personnes, croissance 40 %/mois.

---
## B002-T006 — ML · model evaluation et robustness · anomaly detection · Swift · extreme-scale · service mesh · leakage découvert après mise en production · panne d'un nœud · code review
Contraintes : p99 très faible, fenêtre de migration courte, SLA élevé.

Fintech : détection d'anomalies/fraude sur l'appareil (app iOS en Swift, modèle Core ML) pour les
paiements et connexions ; télémétrie ≈ 1,3 M événements/s de 60 M appareils ; backend (service de
features « réputation appareil », scoring de repli) derrière un service mesh. Le harnais
d'évaluation est écrit en Swift pour garantir la parité avec l'extraction de features en production.
Constat après 3 semaines : AUC-PR hors ligne 0,61 (rappel à 1 % de FPR 0,44) contre ≈ 0,23 estimé
en production sur les labels déjà mûrs. Mode : **code review** de la PR « eval-harness v3 » (2
fichiers Swift fournis) + refonte du protocole.
Mécanisme caché (plusieurs défauts à trouver dans le code, sans les signaler en commentaire) :
feature `chargebacks30d` calculée « au moment de l'extraction » (now) et non à la date de
l'événement → fuite du futur ; split aléatoire par événement (`shuffled` puis 80/20) → même appareil
en train et test ; seuil choisi sur le jeu de test ; événements des 30 derniers jours inclus alors
que les labels (chargebacks, 90 jours) ne sont pas mûrs (35 % arrivent après 30 j, 91 % à 60 j) —
biais inverse. Robustesse : quand un nœud du cache de features tombe (panne du 14/09
14:02–14:38), 4,1 % de features manquantes (0,1 % à l'entraînement) et −58 % de fraudes détectées.
Latence : modèle actuel p99 11,8 ms sur l'appareil, candidat 17,2 ms sur puces A12 ; le paiement
ne doit pas être bloqué > 50 ms (fail-open). Fenêtre : gel du code dans 9 jours, revue App Store ~2 j.
Inconnues : comment l'estimation production a été calculée ; les identifiants d'appareil
changent-ils à la réinstallation ?
Attendu : commentaires de revue classés (bloquant/majeur/mineur) et justifiés, protocole corrigé
(split temporel groupé, features as-of, maturité des labels, IC), plan de robustesse aux features
manquantes, plan de migration dans la fenêtre, critères.

---
## B002-T007 — PS · systèmes de décision sous incertitude · optimisation sous contraintes · Java · production · microservices · file de messages qui croît silencieusement · panne d'une région · conception de protocole
Contraintes : compatibilité API stricte, SLA élevé, legacy non remplaçable à court terme.

Prestataire de paiement : livraison de webhooks à 22 140 endpoints marchands (Java, microservices,
≈ 10 k livraisons/s). Retries avec backoff exponentiel stockés dans un sorted set Redis 6 unique
(`retry:delayed`, réplication asynchrone, legacy conservé ≥ 9 mois). Le tableau de bord suit
`queue.ready.depth` (plat ≈ 12 k) mais pas le sorted set, passé de 2,1 M à 41,7 M en 9 jours.
310 endpoints à < 5 % de succès portent 88 % des messages différés ; 1 900 endpoints lents
(p50 > 8 s pour un timeout de 10 s). Panne de la région eu-1 (09:12–09:59) : eu-2 a repris depuis
un checkpoint de 08:40 → 3,2 M webhooks en double ; 14 marchands ne dédupliquent pas sur event_id.
Contrat marchand figé : en-têtes `X-Event-Id`, `X-Signature-V1`, « au moins une fois pendant 72 h »,
seuls des en-têtes optionnels peuvent être ajoutés.
Mécanisme caché : backoff par message et non par endpoint (un endpoint mort = 400 k minuteurs
indépendants), aucun disjoncteur, partitionnement des workers par hash de marchand (blocage en tête
de file), le sorted set non répliqué synchroniquement rend le point de reprise imprécis.
Preuve de code : `long delay = Math.min(base * (1L << attempt), MAX_DELAY) + jitter(); redis.zadd(...)`.
Décision sous incertitude : un endpoint est-il mort ou lent ? comment allouer 12 k livraisons/s entre
marchands (équité, SLA 99,9 % en < 5 min pour les endpoints sains) ?
Attendu : spécification de protocole (états, ordonnancement par endpoint, poignée de main de
bascule / filigrane de déduplication), formulation d'optimisation sous contraintes, modèle de
capacité, cœur d'ordonnanceur en Java + simulation, métriques manquantes, runbook de bascule.

---
## B002-T008 — PS · raisonnement logique et décision · planification multi-objectifs · TypeScript · prototype · stream processing · saturation d'un sous-ensemble de nœuds · rejouement d'événements · conception de schéma de données
Contraintes : multi-région, résilience à la panne d'une région, p99 très faible.

Compagnie aérienne : prototype (TypeScript/Node, stream processing) de réacheminement des passagers
lors d'annulations (IROPS). ≈ 10 événements/s en prototype, cible production : 2 000 annulations/min
en cas d'orage. Objectifs multiples : minimiser le retard, respecter les statuts de fidélité, ne
pas séparer les familles, mineurs non accompagnés, contraintes de correspondance minimale.
Rejouement de la journée d'orage du 2026-09-02 : 1 318 décisions différentes sur 9 420 (14 %) ;
les passagers ont reçu deux notifications contradictoires après une bascule de région.
Saturation : 3 partitions sur 12 à 100 % CPU (vols des hubs), p99 4,2 s.
Mécanisme caché : la décision dépend de `Date.now()` (expiration des blocages de sièges) et de
l'ordre d'itération d'une `Map` remplie dans des callbacks de `Promise.all` (ordre d'arrivée des
réponses d'inventaire) → non déterministe au rejeu ; partitionnement par numéro de vol alors que
les décisions d'un même passager/famille touchent plusieurs vols. Règles contradictoires : trois
règles métier ne peuvent pas toutes être satisfaites dans certains cas et l'ordre de priorité entre
« platinum prioritaire » et « mineurs non accompagnés d'abord » n'est pas spécifié (inconnue à
faire remonter au métier).
Preuves : exemples d'événements JSON, diff de rejeu (3 exemples), extrait TS du moteur, métriques
de partitions, jeu de règles.
Attendu : schéma de données (événements versionnés, enregistrements de décision avec empreinte des
entrées, blocages d'inventaire), fonction de décision déterministe, formulation multi-objectifs
(lexicographique vs pondérée) et questions au métier, partitionnement, bascule de région, code TS +
tests de rejeu.

---
## B002-T009 — ML · deep learning · NLP long-context · Python · high-scale · multi-région actif/actif · régression de sécurité · partition réseau · forensic debugging
Contraintes : multi-tenant, fenêtre de migration courte, réseau partiellement instable.

Plateforme d'inférence LLM B2B (résumé de documents juridiques longs, jusqu'à 128 k tokens) :
≈ 100 k req/s sur la passerelle (dont ≈ 1 800 req/s de génération longue), ≈ 100 To de documents,
640 tenants dont 38 sous contrat d'« isolation stricte ». Deux régions actif/actif avec un cache
de blocs KV (prompt caching) partagé entre réplicas et un index répliqué entre régions.
Incident : un tenant (T-0412) signale un résumé contenant une clause d'un document d'un autre
tenant (T-0077). Chronologie : v2.4 introduit la « déduplication des blocs de clauses types » pour
augmenter le taux de hit (31 % → 58 % le 17/09) ; partition réseau inter-régions le 18/09
02:10–02:55 ; le drapeau de configuration a été désactivé en eu-west à 01:30 le 18/09 mais est
resté actif en eu-central jusqu'au 19/09 11:40 (propagation par gossip interrompue).
Mécanisme caché : quand la déduplication est active, la clé d'un bloc KV ne chaîne plus le hash du
bloc parent (seulement modèle + tokens du bloc) ; or les KV d'un bloc dépendent de tout le contexte
précédent → un bloc de texte identique réutilisé depuis le contexte d'un autre tenant injecte des
informations de ce contexte. De plus le tenant n'est pas dans la clé (même avec chaînage, un hit
révèle par le temps de réponse qu'un autre tenant a soumis le même préfixe — canal auxiliaire).
Extrait Python de `block_key(...)` fourni. Invariant utile (à ne pas donner) : sortie avec cache ==
sortie sans cache en décodage glouton.
Forensic : fenêtre exacte, requêtes et tenants potentiellement touchés (journaux de hits conservés
7 jours avec hash de bloc, sans tenant : inconnue), obligation de notification sous 72 h,
remédiation sans vider tout le cache (réchauffement = +38 % de GPU pendant 36 h).
Défensif uniquement : aucune méthode pour exploiter la fuite.

---
## B002-T010 — ML · recommender systems · model serving · C++ · small-production · architecture hexagonale · deadlocks rares · horloge dérivante · architecture greenfield
Contraintes : budget mensuel plafonné, observabilité sans surcharge excessive, auditabilité complète.

Média public régional : nouveau composant de serving de recommandations d'articles en C++
(greenfield, remplace un prototype Python), ≈ 500 req/s (pics 1 400 lors d'actualités), ≈ 500 Go.
Architecture hexagonale (ports : génération de candidats, feature store, runtime de modèle ONNX
two-tower + reranker de 180 Mo, règles éditoriales de pluralisme — « au moins 2 sources distinctes
dans le top 10 », « ≤ 30 % d'un même thème » — et journal d'audit exigé par le régulateur : chaque
recommandation doit être justifiable). Latence p99 cible 60 ms ; 2 000 candidats par requête.
Un PoC C++ d'un prestataire sert de point de départ : deadlock environ tous les 2 jours sous charge
(dump gdb fourni : thread de rechargement à chaud du modèle tient le mutex du registre et attend la
fin des requêtes en vol sur une condition variable, pendant qu'un thread requête tient le verrou
d'un shard du cache de features et appelle le registre → inversion d'ordre des verrous, à ne pas
nommer). Horloge : TTL de fraîcheur des features et versions de modèles basés sur
`system_clock` ; sur certaines VM chrony signale un écart de 0,812 s puis un saut → features
périmées considérées fraîches, entrées d'audit non monotones.
Coût actuel du PoC : 3 100 €/mois (6 VM), plafond 2 400 €/mois ; observabilité ≤ 3 % de CPU.
Attendu : architecture (ports/adaptateurs), modèle de concurrence avec argument d'absence de
deadlock (pas de verrou sur le chemin chaud, RCU/échange atomique…), modèle du temps (monotone vs
mur, horloge logique hybride pour l'audit), conception du journal d'audit, squelette C++ du
rechargement et du chemin requête, plan de tests (TSan, stress, injection de sauts d'horloge),
modèle de coût.

---
## B002-T011 — ML · embeddings et retrieval · retrieval et reranking · Python · high-scale · event-driven · dérive de schéma · panne d'une zone · migration progressive
Contraintes : équipe réduite, zero downtime, déploiement progressif.

Marketplace d'offres d'emploi : recherche sémantique (≈ 90 k req/s en pointe autocomplétion
comprise, ≈ 22 k req/s de retrieval), 41 M offres, index HNSW shardé, reranker cross-encoder.
Les offres sont embarquées à l'ingestion par un pipeline événementiel (événements
offer.created/updated). Migration progressive de l'encodeur v1 (768 d) vers v2 (1 024 d,
multilingue) avec double index et répartition du trafic.
Dérive de schéma : le 03/09 l'équipe productrice a renommé `description` en `description_html`
(HTML) et changé `skills` (liste de chaînes → liste d'objets {name, level}) ; le registre de
schémas Avro était passé en compatibilité NONE « pour débloquer un déploiement ». Le worker
d'embedding fait `f"{offer.get('title','')}\n{offer.get('description','')}"` → 23 % des offres
embarquées sur le titre seul (longueur médiane du texte embarqué 212 → 19 tokens pour ces offres).
Panne de la zone eu-west-1b : shards 5 à 8 reconstruits par rejeu d'événements (4 h).
A/B : recall@100 hors ligne v2 +6 % sur le benchmark, mais taux de candidature en ligne −3,1 % dans
le traitement ; v2 a été indexé après la dérive → expérience confondue (à découvrir).
Équipe de 3 personnes ; budget GPU limité pour ré-embarquer.
Attendu : diagnostic des facteurs de confusion, contrat de schéma (tests de contrat côté
consommateur, compatibilité), backfill idempotent sous budget et sans impact p99, refonte de
l'expérience avec règle de décision fixée à l'avance, plan de migration avec garde-fous et rollback
d'index, code Python + tests.

---
## B002-T012 — PS · raisonnement probabiliste · diagnostic sous information incomplète · SQL · extreme-scale · event-driven · coût cloud qui dérive · disque lent · conception d'un système résilient
Contraintes : forte croissance des données, faible consommation mémoire, rollback obligatoire.

Éditeur de jeux mobiles / analytics : ingestion événementielle ≈ 1,4 M événements/s dans un cluster
ClickHouse auto-géré de 48 nœuds (disques réseau de type gp3 pour le chaud ≈ 180 To, tiering S3
pour le froid ≈ 1,3 Po). Coût +63 % en 6 semaines pour +18 % de volume. Information incomplète :
l'export de facturation n'attribue que ≈ 70 % du coût ; `query_log` échantillonné à 10 %
(`log_queries_probability=0.1`) depuis 5 semaines — changement fait la même semaine que le début
de la dérive (facteur de confusion sur la visibilité).
Hypothèses concurrentes à quantifier : (H1) 7 nœuds sur 48 plafonnés à 125 Mo/s de débit disque
(crédits épuisés) → merges en retard → explosion du nombre de parts → plus de CPU et de lectures ;
(H2) un nouveau tableau de bord interroge 30 jours chaque minute alors que le TTL déplace les
données vers le volume froid S3 après 7 jours → requêtes GET S3 ; (H3) croissance naturelle ;
(H4) trafic inter-AZ de resynchronisation des réplicas en retard sur les nœuds lents.
Preuves : ventilation hebdomadaire des coûts (calcul, stockage, requêtes S3, inter-AZ, autres),
métriques disque par nœud, résultats `system.parts`, échantillon de `query_log`, DDL des vues
matérialisées avec `TTL ... TO VOLUME 'cold'`, requête SQL du tableau de bord.
Contraintes : nœuds de 64 Go dont 40 Go pour les requêtes (pas de montée de gamme avant le
trimestre suivant) ; toute modification de politique de stockage/TTL/schéma réversible en < 1 h
sans perte ; croissance +9 %/mois attendue.
Attendu : attribution probabiliste de la dérive (a priori, vraisemblances, données manquantes
explicites), mesures/expériences discriminantes chiffrées, conception résiliente
(merges, tiering, backpressure), requêtes SQL de diagnostic et nouvelles vues, plan de rollback.

---
## B002-T013 — PS · optimisation combinatoire · conception d'algorithme efficace · C# · production · microservices · backpressure insuffisante · latence d'un fournisseur externe · conception de tests de charge
Contraintes : multi-tenant, zero downtime, observabilité sans surcharge excessive.

Plateforme B2B de voyages d'affaires (.NET/C#, microservices), ≈ 10 k req/s de recherches
d'itinéraires (vols + hôtels, jusqu'à 4 segments), 1 100 entreprises clientes avec chacune une
politique voyage (JSON : plafond par nuit, compagnies préférées, classe, budget total).
L'algorithme actuel énumère le produit cartésien des options (jusqu'à 200 vols par segment × 150
hôtels) puis filtre par politique, avec un élagage tardif ; il appelle 3 fournisseurs (GDS) avec un
parallélisme non borné (`Task.WhenAll` sur toutes les combinaisons segment × fournisseur).
Incident du 08/09 : le fournisseur X passe d'un p99 de 800 ms à 6 s ; en parallèle le tenant
« Acme » lance un réacheminement de masse (4 000 voyageurs) ; 38 k requêtes en vol, file du
ThreadPool, pauses GC, 11 Go de mémoire, 503 pour tous les tenants.
Mode : **concevoir les tests de charge** qui reproduisent l'incident et valident un nouvel
algorithme (recherche anytime sous budget de temps : branch & bound, beam search…) et une
backpressure (limites par tenant, concurrence adaptative, hedging borné).
Attendu : algorithme avec complexité et garantie de qualité sous budget de temps, conception de la
backpressure, plan de tests de charge (modèle de charge issu de traces, injection de latence
fournisseur, tenant bruyant, pièges de coordinated omission, seuils de réussite), code C# du cœur de
recherche et d'un limiteur de concurrence, harnais de test ; observabilité ≤ 2 % CPU (pas de
traçage à 100 % des appels fournisseurs).

---
## B002-T014 — PS · planification et recherche · débogage d'un système non déterministe · C# · prototype · architecture hexagonale · timeouts intermittents · panne d'une zone · plan de rollback
Contraintes : SLA élevé, multi-région, budget mensuel plafonné.

Prototype de planification de trajets pour robots mobiles d'entrepôt (multi-agent path finding),
service .NET/C# en architecture hexagonale, ≈ 10 requêtes de planification/s, deux entrepôts
pilotes (Lyon, Saragosse) servis depuis deux régions (28 ms inter-régions). La v0.7 (Conflict-Based
Search avec expansion parallèle) remplace la v0.6 (planification par priorités, séquentielle).
Symptômes : 3 % des requêtes dépassent la deadline de 2 s (l'adaptateur HTTP réessaie 2 fois →
requêtes dupliquées) ; rejouer 50 fois la même entrée donne 7 plans distincts (coûts 212 à 219) et
3 dépassements ; les timeouts se concentrent sur les instances à conflits symétriques (croisements
en couloir). Panne de zone : la table de réservations (cellule × pas de temps) a été restaurée
depuis un snapshot (« 37 réservations obsolètes ») → conflits évités de justesse (arrêts d'urgence).
Mécanisme caché : la liste ouverte du niveau haut de CBS est un `SortedSet<Node>` avec un
comparateur sur le seul coût → deux nœuds de même coût sont considérés égaux et le second est
silencieusement ignoré (perte de complétude → échecs/timeouts) ; les expansions parallèles
(`Parallel.ForEach` + liste partagée sous verrou) rendent l'ordre d'insertion non déterministe.
Rollback v0.7 → v0.6 : le format de la table de réservations a changé (exemples JSON des deux
versions à fournir) ; invariant de sécurité : jamais deux robots sur la même cellule au même pas.
SLA du pilote : 99,5 % des commandes préparées à l'heure ; budget 1 800 €/mois.
Attendu : stratégie de débogage du non-déterminisme (harnais de rejeu déterministe, graines,
ordonnancement contrôlé), hypothèses classées et expériences, plan de rollback avec migration de la
table et invariants, critères go/no-go, correctifs C#, tests de propriété (petites grilles vs
recherche exhaustive).

---
## B002-T015 — ML · speech/audio ML · class imbalance · Python · small-production · actor model · perte ou retard d'événements · checkpoint corrompu ou incomplet · code review
Contraintes : p99 très faible, faible consommation mémoire, compatibilité API stricte.

Téléassistance aux personnes âgées : détection d'événements sonores de détresse (chute, bris de
verre, cri) sur des fenêtres audio de 2 s envoyées par ≈ 1 000 boîtiers actifs (≈ 500 fenêtres/s),
≈ 500 Go d'audio. Déséquilibre extrême : ≈ 1 fenêtre positive pour 40 000. Service Python en
modèle d'acteurs (un acteur par session de boîtier). Mode : **code review** d'une PR qui passe à
une focal loss, recalibre le seuil et modifie la logique de redémarrage des acteurs.
Mécanisme caché (défauts à trouver dans le diff, sans les signaler) : `load_state_dict(strict=False)`
qui ignore silencieusement les clés manquantes (le dernier checkpoint uploadé est tronqué :
37,1 Mo au lieu de 41,9 Mo ; log WARNING « Missing key(s) in state_dict: head.2.weight,
head.2.bias ») ; rapport d'évaluation en accuracy 99,97 % et ROC-AUC 0,991 sur un jeu de test
rééquilibré 1:1 (« rappel 0,93 au seuil 0,5 ») ; seuil choisi sur le test ; paramètre alpha de la
focal loss inversé ; redémarrage des acteurs à au plus une fois (0,7 % des fenêtres perdues pendant
les redémarrages progressifs, retards jusqu'à 45 s quand la boîte aux lettres déborde).
Production : rappel sur incidents audités passé de 0,81 à 0,52 après le dernier déploiement.
Contraintes : détection→alerte p99 < 3 s (inférence CPU p99 < 80 ms) ; 2 Go de RAM par hôte de
200 acteurs, modèle ≤ 25 Mo ; API d'alerte consommée par un logiciel certifié de centre d'appels
(schéma v2 figé : `device_id`, `event_type` enum, `confidence` 0–1, `ts` ; changer l'enum =
recertification de 6 mois).
Attendu : revue structurée (bloquant/majeur/mineur) justifiée, protocole d'évaluation adapté au
déséquilibre extrême (PR-AUC, rappel à taux de fausses alarmes fixé par boîtier-jour, intervalles
de confiance avec peu de positifs), garde d'intégrité des checkpoints, sémantique de livraison des
acteurs sous contrainte mémoire, calibration de `confidence` sans changer l'API.

---
## B002-T016 — PS · problèmes multi-étapes · raisonnement probabiliste · Bash · high-scale · multi-région actif/passif · fuite mémoire progressive · panne d'une région · forensic debugging
Contraintes : forte croissance des données, auditabilité complète, legacy non remplaçable à court terme.

Banque : plateforme d'autorisation de paiements (messages ISO 8583), ≈ 100 k req/s sur 400 hôtes
Linux, démon C d'un éditeur (binaire fermé, non remplaçable avant 2 ans) qui forke des workers.
Les hôtes sont tués par l'OOM après ≈ 11 jours ; le 21/09, 38 hôtes de la région primaire tombent
en 47 min (tous déployés le même jour → fuites synchronisées = défaillance corrélée) → bascule vers
la région passive, dont les hôtes ont été redémarrés 3 jours plus tôt (échéance ≈ 8 jours).
Indices : RSS des workers +212 Mo/jour en moyenne (variance entre hôtes) ; la part des messages
« 0420 reversal » est passée de 1,2 % à 3,9 % avec la croissance ; le cron de garde redémarre le
démon si RSS > 90 % mais mesure `ps -o rss` du seul processus parent alors que la fuite est dans
les workers forkés (à ne pas expliciter).
Contraintes d'investigation : seulement Bash + coreutils + outils déjà présents (pas de gdb en
production, pas de nouvel agent), toutes les commandes journalisées via sudo, sorties horodatées,
hachées et archivées 10 ans ; accès par bastion SSH.
Attendu : plan d'investigation multi-étapes ; scripts Bash sûrs (lecture seule, idempotents,
débit limité sur 400 hôtes, piste d'audit), agrégation (awk) des pentes de fuite ; modèle
probabiliste du temps avant OOM et du risque de défaillances simultanées dans la région passive ;
plan de redémarrages échelonnés optimisé ; dossier de preuves pour l'éditeur.

---
## B002-T017 — PS · problem solving sous contraintes · approximation sous contrainte de temps · JavaScript · small-production · service mesh · duplication sporadique d'opérations · perte de cache · migration progressive
Contraintes : équipe réduite, résilience à la panne d'une région, fenêtre de migration courte.

Livraison de repas : service de dispatch (Node.js) qui affecte des coursiers aux commandes par
zone, ≈ 500 req/s, derrière un service mesh (Envoy). Migration ville par ville depuis un monolithe
PHP (greedy, ETA de prise en charge moyen 8,6 min) vers le service Node (affectation optimale par
algorithme hongrois O(n³), ETA 7,9 min) ; 14 villes restent à migrer en 3 semaines avant le pic de
fin d'année ; équipe de 3 développeurs ; 2 régions.
Symptômes : 0,3 % des commandes affectées à deux coursiers ; corrélation avec les heures où le p99
d'affectation dépasse 150 ms (zones de pointe à 180 coursiers : 90–240 ms) et avec les redémarrages
de pods.
Mécanisme caché : politique de retry Envoy (`retry_on: 5xx,reset,connect-failure,retriable-4xx`,
`per_try_timeout: 150ms`, `num_retries: 2`) qui rejoue un POST /assign non idempotent dont la
première tentative a abouti ; réservations des coursiers gardées dans une `Map` en mémoire perdue
au redémarrage du pod (perte de cache). Fournir la config YAML et l'extrait JS.
Attendu : algorithme d'approximation anytime à temps borné avec évaluation de la qualité
(enchères, greedy + amélioration locale, décomposition par sous-zones…), idempotence de bout en
bout à travers le mesh (clés d'idempotence, réservation durable avec CAS/bail), plan de migration
ville par ville avec rollback < 5 min, comportement en bascule de région, code JS + rejeu de soirées
de pointe avec kills de pods et latence injectée.

---
## B002-T018 — PS · problem solving sous contraintes · preuve ou vérification d'invariants · Kotlin · production · monolithe modulaire · garbage collector en surcharge · horloge dérivante · conception d'un système résilient
Contraintes : rollback obligatoire, réseau partiellement instable, déploiement progressif.

Programme de fidélité / cartes cadeaux : registre de soldes (Kotlin, JVM, monolithe modulaire,
10 nœuds, ≈ 10 k req/s, PostgreSQL en READ COMMITTED). Autorisations (« holds ») avec bail de
7 min, capture sur un nœud, expiration par un balayeur sur un autre nœud, chacun avec sa propre
horloge. En 2 semaines : 14 comptes à solde négatif, 3 comptes dont la somme des écritures ≠ solde.
Indices : logs G1 « Pause Young (G1 Humongous Allocation) 1812.4ms » (gros JSON d'historique),
chrony : décalage −640 ms sur le nœud 3 puis saut ; chronologie d'un compte négatif (hold créé sur
le nœud 2, expiré par le balayeur du nœud 5, capturé sur le nœud 2 après une pause GC).
Code Kotlin fourni : `capture()` vérifie `clock.instant() > hold.expiresAt` puis ajoute un débit et
supprime le hold, sans condition côté base ; le balayeur crédite les holds expirés selon sa propre
horloge (ne pas nommer le problème de bail sans fencing).
Contraintes : schéma réversible, 0,5 % de pertes de paquets et blocages de 2 s entre nœuds et
réplicas, canari sur 1 nœud pendant 48 h.
Attendu : liste formelle des invariants, analyse des entrelacements qui les violent, conception
(jetons de fencing, mises à jour conditionnelles en base, écrivain unique par compte…), esquisse de
preuve, atténuation GC, modèle du temps, code Kotlin, tests par injection de fautes (pauses GC,
sauts d'horloge, pertes réseau), plan de migration et de rollback, réconciliation des 14 comptes.

---
## B002-T019 — PS · problem solving algorithmique · recherche de contre-exemple · Rust · prototype · serverless · latence p99 qui explose sans hausse du p50 · version mixte pendant migration · conception de tests de charge
Contraintes : rollback obligatoire, équipe réduite, forte croissance des données.

Prototype serverless (fonctions Rust) « bornes de recharge les plus proches » : index spatial
chargé depuis un stockage objet au démarrage à froid (≈ 84 Mo pour 1,1 M points ; 180 k il y a un
an). Migration de v1 (R-tree) vers v2 (k-d tree maison construit en masse) via un alias pondéré
50/50 → versions mixtes. p50 stable à 8 ms, p99 passé de 40 ms à 1,9 s. L'équipe affirme « v2 est
toujours au moins aussi rapide que v1 » : le candidat doit chercher un contre-exemple.
Mécanisme caché : la construction de v2 partitionne par valeur (`p[axis] < pivot` à gauche,
le reste à droite) ; les hubs de recharge ont des dizaines de points aux coordonnées identiques →
la partition ne progresse plus, un garde-fou transforme le nœud en feuille géante (distribution des
tailles de feuilles : p50 16, p99 16, max 4 812) → scan linéaire pour les requêtes près des hubs
(zones urbaines denses) ; s'y ajoutent les démarrages à froid (≈ 1,5 % des invocations, chargement
1,4 s) quand la concurrence monte. Le format du jeu de données a migré vers la disposition v2 :
revenir à v1 demande un double format.
Attendu : construction formelle d'une famille d'entrées contre-exemple et de sa complexité,
algorithme corrigé avec garanties de pire cas, conception des tests de charge (ratio de démarrages
à froid, biais spatial, mesure par version, coordinated omission), plan de rollback à double
format, code Rust + tests de propriété contre force brute, benchmarks ; équipe de 2 personnes.

---
## B002-T020 — ML · computer vision · clustering · C++ · extreme-scale · stream processing · contamination du jeu d'évaluation · labels en retard ou partiellement manquants · optimisation de performance
Contraintes : SLA élevé, legacy non remplaçable à court terme, faible consommation mémoire.

Grande marketplace : détection en flux de quasi-doublons d'images produits (≈ 1,1 M événements
image/s en comptant vignettes et re-encodages, ≈ 4,2 Po d'images), en C++, par clustering de pHash
DCT 64 bits (rayon de Hamming 6) avec LSH en 8 bandes de 8 bits. Sert au dédoublonnage des annonces
et à la construction des splits train/éval d'un classifieur de catégories produit.
Optimisation récente : ne sonder que 4 bandes sur 8 (+2,3× de débit, −41 % de mémoire) ; rappel
des paires quasi-doublons sur 120 k paires étiquetées : 0,97 → 0,71 (à mettre dans une preuve
sans en tirer la conclusion).
Contamination : exactitude du classifieur 94,1 % sur le jeu d'éval, mais 86,9 % ± 1,5 sur un
sous-ensemble audité à la main de 2 000 items sans quasi-doublon en train. Labels : 31 % des items
reçoivent leur catégorie plus de 72 h après l'upload ; le jeu d'éval est figé à T+24 h (biais).
Contraintes : 48 Go de RAM par nœud pour l'index d'une fenêtre de 7 jours (44,8 Go utilisés avec
4 bandes ; 8 bandes demanderaient ≈ 71 Go) ; SLA 99,95 % des uploads traités en < 2 s ; le format
pHash 64 bits est consommé par 14 systèmes (inchangeable à court terme).
Attendu : analyse du compromis rappel/performance (probabilité de collision LSH en fonction de la
distance, du nombre de bandes et de leur taille), refonte qui retrouve un rappel exact sur le rayon
6 dans le budget mémoire (sans que la tâche ne cite de technique), modèle mémoire, procédure de
décontamination et ré-estimation, traitement des labels tardifs, code C++ de la recherche,
benchmarks et tests.

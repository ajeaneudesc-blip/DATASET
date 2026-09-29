# batch_002

20 tâches — 12 Problem Solving / 8 Machine Learning.
Énoncés uniquement : aucune solution n'est incluse.

## Sommaire

- B002-T001 — Rollback d'une politique RL de pacing budgétaire dont l'état diverge entre régions (Machine Learning)
- B002-T002 — Montants de facturation incohérents après la perte d'un nœud de cache de sommes cumulées en C (Problem Solving)
- B002-T003 — Feature flags en JavaScript edge : expériences faussées et isolates saturés pendant une migration par PoP (Problem Solving)
- B002-T004 — Refonte d'un pipeline learning-to-rank en Kotlin : shard géant, préemptions GPU et audit entre deux régions (Machine Learning)
- B002-T005 — Divergences silencieuses entre régions dans un moteur de séries temporelles Rust après l'arrivée d'un encodeur SIMD (Problem Solving)
- B002-T006 — Revue du harnais d'évaluation Swift d'un détecteur de fraude Core ML démenti par la production (Machine Learning)
- B002-T007 — Protocole de livraison de webhooks : relances qui saturent en silence et doublons après une bascule de région (Problem Solving)
- B002-T008 — Réacheminement de passagers pendant un orage : décisions non reproductibles au rejeu et schéma de données à reconcevoir (Problem Solving)
- B002-T009 — Clause d'un autre client dans un résumé juridique : forensique d'un cache KV partagé entre deux régions actives (Machine Learning)
- B002-T010 — Serving C++ de recommandations pour un média public : architecture hexagonale à partir d'un PoC qui se bloque et d'un audit incohérent (Machine Learning)
- B002-T011 — Migration progressive d'encodeur pour une recherche d'offres d'emploi : un A/B négatif après une dérive de schéma et la perte d'une zone (Machine Learning)
- B002-T012 — Diagnostic probabiliste d'une dérive de coût de 63 % sur un pipeline d'événements ClickHouse à 1,4 M événements/s (Problem Solving)
- B002-T013 — Reproduire en test de charge l'effondrement d'une recherche d'itinéraires B2B, puis valider un algorithme sous budget de temps (Problem Solving)
- B002-T014 — Déboguer un planificateur multi-agent de robots d'entrepôt non déterministe et préparer son rollback (Problem Solving)
- B002-T015 — Revue d'une PR « focal loss » après l'effondrement du rappel d'un détecteur sonore de détresse (Machine Learning)
- B002-T016 — Forensic en Bash d'une fuite mémoire synchronisée sur le démon d'autorisation fermé d'une banque (Problem Solving)
- B002-T017 — Doubles affectations d'un dispatch de coursiers Node.js en pleine migration ville par ville (Problem Solving)
- B002-T018 — Soldes négatifs dans un registre de cartes cadeaux Kotlin : invariants sous pauses GC et horloges dérivantes (Problem Solving)
- B002-T019 — Bornes de recharge les plus proches : p99 multiplié par 47 pendant la cohabitation de deux index spatiaux Rust (Problem Solving)
- B002-T020 — Quasi-doublons d'images en flux : rappel perdu, évaluation contaminée et index C++ bloqué à 48 Go par nœud (Machine Learning)

---

## B002-T001 — Rollback d'une politique RL de pacing budgétaire dont l'état diverge entre régions

| Axe | Valeur |
|---|---|
| Piste | Machine Learning |
| Domaine | machine learning général |
| Type | RL sous contraintes |
| Langage | Go |
| Charge | extreme-scale (1M+ req/s, 1 PB+) |
| Architecture | actor model |
| Incident | désynchronisation entre régions |
| Failure mode | double livraison |
| Mode | plan de rollback |

### Contexte

AdPulse opère une plateforme d'achat programmatique qui répond à 1,2 M requêtes d'enchères par seconde, réparties sur trois régions (us-east ≈ 540 k/s, eu-west ≈ 410 k/s, ap-south ≈ 250 k/s). Environ 1,4 PB de journaux d'enchères sont conservés pour l'entraînement.

Le rythme de dépense (pacing) et le niveau d'enchère de chaque campagne sont décidés par une politique d'apprentissage par renforcement sous contraintes. Elle est entraînée hors ligne toutes les 6 h par l'équipe Research. En ligne, deux multiplicateurs de Lagrange sont mis à jour à chaque notification de gain : λ_budget pour la contrainte de budget journalier et λ_cpa pour le coût par acquisition cible.

Le 22 septembre 2026, la politique v42 a été déployée à 09:10 UTC (canari 5 %), puis sur 100 % du trafic à 11:40 UTC. Les notes de version annoncent deux changements :
- λ est désormais normalisé par le budget journalier et devient sans dimension ;
- la clé de déduplication des notifications de gain change pour éviter des collisions d'identifiants entre exchanges.

Entre 12:00 et 18:00 UTC, deux problèmes ont été signalés : le support annonceurs relève des sous-livraisons massives en Europe et la finance détecte des campagnes qui dépassent leur budget. Le produit exige un « rollback immédiat vers v41 ». L'équipe Research signale que l'entraînement de v43 a démarré à 15:00 UTC sur les journaux du jour.

Tu es l'ingénieur principal chargé de décider et de piloter le retour à un état sûr.

### Architecture existante

- **Nœuds d'enchères (Go 1.22)** : 1 900 pods. Chaque campagne est un acteur par région, construit sur le runtime interne « hive » (boîte aux lettres, un acteur = une goroutine). L'acteur garde en mémoire l'état de pacing : dépense vue, λ_budget, λ_cpa, un filtre de Bloom des notifications déjà vues, et la version de politique utilisée.
- **Passivation** : un acteur inactif pendant 10 min est passivé. Son état est alors écrit dans un KV régional (snapshot), puis relu à la réactivation. Les snapshots sont répliqués de façon asynchrone entre régions (RPO annoncé : 5 min) pour permettre la reprise d'une campagne dans une autre région.
- **Versions** : un registre de poids par région sert les poids par numéro de version. Une campagne conserve la version enregistrée dans son snapshot jusqu'à la réinitialisation quotidienne de 00:00 dans son fuseau (règle de cohérence intra-journée).
- **Coordinateur budgétaire global** : toutes les 30 s, il répartit le budget restant de chaque campagne entre régions, à partir de la dépense déclarée par les acteurs.
- **Ledger de facturation** : il fait autorité. Il déduplique par WinID seul et est consolidé avec 15 min de retard. Les annonceurs sont facturés sur le ledger, jamais sur la vue des acteurs.
- **Notifications de gain** : elles sont envoyées par 14 exchanges avec une sémantique au moins une fois. L'exchange AX, majoritaire en Europe, réémet après 1 à 3 s sans accusé de réception.

### Problème

Plusieurs mécanismes se superposent, et la demande de rollback porte à la fois sur les poids de la politique et sur un état appris en ligne dont la sémantique a changé entre v41 et v42.

Il faut d'abord établir, preuves à l'appui, ce qui explique chacun des symptômes observés :
- la sous-livraison en eu-west ;
- les dépassements de budget en us-east ;
- le mélange de versions servies.

Il faut ensuite concevoir un plan de retour à un état sûr qui ne crée pas de nouveau dommage : un rollback, un roll-forward correctif, ou une combinaison des deux. Ce plan doit rester compatible avec les enchères continues, l'isolation par annonceur et la réplication asynchrone des snapshots, et il doit dire ce qu'il advient de l'entraînement de v43.

### Preuves


Tableau de bord à 18:00 UTC (dépenses rapportées au budget journalier au prorata de l'heure) :
```text
Région    Dépense vue      Dépense ledger   Campagnes >105 %   Campagnes <80 % du   λ_budget médian   Politique servie
          acteurs/budget   /budget          budget (ledger)    rythme cible         (acteurs v42)
us-east   0,96             0,95             2,1 % (1 870)      1,2 %                0,19              v42 97,4 % / v41 2,6 %
eu-west   0,87             0,85             0,2 %              7,0 %                0,86              v42 83,5 % / v41 16,5 %
ap-south  0,92             0,91             0,3 %              1,8 %                0,22              v42 99,6 % / v41 0,4 %
```


Extrait de journal des nœuds d'enchères us-east (échantillon, niveau INFO) :
```text
2026-09-22T13:41:07Z hive/activate campaign=c-88412 origin_snapshot=eu-west snapshot_ts=13:36:52 policy_version=41 lambda_budget=0.00031 lambda_cpa=0.00012
2026-09-22T13:41:07Z pacing/load  campaign=c-88412 weights=v42 reason="registry default (v41 evicted from us-east cache)"
2026-09-22T13:52:44Z pacing/alert campaign=c-88412 spend_rate=3.8x target over 10m
2026-09-22T14:03:19Z hive/activate campaign=c-10277 origin_snapshot=us-east snapshot_ts=14:01:02 policy_version=42 lambda_budget=0.41 lambda_cpa=0.07
```


Extrait du gestionnaire de notifications de gain (v42) :
```go
// pacing/win.go — v42
func (a *CampaignActor) onWin(ev WinEvent) {
    // Des exchanges réutilisent des WinID : on qualifie la clé par l'instant de réception.
    key := ev.WinID + ":" + strconv.FormatInt(ev.ReceivedAt.Truncate(time.Second).Unix(), 10)
    if a.seen.Test(key) {
        return
    }
    a.seen.Add(key)
    a.spentMicros += ev.PriceMicros
    a.lambdaBudget = math.Max(0, a.lambdaBudget+a.eta*(a.spendRate()-a.targetRate()))
    a.lambdaCPA = math.Max(0, a.lambdaCPA+a.etaCPA*(a.cpa()-a.targetCPA))
}
```

- Rapprochement acteurs / ledger par exchange, 12:00–18:00 UTC : notifications comptées par les acteurs mais absentes du ledger (doublons au sens WinID) — AX : 6,1 % (AX représente 72 % des gains en eu-west), autres exchanges européens : 0,2 %, exchanges US : 0,1 %. Le ledger étant consolidé avec 15 min de retard, sa dépense est légèrement inférieure à celle des acteurs même sans doublons. Avant 09:10 UTC, les écarts étaient inférieurs à 0,05 % partout.

Distribution des λ_budget dans les snapshots échantillonnés (10 000 par région) : les snapshots marqués policy_version=41 ont des valeurs entre 0,0001 et 0,0009 ; ceux marqués policy_version=42 entre 0,05 et 1,3. Structure persistée dans le KV régional :
```go
// hive/pacing/snapshot.go
type PacingSnapshot struct {
    CampaignID    string    `json:"cid"`
    PolicyVersion int       `json:"pv"`
    SpentMicros   int64     `json:"spent"`
    LambdaBudget  float64   `json:"lb"`
    LambdaCPA     float64   `json:"lc"`
    SeenFilter    []byte    `json:"seen"` // filtre de Bloom sérialisé
    SnapshotAt    time.Time `json:"ts"`
}
```

- Research : la politique hors ligne est entraînée sur les journaux d'enchères enrichis de la dépense vue par les acteurs ; le job v43 (démarré à 15:00 UTC) consomme les journaux de 09:00 à 15:00. Aucune information n'est disponible sur la sensibilité de l'entraînement à une dépense surestimée.

### Contraintes

- observabilité sans surcharge excessive — au plus 2 % de CPU supplémentaire par nœud d'enchères ; aucun log par requête (1,2 M req/s) ; métriques par campagne agrégées sur 1 min au minimum
- zero downtime — les enchères ne s'arrêtent jamais ; une campagne sans politique valide doit répondre en moins de 8 ms avec un comportement par défaut sûr (pas d'enchère ou enchère plancher)
- multi-tenant — 38 000 annonceurs, 212 000 campagnes actives ; aucune correction ne doit modifier la dépense facturée d'un annonceur non affecté ; chaque annonceur affecté doit recevoir un relevé chiffré de l'écart

### Objectifs

- Expliquer, preuves à l'appui, chacun des trois symptômes (sous-livraison eu-west, dépassements us-east, mélange de versions), en distinguant faits établis, hypothèses et inconnues.
- Définir un plan de retour à un état sûr, sans interruption des enchères, qui traite ensemble les poids, l'état appris en ligne (λ, dépense vue, filtre de déduplication) et la réplication des snapshots.
- Garantir que la contrainte budgétaire de chaque campagne est respectée pendant et après la transition, et chiffrer l'impact pour les annonceurs touchés.
- Décider du sort de l'entraînement v43 et des journaux du 22 septembre.

### Livrables

- Note de diagnostic : chaîne causale par symptôme, preuves utilisées, hypothèses restantes et mesures (peu coûteuses) permettant de les trancher.
- Plan de rollback / roll-forward séquencé : ordre des actions, état attendu à chaque étape, critères d'arrêt et de retour arrière du plan lui-même, durée estimée.
- Modifications Go de l'acteur couvrant la persistance et la réactivation de l'état, le traitement des notifications de gain et le comportement par défaut sûr, avec tests unitaires et un test de rejeu de 24 h de notifications avec doublons injectés.
- Stratégie de recalcul des λ et de la dépense à partir du ledger, et procédure de relevé par annonceur affecté.
- Liste minimale de métriques et d'alertes compatibles avec le budget d'observabilité, pour détecter une récidive (mélange de versions, écarts acteurs/ledger).

### Critères de réussite

- Au rejeu de la journée du 22 septembre avec les correctifs, l'écart entre dépense vue par les acteurs et ledger reste < 0,1 % par exchange, doublons AX compris.
- Pendant et après la transition : ≤ 0,5 % des campagnes au-delà de 102 % de leur budget journalier (ledger) et ≤ 2 % sous 80 % du rythme cible, dans chaque région.
- Aucune enchère n'est servie à partir d'un état restauré (local ou répliqué) incompatible avec les poids effectivement chargés ; vérifié par un test couvrant les réactivations croisées entre régions et versions, et par une métrique de production.
- Latence d'enchère p99 < 8 ms maintenue pendant toute la transition, et surcoût CPU des nouvelles métriques ≤ 2 % par nœud.
- Décision argumentée et traçable sur v43 : réutilisation, correction des journaux ou réentraînement, avec le critère retenu.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T002 — Montants de facturation incohérents après la perte d'un nœud de cache de sommes cumulées en C

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | optimisation algorithmique |
| Type | décomposition d'un problème complexe |
| Langage | C |
| Charge | small-production (500 req/s, 500 GB) |
| Architecture | batch + streaming |
| Incident | cache incohérent |
| Failure mode | perte de cache |
| Mode | diagnostic d'incident |

### Contexte

Voltaïa est un fournisseur d'électricité qui facture 2,4 millions de contrats équipés de compteurs communicants. Chaque compteur remonte 48 index semi-horaires par jour UTC. Les montants de facture et les estimations en cours de mois sont servis par l'API de tarification, avec environ 500 req/s en pointe. L'historique brut représente environ 500 Go, répartis entre PostgreSQL et Parquet.

Il y a trois semaines, un bug de firmware sur un modèle de compteur a fait passer les corrections de mesure de 90 000 à 1,1 million par jour. Ces corrections arrivent surtout en rafale entre 02:00 et 03:00 UTC, quand les compteurs rejouent leurs données.

Le 26 octobre 2026 à 03:10 UTC, le nœud de cache tarifd-2 (région eu-west-3) a été tué par l'OOM killer. Il a redémarré depuis le snapshot nocturne. Du 26 au 28 octobre, la réconciliation nocturne compare le cache et un recalcul batch sur un échantillon de 1 % des contrats. Elle a relevé des écarts sur 0,31 % des contrats échantillonnés, pouvant atteindre 4,7 % du montant de la période. Environ 38 000 factures ont été émises depuis le shard de tarifd-2 pendant ces deux jours.

Une partie de l'équipe soupçonne le passage à l'heure d'hiver du 25 octobre. Une autre soupçonne une corruption mémoire. La direction veut savoir combien de factures sont fausses, comment les corriger sans reconstruction complète, et comment éviter la récidive, y compris en cas de bascule de région.

### Architecture existante

- **tarifd** : démon C99 mono-processus et multi-thread (pthread), 2 nœuds par région, chacun responsable d'un shard de contrats (hachage de contract_id). Pour chaque contrat actif sur la période de facturation courante (jusqu'à 62 jours), il garde en mémoire un tableau de sommes cumulées de l'énergie en Wh. Toute somme sur un intervalle de créneaux se calcule ainsi en O(1). Les entrées sont regroupées en 65 536 buckets, chacun protégé par un pthread_rwlock.
- **Journal de corrections** : un log interne append-only avec offsets croissants. tarifd applique chaque correction en mettant à jour les sommes cumulées en aval du créneau corrigé.
- **Snapshot nocturne** : à 02:00 UTC, un thread de tarifd parcourt les buckets et écrit un snapshot au format v3 (environ 40 min). Au démarrage, tarifd charge le dernier snapshot puis rejoue le journal à partir de l'offset inscrit dans l'en-tête.
- **Batch + streaming** : un batch Spark nocturne recalcule factures et agrégats depuis l'historique brut et produit la réconciliation. Le streaming applique les corrections au cache et à l'historique.
- **Région de secours** : eu-central-1 reçoit les snapshots (copie à 03:00) et le journal de corrections (réplication asynchrone). Elle démarre ses nœuds tarifd de la même façon.
- Nœuds : 32 Go de RAM, 8 vCPU. Le cache occupe environ 29 Go par nœud.

### Problème

Il faut identifier le ou les mécanismes qui produisent des montants faux après la perte du nœud. Il faut aussi séparer ce qui relève de l'incident de ce qui relève de la dégradation générale apparue avec l'explosion des corrections : contention pendant le snapshot, pression mémoire, puis OOM.

Le problème doit être décomposé en sous-problèmes traitables et testables indépendamment, de la production du snapshot jusqu'à la bascule de région, en justifiant les frontières retenues. Il faut ensuite proposer pour chacun une solution compatible avec le code legacy et le budget.

Enfin, il faut une procédure pour identifier précisément les contrats et factures touchés, puis les corriger sans reconstruire tout le cache.

### Preuves


Journaux de tarifd-2 (horodatage UTC) :
```text
2026-10-26T02:00:04Z tarifd[1841]: snapshot: start log_offset=88412003
2026-10-26T02:41:17Z tarifd[1841]: snapshot: done entries=1203344 bytes=29.1G hdr.log_offset=89164118
2026-10-26T02:58:30Z tarifd[1841]: corrlog: apply backlog 412k corrections (bucket lock waits), prefetch buffer 1.6G
2026-10-26T03:10:52Z kernel: Out of memory: Killed process 1841 (tarifd) total-vm:33.4G anon-rss:31.0G
2026-10-26T03:11:40Z tarifd[2203]: warmup: loading snapshot 20261026T0200 (29.1G)
2026-10-26T03:58:02Z tarifd[2203]: warmup: replaying corrections from offset 89164118
2026-10-26T04:01:15Z tarifd[2203]: warmup: done, serving
```


Extrait de snapshot.c et de warmup.c (tarifd 3.2) :
```c
int snapshot_write(cache_t *c, FILE *out) {
    snap_hdr_t hdr = { .magic = SNAP_MAGIC, .version = 3 };
    fwrite(&hdr, sizeof hdr, 1, out);            /* réservé, réécrit en fin */
    for (size_t b = 0; b < c->n_buckets; b++) {
        pthread_rwlock_rdlock(&c->buckets[b].lock);
        write_bucket(&c->buckets[b], out);      /* contract_id, first_day, n_days, prefix[] */
        pthread_rwlock_unlock(&c->buckets[b].lock);
    }
    hdr.log_offset = corrlog_committed_offset(c->log);
    fseek(out, 0, SEEK_SET);
    fwrite(&hdr, sizeof hdr, 1, out);
    return 0;
}

/* warmup.c */
e->applied_offset = hdr->log_offset;   /* pour chaque entrée chargée */

/* tarif_cache.c */
int apply_correction(entry_t *e, const corr_t *c) {
    if (c->offset <= e->applied_offset) return 0;   /* déjà appliquée */
    size_t i = (size_t)(c->day - e->first_day) * 48 + c->slot;
    int64_t delta = c->new_wh - c->old_wh;
    for (size_t k = i + 1; k <= (size_t)e->n_days * 48; k++)
        e->prefix[k] += delta;
    e->applied_offset = c->offset;
    return 1;
}
```


Six contrats en écart (réconciliation du 27/10), avec les corrections reçues le 26/10 :
```text
contrat     écart (Wh)  corrections à delta non nul du 26/10 (offset @ heure UTC)
C-0419982   -18 240     88468310 @ 02:03:11 ; 89321954 @ 06:12:40
C-1022871   +3 115      88959204 @ 02:29:55
C-1804410   -9 870      88667531 @ 02:14:02 ; 88699877 @ 02:15:47
C-0033172   +41 002     89150442 @ 02:40:31
C-2210945   -2 260      88543119 @ 02:07:20
C-0901337   +7 480      89052768 @ 02:35:09 ; 89359490 @ 09:48:03
```
Parmi l'ensemble des contrats en écart, 3 % ont une correction portant sur un créneau du 25 octobre.

- Métriques de l'API de tarification et de tarifd : p99 de 12 ms en journée, 380 ms entre 02:00 et 02:45 UTC depuis trois semaines ; nombre moyen de cases mises à jour par correction : environ 1 450 ; part des corrections de la rafale nocturne dont new_wh = old_wh : 98 % ; CPU moyen de tarifd : 9 %, 71 % pendant la fenêtre de snapshot.
- Le snapshot et le journal de corrections de la nuit du 26/10 ont été copiés vers eu-central-1 à 03:00 comme chaque nuit ; aucun test de bascule n'a été fait depuis l'explosion des corrections. tarif_audit lit les snapshots v3 en vérifiant magic et version, et ignore les octets au-delà de la taille d'entrée attendue.

### Contraintes

- legacy non remplaçable à court terme — le démon tarifd (C99, 2019) reste en production au moins 18 mois ; le format de snapshot v3 est lu par tarif_audit, outil réglementaire non modifiable avant le T3 2027
- résilience à la panne d'une région — bascule vers la région de secours eu-central-1 en moins de 30 min, avec des montants strictement identiques à ceux de la région primaire
- budget mensuel plafonné — 14 000 €/mois au total, dont 13 200 € déjà consommés en régime courant ; une reconstruction complète du cache depuis le batch coûte ≈ 380 € et 6 h de calcul

### Objectifs

- Établir le mécanisme des écarts et la population exacte des contrats et factures touchés, sans se contenter de l'échantillon de 1 %.
- Décomposer le problème en sous-problèmes indépendants, avec pour chacun une solution qui respecte le legacy (format v3 lisible par tarif_audit) et le budget.
- Revoir l'algorithme d'application des corrections et la production du snapshot pour tenir la charge actuelle et une croissance x3, avec une analyse de complexité en temps et en mémoire.
- Garantir des montants identiques entre région primaire et région de secours après bascule.

### Livrables

- Diagnostic écrit : mécanisme, preuves, hypothèses écartées (heure d'hiver, corruption mémoire) avec la justification de leur rejet ou les mesures pour les trancher.
- Procédure d'identification et de réparation ciblée des entrées et factures touchées, avec estimation de coût et de durée.
- Conception et code C (C99, pthread) des correctifs retenus pour la production du snapshot, le redémarrage et l'application des corrections, avec au moins deux structures de sommes comparées pour des corrections fréquentes et la compatibilité ascendante du format v3.
- Plan de tests : tests de propriété comparant le cache à un recalcul naïf sur des séquences aléatoires de corrections concurrentes du snapshot, test de redémarrage en pleine rafale, test de bascule de région.
- Chiffrage mémoire, CPU et coût mensuel des options, et plan de déploiement avec retour arrière.

### Critères de réussite

- Réconciliation à 100 % des contrats du shard (et non 1 %) : zéro écart après réparation, et zéro écart après un redémarrage provoqué en pleine rafale de corrections.
- p99 de l'API ≤ 25 ms y compris pendant la production du snapshot, avec 1,1 million de corrections par jour concentrées sur une heure.
- Empreinte mémoire de tarifd ≤ 28 Go par nœud (RAM physique inchangée à 32 Go) et aucun OOM au rejeu d'une rafale trois fois supérieure à celle du 26/10.
- tarif_audit lit sans modification les snapshots produits par la nouvelle version (test de non-régression sur le binaire actuel).
- Montants identiques à l'unité près entre eu-west-3 et eu-central-1 après une bascule simulée ; coût total des corrections et réparations ≤ 700 € sur le mois.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T003 — Feature flags en JavaScript edge : expériences faussées et isolates saturés pendant une migration par PoP

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | problem solving algorithmique |
| Type | choix entre plusieurs stratégies |
| Langage | JavaScript |
| Charge | high-scale (100k req/s, 100 TB) |
| Architecture | serverless |
| Incident | régression après déploiement |
| Failure mode | version mixte pendant migration |
| Mode | implémentation multi-fichiers |

### Contexte

Aiguilla édite une plateforme SaaS de feature flags et d'expérimentation A/B utilisée par 1 900 tenants. Les SDK de leurs applications (web, iOS, Android, serveurs) appellent un service d'évaluation exécuté en fonctions edge dans 312 PoP, soit environ 100 000 requêtes/s en pointe. Chaque requête renvoie, pour un utilisateur donné, la variante de chacun des flags du tenant. Chaque évaluation d'un flag d'expérience émet un événement d'exposition ; l'entrepôt en conserve environ 115 To sur 90 jours.

Le plus gros tenant, t-0193 (une plateforme de streaming), compte 2 300 flags, 14 200 règles de ciblage et des listes d'identifiants qui totalisent 2,1 M valeurs distinctes. Avec l'évaluateur v1, son CPU d'évaluation atteint 7,8 ms au p99, pour un budget de 10 ms par requête. Ses règles croissent de 6 % par mois : le budget serait épuisé vers février 2027. L'évaluateur v2 a été écrit pour cette raison : il compile les règles en index de bitsets par attribut et par valeur.

v2 a été activé PoP par PoP : 1 % le 21/09, 10 % le 22/09, 50 % le 23/09 (156 PoP, 29 % du trafic). Le 25/09, l'équipe data de t-0193 a signalé un déséquilibre d'échantillon sur son test de tunnel de paiement, et le déploiement a été gelé. Au 28/09, trois expériences de deux tenants sont en Sample Ratio Mismatch. Des utilisateurs affirment avoir vu les deux versions d'un même écran. Enfin, les isolates des PoP v2 sont évincés près de 50 fois plus souvent qu'avant.

L'équipe plateforme compte quatre ingénieurs. Tu prends en charge l'analyse, le choix de stratégie et l'implémentation.

### Architecture existante

- **Plan de contrôle (Node.js 20)** : chaque publication d'un tenant crée une version de configuration immuable (`cfg`). Pendant la migration, `compiler/` en tire deux artefacts : format 1 (règles JSON ; listes de plus de 64 valeurs stockées en hachages 64 bits triés dans des Uint32Array) et format 2 (index compilé), poussés dans le KV global de la plateforme (propagation ≤ 60 s).
- **Fonctions edge** : JavaScript ES2022 dans des isolates V8 ; 128 Mo de tas par isolate, 10 ms de CPU par requête, 500 ms pour le premier chargement d'un artefact. Les artefacts de plusieurs tenants partagent un cache LRU ; un isolate qui dépasse son plafond est évincé.
- **Affectation** : `edge/bucketing.js`, commun aux deux versions, calcule `murmur3_32(salt:key) % 10000`. Rien n'est stocké : la stabilité repose sur le déterminisme (même `cfg`, même clé, même variante).
- **Contrat produit** : les règles d'un flag s'appliquent dans l'ordre affiché dans la console ; la première satisfaite décide, sinon la règle par défaut.
- **Routage** : anycast ; version d'évaluateur fixée par PoP (propagation ≈ 5 min). En une semaine, 6,8 % des utilisateurs actifs de t-0193 passent par au moins deux PoP.
- **Statistiques** : une exposition porte tenant, flag, `cfg`, clé, variante, indice de règle, PoP et version d'évaluateur. Un test χ² quotidien signale le SRM (p < 0,001) ; l'analyse exclut les utilisateurs ayant reçu plus d'une variante.

### Problème

Trois phénomènes se superposent depuis que les deux évaluateurs cohabitent : le déséquilibre d'échantillon, les utilisateurs exposés à plusieurs variantes et la saturation mémoire des isolates v2. Il faut relier chacun à un mécanisme démontré par les preuves. Il faut aussi mesurer l'étendue réelle : quels flags, tenants et utilisateurs ont reçu un résultat différent selon la version, bien au-delà des trois expériences signalées.

Il faut ensuite retenir une stratégie d'évaluation qui tienne à la fois le budget CPU, le budget mémoire et le contrat produit, puis la coder en JavaScript sur plusieurs modules. Enfin, il faut sortir de l'état mixte actuel (156 PoP en v2) par un chemin de déploiement et de retour arrière qui ne réaffecte pas les utilisateurs déjà exposés.

### Preuves


Expériences actives du 23/09 au 29/09 : utilisateurs uniques par population de PoP, p du test χ² de SRM, et entre parenthèses les utilisateurs multi-variantes :
```text
Expérience (tenant)          Allocation   v1 seul              v2 seul              v1 et v2
exp-checkout-v7 (t-0193)     50/50        2 959 711 · p=0,49   1 122 649 · p<1e-6   117 640 · p<1e-6 (1 906)
exp-reco-carousel (t-0193)   34/33/33     1 761 742 · p=0,72     668 251 · p<1e-6    70 007 · p<1e-6 (2 065)
exp-trial-length (t-0877)    80/20          388 150 · p=0,31     146 077 · p<1e-6    21 930 · p<1e-6 (1 206)
exp-search-v12 (t-0193)      50/50        2 572 105 · p=0,58     975 695 · p=0,44   102 200 · p=0,61 (4)
```
Part « contrôle » de exp-checkout-v7 : 50,02 % (v1 seul), 51,62 % (v2 seul), 50,82 % (v1 et v2, après exclusion des multi-variantes). Avant le 21/09, 0,004 % des utilisateurs exposés recevaient plus d'une variante, à cause des changements de configuration.


Expositions brutes de deux utilisateurs multi-variantes :
```text
2026-09-24T08:12:41.207Z pop=CDG3 eval=v1 t=t-0193 flag=exp-checkout-v7 cfg=4412 key=u_7f3a91 variant=treatment rule=0
2026-09-24T19:40:05.913Z pop=MRS1 eval=v2 t=t-0193 flag=exp-checkout-v7 cfg=4412 key=u_7f3a91 variant=control rule=2
2026-09-25T07:55:13.022Z pop=CDG3 eval=v1 t=t-0193 flag=exp-checkout-v7 cfg=4412 key=u_7f3a91 variant=treatment rule=0
2026-09-26T12:03:44.480Z pop=FRA2 eval=v2 t=t-0877 flag=exp-trial-length cfg=918 key=acc_20931 variant=trial_30d rule=1
2026-09-26T12:09:02.117Z pop=AMS1 eval=v1 t=t-0877 flag=exp-trial-length cfg=918 key=acc_20931 variant=trial_14d rule=0
```

- Analyse de l'équipe data (28/09) sur les 5 177 utilisateurs multi-variantes des trois expériences en SRM : 71 % utilisent le SDK Android 5.2, publié le 14/09, qui modifie le cache local des variantes (38 % des exposés) ; 44 % sont passés par au moins trois PoP (1,9 % des exposés) ; 99,2 % satisfont au moins deux règles du flag concerné, réévaluées hors ligne sur la même cfg (6,1 % des exposés) ; 98,8 % ont des expositions divergentes portant la même cfg. L'équipe mobile soupçonne le SDK Android 5.2. Par ailleurs, bucketing.js a été réécrit pendant le projet v2 (portage de murmur3 avec Math.imul) et sert aux deux versions depuis le 15/09 ; comparé à l'ancien sur 10 M clés, il donne des seaux identiques.

Extraits de code (v2.3.0) :
```javascript
// compiler/compile.js — exécuté par le plan de contrôle à chaque publication
import { AttributeIndex } from './attribute-index.js';
import { isIndexable } from './ops.js';

export function compileFlag(flag) {
  const rules = flag.rules
    .map((rule, srcIndex) => ({ ...rule, srcIndex, arity: rule.clauses.length }))
    // Règles les plus sélectives d'abord : moins de clauses résiduelles évaluées
    // avant la sortie anticipée (banc t-0193 : -37 % de CPU d'évaluation).
    .sort((a, b) => b.arity - a.arity);
  const index = new AttributeIndex(rules.length);
  const residual = rules.map(() => []);
  rules.forEach((rule, ord) => {
    for (const c of rule.clauses) {
      if (isIndexable(c.op)) index.add(c.attr, c.values, ord, c.negate === true);
      else residual[ord].push(c);
    }
  });
  return { key: flag.key, salt: flag.salt, index: index.freeze(), residual,
           serves: rules.map((r) => r.serve), srcIndex: rules.map((r) => r.srcIndex),
           fallthrough: flag.fallthrough, format: 2 };
}

// edge/evaluate-v2.js
export function evaluateFlag(cf, ctx) {
  const cand = cf.index.candidates(ctx); // Uint32Array : bit ord à 1 si les clauses indexées de la règle sont satisfaites
  for (let w = 0; w < cand.length; w++) {
    for (let word = cand[w]; word !== 0; word &= word - 1) {
      const ord = (w << 5) | (31 - Math.clz32(word & -word));
      if (cf.residual[ord].every((c) => matchClause(c, ctx))) {
        return serve(cf.salt, cf.serves[ord], ctx, cf.srcIndex[ord]);
      }
    }
  }
  return serve(cf.salt, cf.fallthrough, ctx, -1);
}

// edge/evaluate-v1.js
export function evaluateFlag(flag, ctx) {
  for (let i = 0; i < flag.rules.length; i++) {
    if (flag.rules[i].clauses.every((c) => matchClause(c, ctx))) {
      return serve(flag.salt, flag.rules[i].serve, ctx, i);
    }
  }
  return serve(flag.salt, flag.fallthrough, ctx, -1);
}
```


Mesures pour le tenant t-0193 (cfg 4412, du 26 au 28/09) :
```text
Mesure                                         PoP v1          PoP v2
Artefact de configuration                      25 Mo           71 Mo
CPU de chargement dans un isolate              58 ms           412 ms
Tas retenu après chargement                    36 Mo           118 Mo
CPU d'évaluation par requête, p50 / p99        1,9 / 7,8 ms    0,6 / 2,1 ms
Requêtes rejetées (> 10 ms de CPU)             0,04 %          0 %
Évictions d'isolates par PoP et par heure      0,3             14,6
Requêtes servies par un isolate froid          0,02 %          0,41 %
Latence de bout en bout p99 / p99,9            24 / 41 ms      27 / 455 ms
```
Instantané de tas v2 après chargement de t-0193 (2,1 M valeurs distinctes, 2,6 M occurrences flag × attribut × valeur) : (string) 2 184 551 objets, 49,7 Mo ; Map 2 318 objets, 31,4 Mo ; Uint32Array 2 318 objets, 12,4 Mo ; Array 214 880 objets, 15,9 Mo ; Object 198 402 objets, 6,2 Mo ; autres 2,6 Mo. Instantané v1 : Uint32Array des hachages triés 20,8 Mo ; objets des règles 9,1 Mo ; chaînes 3,9 Mo ; autres 2,2 Mo.

- Informations non disponibles : la politique d'éviction exacte de la plateforme (seuil, délai de grâce, prise en compte des isolates concurrents d'un même PoP) n'est pas documentée ; on ignore si des tenants ont modifié leurs règles depuis le 23/09 en réaction aux résultats observés ; la part des SDK clients qui mettent les variantes en cache local, et masquent ainsi une partie des changements vus par l'utilisateur, n'est pas mesurée.

### Contraintes

- faible consommation mémoire — tas plafonné à 128 Mo par isolate par la plateforme ; objectif ≤ 40 Mo pour la configuration chargée du plus gros tenant (t-0193 : 14 200 règles, 2,1 M valeurs distinctes) et ≤ 64 Mo pour l'ensemble des configurations d'un isolate ; ni WebAssembly ni module natif
- déploiement progressif — paliers de 1 %, 10 %, 50 % puis 100 % des 312 PoP, chacun tenu au moins 24 h ; passage au palier suivant seulement si aucune expérience active n'est en SRM du fait de la version (p > 0,001) et si les évictions d'isolates restent ≤ 0,5 par PoP et par heure
- rollback obligatoire — retour à l'évaluateur précédent sur tous les PoP d'un palier en ≤ 15 min, sans republier les configurations des tenants et sans réaffecter un utilisateur déjà exposé à une expérience en cours, sauf expérience explicitement invalidée par son propriétaire

### Objectifs

- Expliquer, preuves à l'appui, le SRM, les utilisateurs multi-variantes et la pression mémoire des isolates v2, en séparant faits établis, hypothèses et inconnues.
- Recenser tous les flags, tenants et utilisateurs dont le résultat a dépendu de la version d'évaluateur depuis le 21/09.
- Choisir, parmi au moins trois stratégies d'évaluation, celle qui respecte à la fois le contrat produit, le budget CPU et le budget mémoire, y compris avec un doublement des règles.
- Définir la sortie de l'état mixte (poursuite du déploiement ou retour arrière) sans réaffecter d'utilisateur déjà exposé, et décider du sort des trois expériences touchées.

### Livrables

- Note de diagnostic : mécanisme de chaque phénomène, hypothèses concurrentes examinées (SDK Android 5.2, bucketing, propagation des configurations), chacune confirmée ou réfutée par les preuves, inconnues, et méthode de recensement des flags touchés sur tous les tenants avec son coût de calcul.
- Comparaison d'au moins trois stratégies d'évaluation (par exemple parcours séquentiel optimisé, index inversé, structure de décision partagée, compilation paresseuse) : complexité en temps et en mémoire, mesures sur t-0193 et sur un jeu de règles doublé, coût de chargement, choix argumenté.
- Implémentation JavaScript multi-fichiers : compiler/ (compilation et sérialisation), edge/evaluate.js, edge/bucketing.js et edge/migration-shim.js (choix de version par PoP, lecture des deux formats d'artefact), avec des représentations mémoire justifiées pour V8.
- Tests : équivalence différentielle entre v1 et le nouvel évaluateur (propriétés sur des règles générées qui se chevauchent, rejeu de contextes réels), tests du bucketing, bancs de mémoire et de CPU exécutés sous les plafonds de l'isolate.
- Plan de migration et de retour arrière à partir de l'état actuel : traitement des utilisateurs déjà exposés à des variantes divergentes, décision sur les trois expériences, critères de passage de palier et d'arrêt, durée.

### Critères de réussite

- Équivalence : aucun écart de variante ni d'indice de règle source avec v1 sur le rejeu de 50 M contextes réels (7 jours, 20 plus gros tenants) et sur 10 M cas générés adverses (règles qui se chevauchent, négations, listes de plus de 100 000 valeurs).
- t-0193 : configuration chargée ≤ 40 Mo de tas, chargement ≤ 120 ms de CPU, évaluation ≤ 3 ms de CPU au p99, et ≤ 5 ms au p99 avec un jeu de règles synthétique doublé.
- À chaque palier : aucune expérience active en SRM attribuable à la version (p > 0,001 par population v1 et v2), utilisateurs multi-variantes ≤ 0,005 %, évictions ≤ 0,5 par PoP et par heure.
- Répétition de retour arrière sur 3 PoP : retour complet en ≤ 15 min et aucun utilisateur déjà exposé réaffecté dans les 48 h suivantes (mesuré sur les expositions), hors expériences invalidées par leur propriétaire.
- Recensement reproductible par script : il attribue une cause à chacun des 5 177 utilisateurs multi-variantes connus (version d'évaluateur, changement de cfg ou autre) et chiffre, flag par flag et pour tous les tenants, les utilisateurs dont la variante a dépendu de la version.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T004 — Refonte d'un pipeline learning-to-rank en Kotlin : shard géant, préemptions GPU et audit entre deux régions

| Axe | Valeur |
|---|---|
| Piste | Machine Learning |
| Domaine | MLOps et training pipelines |
| Type | ranking |
| Langage | Kotlin |
| Charge | production (10k req/s, 10 TB) |
| Architecture | multi-région actif/passif |
| Incident | hotspot sur une partition |
| Failure mode | perte d'un worker GPU en cours d'entraînement |
| Mode | refactorisation legacy |

### Contexte

Placelia est une place de marché généraliste d'environ 38 M d'offres actives. Son moteur sert environ 10 000 requêtes/s en pointe, pages de recherche et pages de catégorie confondues. Le classement vient d'un ranker neuronal listwise réentraîné chaque nuit à partir des journaux de clics (≈ 10 To conservés 90 jours). Un règlement sur la transparence du classement impose de pouvoir justifier, pour tout modèle mis en production, les données, la configuration, le code et l'évaluation qui l'ont produit ; ces pièces sont conservées 5 ans.

Le pipeline est orchestré par `ltr-pipeline`, un monolithe Kotlin de 9 ans. Chaque nuit à 00:30 UTC, il exporte une fenêtre glissante de 14 jours de journaux arrêtée à J−2 (≈ 182 M listes de résultats, ≈ 445 Go), la découpe en 64 shards et entraîne le modèle sur 8 workers GPU de la région active (eu-central). Il évalue ensuite le modèle, le publie, puis le réplique vers la région passive (eu-north). Le SLA exige un modèle disponible dans les deux régions 6 h après le début du run.

Sur les dix derniers runs (17–26/09), ce SLA a été manqué quatre fois. Le shard 17 pèse 167 Go pour une médiane de 4,4 Go. Chaque préemption d'un worker relance l'époque depuis le début. Le lien inter-régions coupe régulièrement les envois. Un essai hors production, qui plafonnait les requêtes les plus fréquentes, a raccourci l'entraînement mais dégradé certains segments ; il a été abandonné.

L'équipe Ranking Platform (5 personnes) veut refactoriser le pipeline sans casser ses trois équipes clientes ni la traçabilité réglementaire. Tu en es l'architecte.

### Architecture existante

- **ltr-pipeline** (Kotlin 1.9, JVM 17, Spring Boot 2.7) : étapes EXPORT → TRAIN → EVAL → PUBLISH dans un même processus ; état des runs dans PostgreSQL, en région active.
- **EXPORT** (job Spark 3.3 piloté en Kotlin) : une ligne par liste affichée, sur un échantillon de 4 % des sessions (items, positions, clics, achats, 180 features par item quantifiées sur 8 bits, Parquet), shard = `QueryKey.shardOf(rawQuery)`. Les statistiques par requête normalisée (normalisation des CTR, échantillonnage des négatifs) sont calculées dans le shard : toutes les listes d'une même requête normalisée doivent y rester. `QueryKey.normalize` sert aussi au service de features en ligne (priors de CTR par requête).
- **TRAIN** : job sur le cluster GPU (8 A100 sur nœuds préemptibles) exécutant `ranker-train` 1.8 (Python), figé car le serving lit son format de modèle. Une époque par run, départ à chaud depuis le modèle de la veille, checkpoint toutes les 2 000 étapes (27 Go, 3 min 20 s d'écriture, entraînement suspendu).
- **EVAL** : NDCG@10, global et par segment, sur les listes de la veille (J−1), exclues de la fenêtre d'entraînement.
- **PUBLISH** : enregistre le modèle en région active et écrit une ligne `audit_run` (URI du modèle, préfixe des shards réécrit chaque nuit, commit, URI du rapport). L'artefact (9,2 Go) part ensuite en un seul PUT vers eu-north ; en cas d'échec, nouvel envoi complet après 10 min.
- **API** : `POST /v1/pipelines/{id}/runs` et `GET /v1/runs/{runId}`, utilisées par Search Quality, Ads Relevance et Recommandations pour lancer des runs ad hoc et les suivre.

### Problème

Le retard chronique mêle trois causes qui interagissent : un shard hors norme, des reprises qui repartent de zéro et une réplication fragile. Il faut d'abord expliquer la taille du shard 17 et mesurer ce qu'elle coûte, en durée mais aussi dans la distribution des données réellement vues à l'entraînement et dans les métriques par segment.

Il faut ensuite refactoriser le monolithe par étapes : un partitionnement qui préserve les regroupements nécessaires aux statistiques par requête tout en bornant le plus gros shard, une reprise après perte de worker, une réplication tolérante aux coupures et une piste d'audit complète, sans rien changer au contrat de l'API. Enfin, il faut un protocole pour décider si les modèles du nouveau pipeline peuvent remplacer ceux de l'ancien, alors qu'aucune pondération métier entre segments n'est fixée.

### Preuves


Durées des dix derniers runs (h:min) :
```text
Run     Export  Entraîn.  Éval   Publi.  Total   Événements
17/09   0:58    3:06      0:22   0:12    4:38    —
18/09   1:01    5:28      0:23   0:27    7:19    worker-2 perdu au pas 16 900 ; 2 envois
19/09   1:00    3:09      0:22   0:12    4:43    —
20/09   1:03    3:10      0:22   0:12    4:47    —
21/09   1:02    5:43      0:23   0:44    7:52    worker-5 perdu au pas 18 400 ; 3 envois
22/09   1:04    3:11      0:23   0:12    4:50    —
23/09   1:05    3:12      0:23   1:27    6:07    6 envois
24/09   1:04    3:12      0:23   0:12    4:51    —
25/09   1:06    4:59      0:24   0:12    6:41    worker-7 perdu au pas 12 500
26/09   1:07    3:14      0:24   0:12    4:57    —
```


Journal du run du 21/09 :
```text
2026-09-21T00:30:00Z run r-0921 start window=2026-09-06..2026-09-19 eval_day=2026-09-20
2026-09-21T01:32:04Z EXPORT done shards=64 median=4.4GB (3m41s) max=shard-17 167.2GB (58m12s)
2026-09-21T01:32:40Z TRAIN submit workers=8 steps_per_epoch=23860 local_batch=2720 warm_start=r-0920
2026-09-21T03:59:51Z TRAIN worker-5 lost (node preempted) at step 18400, restarting epoch
2026-09-21T04:05:37Z TRAIN attempt 2 started at step 0
2026-09-21T07:15:22Z TRAIN done steps=23860
2026-09-21T07:38:30Z EVAL done day=2026-09-20 ndcg@10=0.4127
2026-09-21T07:46:37Z PUBLISH upload eu-north attempt 1 failed after 3.1GB: connection reset
2026-09-21T08:01:09Z PUBLISH upload eu-north attempt 2 failed after 6.8GB: timeout
2026-09-21T08:17:17Z PUBLISH upload eu-north attempt 3 ok (9.2GB)
2026-09-21T08:22:07Z PUBLISH done (eu-north registered, checksum ok) — run done in 7h52m07s
```


Tableau de bord qualité des données, shard 17 du run du 21/09. Ce tableau de bord masque les valeurs vides de `normalized_query`. Le shard contient 50,2 M listes et 38 912 requêtes normalisées distinctes, contre 2,1 M listes et environ 38 700 requêtes pour un shard médian. Requêtes en tête : « iphone » 1 912 440 listes (3,8 %), « parfum » 402 118, « dyson » 211 905, « manga » 187 330 ; les vingt premières totalisent 3,3 M listes (6,6 %). Search Quality attribue le déséquilibre à « iphone ». Échantillon brut du shard :
```text
list_id      page_type  raw_query   items
L-9f10c2e4   CATEGORY   null        48
L-9f10c2e9   SEARCH     "🔥🔥"       24
L-9f10c311   CATEGORY   null        40
L-9f10c3a0   SEARCH     "iPhone"    24
L-9f10c3b7   SEARCH     "???"       24
L-9f10c3c2   CATEGORY   null        36
```


Extraits de ltr-pipeline :
```kotlin
// export/QueryKey.kt (2017)
object QueryKey {
    private const val SEED = 0x2017DF00
    private val MARKS = Regex("\\p{Mn}+")
    private val NON_ALNUM = Regex("[^\\p{L}\\p{Nd} ]")
    private val SPACES = Regex("\\s+")

    fun normalize(raw: String?): String =
        Normalizer.normalize((raw ?: "").toLowerCase(Locale.ROOT), Normalizer.Form.NFD)
            .replace(MARKS, "")
            .replace(NON_ALNUM, " ")
            .replace(SPACES, " ")
            .trim()

    fun shardOf(raw: String?, shards: Int = 64): Int =
        Math.floorMod(Hashing.murmur3_32(SEED).hashBytes(normalize(raw).toByteArray(UTF_8)).asInt(), shards)
}

// pipeline/PlanStage.kt
val byWorker = shards.groupBy { it.index % workers }
val stepsPerEpoch = byWorker.values.maxOf { ws -> ws.sumOf { it.lists } }
    .let { (it + localBatch - 1) / localBatch }
// ranker-train 1.8 : un worker qui épuise ses shards avant la fin de l'époque les reprend depuis le début.

// pipeline/TrainStage.kt
override suspend fun run(ctx: RunContext): StageResult {
    repeat(MAX_ATTEMPTS) { attempt ->
        val job = cluster.submit(TrainSpec(ctx.shards, workers = 8, stepsPerEpoch = ctx.stepsPerEpoch,
            warmStart = ctx.previousModelUri, checkpointEvery = 2_000, workDir = ctx.workDir))
        when (val r = job.await()) {
            is JobResult.Succeeded -> {
                audit.record(ctx.runId, "TRAIN", mapOf("model" to r.modelUri, "attempt" to attempt + 1))
                return StageResult.Ok(r.modelUri)
            }
            is JobResult.WorkerLost -> {
                log.warn("worker ${r.worker} lost at step ${r.step}, restarting epoch")
                cluster.cleanup(job) // purge workDir
            }
            is JobResult.Failed -> return StageResult.Failed(r.reason)
        }
    }
    return StageResult.Failed("too many worker losses")
}
```


Essai hors production du 24/09, rejouant les données du run du 23/09 avec au plus 200 000 listes par requête normalisée, tirées au hasard. Les données passent de 182,5 M à 131,6 M listes, le worker le plus chargé de 23 860 à 6 590 pas, et l'entraînement dure 0 h 53. Évaluation sur les mêmes listes que le run de production du 23/09 (journée du 22/09) :
```text
Segment (part des listes d'évaluation)    Référence   Essai     Écart
Requêtes de tête, top 1 000 (31 %)        0,4680      0,4717    +0,8 %
Requêtes de traîne (44 %)                 0,3968      0,3909    −1,5 %
Pages de catégorie sans requête (25 %)    0,3710      0,3632    −2,1 %
NDCG@10 global                            0,4124      0,4090    −0,8 %
```
Écart-type jour à jour du NDCG@10 global de production sur 30 jours : 0,0021.


Contrat de l'API et informations manquantes. Extrait de réponse figée de GET /v1/runs/{runId} :
```json
{"runId": "r-0921", "status": "RUNNING", "stages": [{"name": "TRAIN", "status": "RUNNING", "progress": 0.77}], "modelUri": null, "auditId": "a-5c1e09"}
```
`status` ∈ {QUEUED, RUNNING, SUCCEEDED, FAILED} et `stages[].name` ∈ {EXPORT, TRAIN, EVAL, PUBLISH}. Le client d'Ads Relevance désérialise `stages[].name` dans une enum Kotlin stricte. Celui de Recommandations considère un run terminé dès que `modelUri` n'est plus nul. Non disponible : l'équipe qui a écrit ranker-train 1.8 a été dissoute, et sa documentation ne dit pas s'il sait reprendre en cours d'époque avec l'état du chargeur de données, ni changer de nombre de workers en cours de route. Aucune pondération métier n'est définie entre pages de catégorie et pages de recherche.


### Contraintes

- auditabilité complète — pour chaque modèle publié : lien vérifiable modèle ↔ données exactes (empreintes des shards) ↔ configuration ↔ commit ↔ rapport d'évaluation, conservé 5 ans et consultable depuis les deux régions ; toute reprise, tout rééchantillonnage et toute repondération doivent être enregistrés et rejouables
- réseau partiellement instable — lien eu-central ↔ eu-north à ≈ 25 Mo/s utiles, coupures de 30 s à 12 min ; 17 % des envois d'artefact (9,2 Go) ont échoué sur les 90 derniers jours, avec jusqu'à 5 échecs consécutifs
- compatibilité API stricte — POST /v1/pipelines/{id}/runs et GET /v1/runs/{runId}, utilisés par 3 équipes : noms, types et valeurs d'enum de la réponse figés ; seuls des champs optionnels peuvent être ajoutés, aucune nouvelle valeur d'enum

### Objectifs

- Expliquer la taille du shard 17 et chiffrer ses effets sur la durée des runs, sur la distribution des données vues par chaque worker et sur la qualité par segment, en séparant faits, hypothèses et inconnues.
- Tenir le SLA de 6 h malgré les préemptions et les coupures réseau, avec une perte de travail bornée et justifiée par un calcul.
- Refactoriser le monolithe par étapes réversibles, sans changer le contrat de l'API ni affaiblir la piste d'audit réglementaire.
- Définir comment juger qu'un modèle issu du nouveau pipeline peut remplacer l'ancien, segment par segment.

### Livrables

- Diagnostic chiffré : origine de la taille du shard 17 (avec les requêtes de vérification), effets sur la durée, sur les données vues par chaque worker et sur les métriques par segment ; examen de l'hypothèse « iphone » ; relecture de l'essai de plafonnement.
- Plan de refactorisation progressive : étapes extraites du monolithe, interfaces, ordre, bascule et retour arrière par étape, tests de contrat de l'API.
- Code Kotlin : clé de partitionnement et affectation des shards avec une borne sur le plus gros shard (algorithme et complexité), reprise après perte de worker (coroutines, idempotence, fréquence de checkpoint justifiée), réplication reprenable ; tests unitaires, tests de propriété sur l'intégrité des regroupements, injection de préemptions et de coupures.
- Conception de la piste d'audit : modèle de données, empreintes, enregistrement des reprises et des repondérations, cohérence entre régions malgré les coupures, rétention 5 ans.
- Protocole d'évaluation par segment et règle de décision explicite en l'absence de pondération métier, avec les questions à soumettre aux équipes métier.

### Critères de réussite

- Sur les dix runs du 17 au 26/09 rejoués, le plus gros shard reste ≤ 3 × la médiane et un test automatique prouve, à chaque run, qu'aucune clé de regroupement n'est répartie sur deux shards.
- Rejeu des dix runs avec les mêmes incidents injectés (pertes de worker aux mêmes pas, mêmes échecs d'envoi) : 10 sur 10 disponibles dans les deux régions en moins de 6 h, et une perte de worker coûte au plus 25 min.
- 100 % des requêtes et réponses des trois équipes clientes enregistrées sur 30 jours sont rejouées sans écart de schéma ; aucune nouvelle valeur d'enum n'est observable.
- Pour tout modèle publié, une requête unique restitue données, configuration, commit, reprises et rapport, avec un résultat identique dans les deux régions au plus 1 h après publication ; un rejeu à partir de ces pièces reproduit le NDCG@10 à ± 0,001.
- En shadow sur 7 runs consécutifs, aucun segment (tête, traîne, catégories) ne recule de plus de 0,003 de NDCG@10 par rapport à l'ancien pipeline, avec un intervalle de confiance à 95 % qui tient compte de la variabilité jour à jour.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T005 — Divergences silencieuses entre régions dans un moteur de séries temporelles Rust après l'arrivée d'un encodeur SIMD

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | debugging et root-cause analysis |
| Type | analyse de cause racine |
| Langage | Rust |
| Charge | prototype (10 req/s, 10 GB) |
| Architecture | monolithe modulaire |
| Incident | corruption logique de données |
| Failure mode | déploiement partiel |
| Mode | optimisation de performance |

### Contexte

Brumeo surveille des chambres froides et des entrepôts pour une quarantaine de clients : capteurs de température, d'humidité et d'ouverture de porte. Sa base de séries temporelles est un prototype maison en Rust, en production depuis début juillet. Elle gère 72 000 séries, reçoit ≈ 1 200 points/s en lots envoyés par des passerelles (≈ 10 requêtes/s) et stocke ≈ 9 Go compressés. Le volume croît de 40 % par mois.

Deux régions, eu-west et us-east, consomment indépendamment le même topic Kafka et encodent chacune leurs propres blocs. Chaque client lit dans sa région de rattachement ; en cas de panne, l'autre région doit pouvoir servir tout le monde.

La v0.9 apporte un encodeur SIMD (AVX2), écrit pour préparer la croissance et les imports d'historique : le débit d'encodage est multiplié par 3,1 au benchmark. Elle a été déployée en eu-west nœud par nœud : eu-west-1 le 09/09 à 10:40 UTC, eu-west-2 le 11/09 à 16:05. us-east, sur aarch64, reste en v0.8 en attendant un portage NEON. Le 12/09, le job d'anti-entropie entre régions a été désactivé.

Le 26/09, un client de logistique frigorifique signale qu'une excursion de température apparaît horodatée avant l'ouverture de porte qui l'a provoquée. Une comparaison ad hoc trouve alors des blocs dont le contenu décodé diffère d'une région à l'autre, alors que tous les CRC sont valides.

L'équipe compte deux ingénieurs. Tu mènes l'analyse et le correctif.

### Architecture existante

- **Monolithe modulaire** : un binaire Rust (stable 1.80) composé des crates `ingest`, `codec`, `storage`, `compaction`, `query` et `antientropy`. Chaque région a 2 VM de 4 vCPU : x86_64 en eu-west, aarch64 en us-east.
- **Ingestion** : topic Kafka de 24 partitions (clé = série, rétention 7 jours), un groupe de consommateurs par région ; une série appartient au nœud qui détient sa partition. Les blocs couvrent 2 h alignées sur UTC et sont scellés 5 min après la fin de la fenêtre ; les points plus tardifs attendent la compaction.
- **Format de bloc v3** (depuis v0.4, juin 2026) : en-tête (format_version, series_id, count, t_first, t_last, CRC32 de la charge utile), section horodatages (premier delta sur 14 bits, puis delta-of-delta en codes préfixés), section valeurs (XOR des f64). Le bloc ne porte ni version d'encodeur ni identifiant de nœud ; le décodeur est commun à toutes les versions.
- **Compaction nocturne** (fenêtre 02:00–04:00 UTC) : décode les 12 blocs de 2 h de la veille et les points tardifs, fusionne, trie par horodatage, dédoublonne et réencode un bloc de 24 h. Les blocs de 2 h sont supprimés 7 jours plus tard.
- **Anti-entropie** : chaque nuit, comparait les CRC32 des blocs homologues des deux régions et alertait en cas d'écart.

### Problème

Il faut établir le mécanisme exact des divergences et le démontrer au bit près sur un bloc. Il faut aussi expliquer pourquoi ni les CRC, ni les tests existants, ni l'ancienne anti-entropie ne l'ont révélé. Vient ensuite le périmètre : tous les blocs touchés, y compris ceux produits par la compaction et ceux écrits pendant le déploiement nœud par nœud, à réparer à partir des sources encore disponibles.

Le correctif doit conserver le gain de performance qui justifiait la v0.9 et permettre à us-east de converger vers la même logique. Il doit s'accompagner de garde-fous peu coûteux, rester à la portée de deux ingénieurs et tenir la croissance prévue.

### Preuves


Commit qui a désactivé l'anti-entropie :
```text
commit 7c1e9a2  2026-09-12 09:14 UTC
    antientropy: désactive la comparaison inter-régions des CRC de blocs

    Depuis v0.9, les CRC diffèrent sur ~71 % des blocs (encodage des valeurs
    différent mais équivalent). Trop de faux positifs : on coupe en attendant
    une comparaison sémantique.
```


Extraits du crate `codec` :
```rust
// crates/codec/src/ts_simd.rs — v0.9 (PR #212 « encodeur SIMD »)
/// Seaux de delta-of-delta : (min, max, préfixe, bits du préfixe, bits de la valeur),
/// d'après l'article Gorilla (VLDB 2015, § 4.1.1).
const DOD_BUCKETS: [(i64, i64, u64, u32, u32); 3] = [
    (-63, 64, 0b10, 2, 7),
    (-255, 256, 0b110, 3, 9),
    (-2047, 2048, 0b1110, 4, 12),
];

#[inline(always)]
fn push_dod(w: &mut BitWriter64, dod: i64) {
    if dod == 0 {
        return w.push(0, 1);
    }
    for &(lo, hi, prefix, plen, vlen) in DOD_BUCKETS.iter() {
        if (lo..=hi).contains(&dod) {
            let v = (dod as u64) & ((1u64 << vlen) - 1);
            return w.push((prefix << vlen) | v, plen + vlen);
        }
    }
    w.push(0b1111, 4);
    w.push(dod as i32 as u32 as u64, 32);
}

/// Deltas et delta-of-delta calculés quatre par quatre (AVX2), codes émis ensuite un par un.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn encode_timestamps_avx2(ts: &[i64], w: &mut BitWriter64) {
    let dods = dod_lanes_avx2(ts); // dods[0] = premier delta
    w.push(dods[0] as u64, 14);
    for &dod in &dods[1..] {
        push_dod(w, dod);
    }
}

pub fn encode_timestamps(ts: &[i64], w: &mut BitWriter64) {
    #[cfg(target_arch = "x86_64")]
    if is_x86_feature_detected!("avx2") {
        return unsafe { encode_timestamps_avx2(ts, w) };
    }
    crate::ts::encode_timestamps_scalar(ts, w) // encodeur des versions v0.4 à v0.8
}

// crates/codec/src/ts.rs — décodeur commun, inchangé depuis v0.4
fn read_dod(r: &mut BitReader) -> Result<i64, DecodeError> {
    let width = match r.read_unary_prefix(4)? { // nombre de 1 avant le premier 0, au plus 4
        0 => return Ok(0),
        1 => 7,
        2 => 9,
        3 => 12,
        _ => 32,
    };
    Ok(sign_extend(r.read_bits(width)?, width))
}

#[inline]
fn sign_extend(raw: u64, width: u32) -> i64 {
    let shift = 64 - width;
    ((raw << shift) as i64) >> shift
}
```


Bloc de la série s-40117 (sonde de température d'une chambre froide, pas nominal de 60 s), fenêtre du 24/09 de 06:00 à 08:00 UTC. Les en-têtes sont identiques dans les deux régions, hors CRC : format_version=3, count=119, t_first=1790229612 (06:00:12Z), t_last=1790236756 (07:59:16Z). Les CRC32 sont valides des deux côtés. Les sections de valeurs ont des octets différents mais se décodent à l'identique. Sections d'horodatages (25 octets, bit de poids fort en premier) :
```text
eu-west  00000000  00 f0 00 00 10 1b f4 04 00 00 00 00 00 14 0d c0
         00000010  00 00 00 08 15 f2 04 00 00
us-east  00000000  00 f0 00 00 10 1b f4 04 00 00 00 00 00 18 81 40
         00000010  00 00 00 08 15 f2 04 00 00
```


Comparaison sémantique ad hoc du 28/09 (décodage des blocs homologues dans les deux régions) :
```text
Population                                              Échantillon   Divergents
Blocs de 2 h encore présents (écrits du 21/09 au 28/09)   1 200 000     241 (0,020 %)
Blocs de 24 h compactés avant le 09/09                      100 000       0
Blocs de 24 h compactés depuis le 10/09                     150 000     390 (0,26 %)
```
Premier écart d'horodatage (eu-west − us-east) dans les 241 blocs de 2 h divergents : −128 s (234 blocs), −512 s (6), −4 096 s (1). L'écart grandit ensuite jusqu'à la fin du bloc, et dans 64 % de ces blocs les horodatages décodés en eu-west ne sont plus croissants. 3,3 % des blocs divergents contiennent des points tardifs, contre 3,1 % de l'ensemble des blocs. L'équipe a d'abord soupçonné le chemin XOR des valeurs, entièrement réécrit par la PR, puis le traitement des points tardifs (le consommateur us-east accuse jusqu'à 40 s de retard).


Performances mesurées :
```text
Criterion, 1 cœur, blocs réels de 120 points   x86_64 (eu-west)   aarch64 (us-east)
encode_block scalaire (v0.4 à v0.8)             4,8 M points/s     4,1 M points/s
encode_block AVX2 (v0.9)                       14,9 M points/s     —
decode_block (commun)                           7,1 M points/s     6,3 M points/s
```
Taille moyenne : 1,41 octet par point en v0.8, 1,33 en v0.9. Import de référence (1,8 Md de points depuis un fichier local, mono-thread) : 11 min 40 s en v0.8, 7 min 26 s en v0.9. Compaction nocturne du 28/09 : 26 min dans chaque région, dont 88 % d'attente d'E/S (lecture des 864 000 blocs de 2 h de la veille) ; décodage et encodage pèsent chacun moins de 2 % de la durée.

- Rétention et traçabilité : Kafka garde 7 jours (rien avant le 22/09) ; les blocs de 2 h disparaissent 7 jours après leur compaction ; les journaux d'affectation des partitions sont conservés 14 jours (rien avant le 15/09). Entre le 09/09 10:40 et le 11/09 16:05, les partitions étaient réparties entre eu-west-1 (v0.9) et eu-west-2 (v0.8), avec trois rééquilibrages lors des redémarrages ; l'affectation exacte sur cette période n'est plus connue. Les exports CSV faits par les clients européens depuis le 09/09 ne sont pas journalisés.

### Contraintes

- forte croissance des données — +40 % de points par mois : ≈ 1 200 points/s et ≈ 9 Go compressés aujourd'hui, ≈ 6 500 points/s fin février 2027 ; trois imports d'historique de 2 à 6 Md de points chacun prévus d'ici décembre
- équipe réduite — 2 ingénieurs, dont un à mi-temps sur le support ; 10 jours-personne au plus pour le correctif, la réparation et les garde-fous ; aucune étape manuelle de nuit (pas d'astreinte)
- multi-région — eu-west (x86_64) et us-east (aarch64) ingèrent indépendamment le même topic Kafka ; chacune doit pouvoir servir seule tous les clients après une bascule DNS de ≤ 10 min, avec des données sémantiquement identiques ; aucune des deux ne fait autorité par construction

### Objectifs

- Démontrer le mécanisme des divergences et caractériser exactement les entrées qui les déclenchent, en séparant faits, hypothèses et inconnues.
- Délimiter et réparer tous les blocs touchés dans les deux formats (2 h et 24 h), y compris sur la période du déploiement nœud par nœud, avec une procédure automatisée et vérifiable.
- Corriger l'encodeur sans perdre le gain de performance, faire converger les deux régions vers la même logique et rendre toute récidive détectable à faible coût.
- Garantir que la compaction et les imports tiennent la croissance prévue sur le matériel actuel.

### Livrables

- Analyse de cause racine : mécanisme démontré au bit près sur le bloc s-40117 (premier point faux, valeur lue et valeur attendue), caractérisation exacte des entrées concernées, raisons pour lesquelles CRC, tests et anti-entropie ne l'ont pas détecté, examen des hypothèses « chemin XOR » et « points tardifs ».
- Périmètre et réparation : algorithme d'identification des blocs touchés (2 h, 24 h, période du 09/09 au 11/09), source de vérité retenue pour chaque cas et ses limites, procédure idempotente et automatisée avec vérification, liste des clients à prévenir.
- Correctif Rust : correction du codec qui conserve le gain de la v0.9, décision argumentée pour aarch64 (portage NEON ou maintien du scalaire), traçabilité de la version d'encodeur sans casser les lecteurs du format v3, vérification intégrée peu coûteuse ; benchmarks Criterion avant et après.
- Tests : propriétés d'aller-retour encodage/décodage sur des distributions adverses (proptest), test différentiel croisé x86_64/aarch64, fuzzing du décodeur, test de non-régression sur le bloc s-40117.
- Garde-fous et capacité : anti-entropie sémantique (ce qu'elle compare, tolérance aux points tardifs, coût), alerte, et plan pour que la compaction et les imports tiennent la croissance jusqu'à fin février 2027.

### Critères de réussite

- Après réparation, aucune divergence sémantique entre régions sur 100 % des blocs écrits depuis le 09/09 (2 h et 24 h), vérifiée par la nouvelle anti-entropie et non par échantillon.
- Tests de propriété : 10^8 séquences générées (pas réguliers et irréguliers, trous, sauts jusqu'aux limites de i32) plus un balayage exhaustif de tous les delta-of-delta de −10 000 à +10 000, sans aucun écart d'aller-retour sur x86_64 comme sur aarch64 ; le bloc s-40117 réparé se décode à l'identique de sa copie us-east.
- Après correctif, encodage (vérification intégrée comprise) ≥ 14 M points/s sur x86_64 au benchmark actuel ; surcoût de cette vérification ≤ 5 % ; import de référence ≤ 7 min 45 s.
- Anti-entropie sémantique : 100 % des blocs scellés couverts, alerte moins de 3 h après l'écriture d'un bloc divergent, aucun faux positif sur 7 jours malgré des encodages différents, ≤ 5 % d'un vCPU par région en moyenne.
- Compaction d'un volume synthétique 5,4 fois supérieur à celui du 28/09 en ≤ 2 h sur le matériel actuel.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T006 — Revue du harnais d'évaluation Swift d'un détecteur de fraude Core ML démenti par la production

| Axe | Valeur |
|---|---|
| Piste | Machine Learning |
| Domaine | model evaluation et robustness |
| Type | anomaly detection |
| Langage | Swift |
| Charge | extreme-scale (1M+ req/s, 1 PB+) |
| Architecture | service mesh |
| Incident | leakage découvert après mise en production |
| Failure mode | panne d'un nœud |
| Mode | code review |

### Contexte

Pactéo est une néobanque européenne de 34 M clients. Son app iOS évalue sur l'appareil, avec un modèle Core ML nommé fraudnet, le risque de chaque paiement (≈ 9,6 M par jour, taux de fraude ≈ 0,09 %) et de chaque connexion. Les 60 M appareils enrôlés remontent une télémétrie comportementale de 0,75 M événements/s en moyenne et 1,3 M/s en pointe ; 1,4 Po en sont conservés 120 jours.

Le harnais d'évaluation est écrit en Swift. Il réutilise le paquet RiskFeatures de l'app pour que les features soient calculées exactement comme sur l'appareil, et tourne sur une ferme de 40 Mac mini, Core ML n'existant que sur les plateformes Apple.

fraudnet-7 a tourné en mode shadow du 15 juin au 7 septembre 2026, puis a été activé le 8 septembre sur la foi d'une AUC-PR hors ligne de 0,61. Trois semaines plus tard, l'équipe Risque estime son AUC-PR en production à environ 0,23. Elle met en cause une évolution des tactiques de fraude depuis l'été ; l'équipe mobile soupçonne plutôt la conversion en Float16. Le 14 septembre, la panne d'un nœud du cache de réputation a en outre privé une partie des appareils de leurs features serveur pendant 36 min.

La PR #4127 « eval-harness v3 » doit faire de ce harnais la porte de validation officielle. Elle accompagne fraudnet-8, que l'équipe veut livrer dans la version 7.40 de l'app. Tu es le relecteur principal de la PR et tu portes la recommandation de livraison.

### Architecture existante

- **App iOS (Swift 6, iOS 17+)** : RiskFeatures calcule 53 features locales (cadence de saisie, contexte réseau, historique sur l'appareil). RiskClient obtient 11 features serveur de reputation-svc, dont chargebacks30d, avec un budget de 30 ms. fraudnet (.mlmodelc de 4,8 Mo, 64 entrées) produit un score ; deux seuils publiés dans RemoteConfig déclenchent une authentification renforcée (step-up) ou un refus.
- **Maillage de services (Istio/Envoy, mTLS)** : reputation-svc (Go) lit repcache, un cache en mémoire de 24 nœuds en hachage cohérent, sans réplica. Sur échec, il interroge Cassandra avec un budget de 8 ms, sinon la feature est renvoyée absente. reputation-svc ne sert que l'état courant ; ses changements sont publiés dans le topic reputation-changes, conservé 30 jours. fallback-scorer (GBDT) note côté serveur les paiements arrivés sans score appareil.
- **Labels** : ChargebackStore reçoit les rétrofacturations des réseaux de cartes jusqu'à 90 jours après le paiement, avec leur date d'arrivée.
- **Entraînement** : pipeline Python (PyTorch, conversion par coremltools), alimenté par le split train que le harnais exporte en Parquet.
- **Déploiement** : l'app 7.3x télécharge par OTA un .mlmodelc signé si sa signature d'entrée est identique à FeatureSchema.v7 ; tout changement d'entrées exige une nouvelle version de l'app.

### Problème

Il faut établir si les métriques hors ligne de fraudnet-7 et de fraudnet-8 ont une valeur. Pour chaque biais identifié, il faut en donner le sens et un ordre de grandeur, et le rattacher à un endroit précis du code de la PR ou à une propriété des données. Les remarques de revue doivent être classées (bloquant, majeur, mineur) et chacune doit s'appuyer sur un effet mesurable ou sur un test qui le démontre.

Il faut ensuite un protocole d'évaluation qui prédise la performance en production, y compris lorsque des features serveur manquent, que ce soit pendant une panne ou dans d'autres circonstances.

Enfin, il faut décider de ce qui part dans la 7.40, de ce qui peut suivre par OTA ou côté serveur, et du sort de fraudnet-7 et de ses seuils d'ici là, sans sortir du budget de latence ni fragiliser l'autorisation des paiements.

### Preuves


Description de la PR et métriques rapportées :
```text
PR #4127 « eval-harness v3 » — équipe Risk ML, 2 fichiers, +214 −37, ouverte le 2026-09-26
« v3 calcule les features comme l'app (RiskFeatures + vrai client réputation) et recalcule
chargebacks30d depuis ChargebackStore. Extraction du 2026-09-25 : 24,1 M paiements (échantillon
de 1,4 % des appareils, 180 jours). Le split train est exporté vers le pipeline d'entraînement ; le rapport JSON
alimente la publication des seuils RemoteConfig. Utilisé depuis mai sur la branche
risk/eval-v3 pour fraudnet-7 et fraudnet-8. » Durée d'une exécution complète : ≈ 31 h.

Modèle       Source                     AUC-PR   Rappel à 1 % FPR   Seuil step-up   Positifs
fraudnet-7   harnais v3 (split test)    0,61     0,44               0,37            3 641
fraudnet-8   harnais v3 (split test)    0,64     0,49               0,34            3 641
fraudnet-7   estimation production*     ≈ 0,23   ≈ 0,17             0,37            —
* équipe Risque, paiements du shadow du 15/06 au 31/07, labels d'au moins 60 jours ; requête non
  archivée ; traitement des paiements bloqués ou challengés par fraudnet-6 non documenté
```


Premier fichier de la PR :
```swift
// Sources/EvalHarness/DatasetBuilder.swift (PR #4127)
import Foundation
import RiskFeatures

struct LabeledEvent: Sendable {
    let eventID: String
    let deviceID: String
    let timestamp: Date
    let features: FeatureVector
    let isFraud: Bool
}

struct DatasetBuilder {
    let reputation: ReputationClient      // même client que l'app, pointé sur reputation-svc interne
    let chargebacks: ChargebackStore
    let extractor = FeatureExtractor()

    func build(_ events: [RiskEvent]) async throws -> (train: [LabeledEvent], test: [LabeledEvent]) {
        let now = Date()
        let last30d = DateInterval(start: now.addingTimeInterval(-30 * 86_400), end: now)
        var rows: [LabeledEvent] = []
        rows.reserveCapacity(events.count)
        for event in events {
            guard let rep = try? await reputation.fetch(deviceID: event.deviceID) else { continue }
            var f = extractor.localFeatures(for: event)
            f.merge(rep.features) { local, _ in local }
            f["chargebacks30d"] = try await Double(chargebacks.count(deviceID: event.deviceID, in: last30d))
            let fraud = try await chargebacks.exists(paymentID: event.id)
            rows.append(LabeledEvent(eventID: event.id, deviceID: event.deviceID,
                                     timestamp: event.timestamp, features: f, isFraud: fraud))
        }
        let mixed = rows.shuffled()
        let cut = mixed.count * 8 / 10
        return (Array(mixed[..<cut]), Array(mixed[cut...]))
    }
}
```


Second fichier de la PR, et fonction du paquet partagé qu'il appelle :
```swift
// Sources/EvalHarness/EvalRunner.swift (PR #4127)
import CoreML
import Foundation
import RiskFeatures

struct EvalRunner {
    let model: MLModel
    let reportURL: URL      // lu par le job publish-thresholds

    func run(train: [LabeledEvent], test: [LabeledEvent]) throws -> EvalReport {
        let scored: [(score: Double, fraud: Bool)] = try test.map { row in
            let input = try MLDictionaryFeatureProvider(dictionary: row.features.coreMLInputs())
            let out = try model.prediction(from: input)
            return (out.featureValue(for: "fraud_prob")!.doubleValue, row.isFraud)
        }
        let curve = PRCurve(scored)                  // points triés par score décroissant
        let report = EvalReport(
            model: model.modelDescription.metadata[.versionString] as? String ?? "?",
            aucPR: curve.trapezoidArea,
            recallAt1pctFPR: curve.recall(atFalsePositiveRate: 0.01),
            stepUpThreshold: curve.threshold(atFalsePositiveRate: 0.01),
            blockThreshold: curve.threshold(atFalsePositiveRate: 0.0005),
            positives: scored.filter { $0.fraud }.count)
        try JSONEncoder().encode(report).write(to: reportURL)
        return report
    }
}

// Packages/RiskFeatures/Sources/FeatureVector.swift (inchangé, partagé avec l'app)
extension FeatureVector {
    public func coreMLInputs() -> [String: MLFeatureValue] {
        Dictionary(uniqueKeysWithValues: FeatureSchema.v7.names.map {
            ($0, MLFeatureValue(double: self[$0] ?? 0))
        })
    }
}
```


Données, labels et journalisation :
```text
Délai paiement → rétrofacturation (fraudes 2025, n = 2,9 M) : 65 % sous 30 j, 91 % sous 60 j, 99,2 % sous 90 j
Extraction du 2026-09-25 : 0,38 M appareils distincts, 63 paiements par appareil en moyenne ;
  0,4 % des appareils portent 63 % des fraudes labellisées ;
  âge des paiements : 17 % de moins de 30 j, 17 % de 30 à 60 j, 66 % de plus de 60 j
Rapport fraudnet-7 (harnais v3) : chargebacks30d est la feature la plus importante (sa permutation retire 0,29 d'AUC-PR)
reputation-svc répond 404 pour les appareils effacés à la demande du client (RGPD) :
  0,6 % des appareils de l'extraction brute, 4,8 % de ceux qui ont au moins une fraude
Journalisation des 64 entrées telles que servies au modèle : depuis l'app 7.36 (3 août, 88 % des appareils
  actifs aujourd'hui) ; avant cette version, seuls les scores (fraudnet-6 actif, fraudnet-7 en shadow) l'étaient
deviceID : sa persistance après désinstallation puis réinstallation de l'app n'est pas documentée
  (identifierForVendor ou UUID en trousseau selon les versions de RiskFeatures)
```


Panne du nœud repcache-17, le 14/09 :
```text
2026-09-14T14:02:11Z repcache-17     kernel: watchdog: BUG: soft lockup - CPU#6 stuck for 23s
2026-09-14T14:02:19Z istio-proxy     outlier_detection ejected 10.42.17.9:6380 cluster=repcache consecutive_5xx=5
2026-09-14T14:02:20Z reputation-svc  WARN repcache miss -> cassandra fallback p99=41ms budget=8ms partial=true
2026-09-14T14:38:47Z repcache-17     rejoined ring, warm-up 0/1.9M keys

Fenêtre 14:02–14:38, comparée au même créneau du lundi 07/09 :
paiements dont les 11 features serveur sont absentes (imputées à 0)   4,1 %    (0,1 %)
vérification complète p99                                             44 ms    (31 ms)
fail-open (> 50 ms)                                                   0,04 %   (0,01 %)
fraudes confirmées à ce jour dans la fenêtre : 131
  features complètes : 107, détectées (step-up ou refus) : 53
  features absentes  :  24 (issues de 9 appareils), détectées : 5
Hors panne (semaine du 21/09) : features serveur absentes pour 0,1 % des paiements,
  et pour 2,7 % des paiements des appareils que l'app signale comme jailbreakés.
```
Une partie de l'équipe attribue la hausse de latence aux relances Envoy vers reputation-svc (retries: 2, perTryTimeout: 12ms).


Latence et parc d'appareils :
```text
Inférence Core ML p99 (ms), appareils de test sous iOS 18.6
Puce    Part des appareils actifs    fraudnet-7    fraudnet-8
A12     11 %                         11,8          17,2
A13     14 %                         9,6           13,9
A15     31 %                         5,1           7,4
A17+    44 %                         3,2           4,6
Écart de score Core ML (Float16, Neural Engine) / référence PyTorch Float32 sur 100 k paiements :
  médiane 2e-4, maximum 3,1e-3
Adoption d'une nouvelle version de l'app : 52 % à J+7, 81 % à J+21
```


### Contraintes

- p99 très faible — vérification de risque complète ≤ 50 ms p99 sur l'appareil, au-delà de quoi le paiement part sans score appareil (fail-open) ; appel à reputation-svc ≤ 30 ms p99 à travers le maillage ; inférence Core ML ≤ 15 ms p99 sur A12, la puce la plus ancienne supportée (11 % des appareils actifs)
- fenêtre de migration courte — gel du code de la version 7.40 le 8 octobre 2026, dans 9 jours ; revue App Store d'environ 2 jours ; aucune version de l'app entre la 7.40 et le 12 janvier 2027 ; après le gel, seul un modèle aux entrées inchangées peut être poussé par OTA
- SLA élevé — autorisation des paiements disponible à 99,99 % par mois (≈ 4,3 min d'indisponibilité) ; une panne de la détection ne doit jamais bloquer un paiement ; refus à tort ≤ 0,05 % des paiements légitimes

### Objectifs

- Qualifier chaque défaut de la PR #4127 par son effet sur les métriques (sens, ordre de grandeur, population touchée) et le classer, en séparant ce qui est démontré, ce qui est probable et ce qui reste inconnu.
- Définir un protocole d'évaluation qui prédise la performance en production à partir des labels et des historiques de features réellement disponibles.
- Rendre mesurable, puis borner, la dégradation du détecteur quand des features serveur manquent, sans compromettre l'autorisation des paiements.
- Arrêter ce qui part dans la 7.40, ce qui suit par OTA ou côté serveur, et ce qu'il advient de fraudnet-7 et de ses seuils d'ici là.

### Livrables

- Revue de la PR #4127 : commentaires ancrés sur les lignes concernées, classés bloquant / majeur / mineur, chacun avec son effet attendu sur les métriques et le test ou la mesure qui le démontre.
- Protocole d'évaluation corrigé et code Swift correspondant, avec les invariants qu'il garantit et des tests unitaires sur données synthétiques datées qui les vérifient.
- Estimation révisée de fraudnet-7 et fraudnet-8 avec intervalles de confiance, explication chiffrée de l'écart avec l'estimation de production et liste de ce qu'il faudrait connaître de sa méthode.
- Plan de robustesse aux features manquantes : scénarios d'injection (panne d'un nœud, absence totale, absences concentrées sur certains appareils), options côté modèle, app et serveur, avec leur coût en latence.
- Plan de livraison daté jusqu'au gel du 8 octobre : contenu de la 7.40, actions OTA et RemoteConfig, critères go/no-go et retour arrière.

### Critères de réussite

- Chaque remarque bloquante est accompagnée d'un test automatisé qui échoue sur le code de la PR et passe sur le code corrigé ; deux exécutions du harnais corrigé sur la même extraction produisent un rapport identique octet pour octet.
- Appliqué à fraudnet-7 sur les paiements du shadow, le protocole produit une AUC-PR dont l'intervalle de confiance à 95 % (rééchantillonnage par appareil) contient l'estimation de production recalculée par une méthode documentée, ou l'écart restant est attribué et chiffré.
- Au rejeu de la panne du 14/09 et d'une panne simulée d'un nœud sur 24, le rappel à 1 % de FPR sur les paiements touchés reste à au moins 90 % de celui obtenu sur ces mêmes paiements avec leurs features complètes, et 100 % des paiements sans features serveur complètes reçoivent un score appareil ou serveur.
- Tout modèle livré aux appareils A12 tient 15 ms p99 d'inférence ; la vérification complète tient 50 ms p99 et le fail-open reste ≤ 0,05 % des paiements hors panne.
- Modèle et seuils réversibles en moins d'une heure sans nouvelle version de l'app ; plan validé avant le gel du 8 octobre 2026.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T007 — Protocole de livraison de webhooks : relances qui saturent en silence et doublons après une bascule de région

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | systèmes de décision sous incertitude |
| Type | optimisation sous contraintes |
| Langage | Java |
| Charge | production (10k req/s, 10 TB) |
| Architecture | microservices |
| Incident | file de messages qui croît silencieusement |
| Failure mode | panne d'une région |
| Mode | conception de protocole |

### Contexte

Ondalys est un prestataire de services de paiement qui notifie 22 140 endpoints marchands par webhooks : paiement autorisé, remboursement, litige, versement. Le dispatcher, un ensemble de microservices Java, effectue environ 10 000 tentatives de livraison par seconde en journée, dont 6 300 premières tentatives et 3 700 relances.

Depuis le 20 septembre 2026, rien d'anormal n'apparaît au tableau de bord : la profondeur de la file prête est stable et le retard du consommateur Kafka reste sous la seconde. Pourtant, la part des événements livrés en moins de 5 min aux endpoints sains est tombée de 99,95 % à 97,1 %. Une analyse a posteriori des sauvegardes Redis montre que le sorted set des relances est passé de 2,1 M à 41,7 M éléments en 9 jours.

Le 24 septembre, la région eu-1 a été perdue de 09:12 à 09:59 UTC. eu-2 a repris le service à 09:31 à partir d'un état Redis correspondant à 09:03:27. Environ 3,2 M webhooks ont alors été livrés deux fois, et 14 marchands qui ne dédupliquent pas ont expédié des commandes ou passé des écritures comptables en double.

Une partie de l'équipe impute la situation à Carrelune, une plateforme de places de marché dont 212 endpoints échouent depuis sa migration d'infrastructure du 21 septembre. La direction attend un protocole de livraison et de bascule qui ne change pas le contrat marchand et conserve Redis pendant les 9 prochains mois.

### Architecture existante

- **Ingestion** : topic Kafka merchant-events de 96 partitions (clé = merchantId), répliqué vers eu-2 par MirrorMaker 2.
- **webhook-dispatcher (Java 17, Spring Boot 2.7)** : 48 pods en eu-1. Chaque pod consomme 2 partitions et dispose d'une file prête de 250 livraisons et de 256 threads d'envoi (webhook-sender), soit 12 288 appels simultanés au plus. Après chaque lot consommé, l'offset Kafka est écrit dans Redis, dans la même transaction MULTI que les ZADD des livraisons différées du lot.
- **Relances** : sorted set Redis retry:delayed (score = échéance en ms, membre = clé de livraison), sur un primaire unique en eu-1 avec un réplica asynchrone en eu-2. Chaque pod exécute un poller toutes les 100 ms. Les corps d'événements sont dans PostgreSQL.
- **Journal** : table PostgreSQL delivery_attempts (une ligne par tentative, ≈ 8 To sur 30 jours), servie aux marchands par GET /v1/deliveries et répliquée vers eu-2 par réplication logique asynchrone.
- **Bascule** : manuelle, selon un runbook : promotion du réplica Redis, démarrage des pods en eu-2, reprise de Kafka aux offsets lus dans Redis.
- **Supervision** : queue.ready.depth (somme des 48 files prêtes), retard Kafka, taux de 2xx global. Ni retry:delayed ni l'état de la réplication Redis ne sont suivis.

### Problème

Il faut d'abord expliquer comment la file des relances a pu croître pendant 9 jours sans qu'aucun indicateur suivi ne bouge, pourquoi des endpoints sains en pâtissent, et s'il existe un lien entre cette croissance et le point de reprise de la bascule du 24 septembre.

Il faut ensuite concevoir un protocole de livraison qui décide, sous incertitude, quand un endpoint doit être traité comme lent, momentanément indisponible ou durablement en échec, et qui répartit une capacité d'envoi bornée entre marchands. Ce protocole doit tenir le SLA des endpoints sains et la promesse de 72 h faite à tous. Il doit couvrir la bascule entre régions avec une borne explicite sur les doublons, et fonctionner avec le Redis et le module d'envoi existants.

### Preuves


Relevé quotidien à 12:00 UTC (ZCARD et ZCOUNT reconstitués depuis les fichiers RDB, absents du tableau de bord) :
```text
Jour    queue.ready.depth   Retard Kafka   ZCARD retry:delayed   ZCOUNT échus (≤ now)   Sains livrés < 5 min
19/09   310 à 2 900         < 1 s          2,0 M                 0,01 M                 99,96 %
20/09   420 à 3 400         < 1 s          2,1 M                 0,01 M                 99,95 %
22/09   10 400 à 12 000     < 1 s          4,6 M                 0,3 M                  99,71 %
24/09   11 000 à 12 000     < 1 s          12,8 M                1,9 M                  98,90 %
26/09   11 000 à 12 000     < 1 s          25,1 M                4,2 M                  97,80 %
28/09   11 000 à 12 000     < 1 s          37,2 M                6,4 M                  97,10 %
29/09   11 000 à 12 000     < 1 s          41,7 M                6,9 M                  —
Compteur delivery.deferred (existant, non affiché) : 0 à 40/s jusqu'au 21/09, 2 100 à 2 600/s depuis le 23/09
Redis used_memory : 1,6 Go le 19/09, 7,1 Go le 29/09
```


Extraits du dispatcher (version 3.8) :
```java
// LaneWorker.java — une instance par pod
final class LaneWorker {
    private static final String DELAYED = "retry:delayed";
    private static final long BASE_DELAY_MS = 5_000, MAX_DELAY_MS = 6 * 3_600_000L;
    private static final Duration MAX_AGE = Duration.ofHours(72);
    private final BlockingQueue<Delivery> ready = new ArrayBlockingQueue<>(250);
    private final ExecutorService senders = Executors.newFixedThreadPool(256);

    void submit(Delivery d) {
        if (!ready.offer(d)) {
            redis.zadd(DELAYED, clock.millis() + 2_000, d.key());
            metrics.counter("delivery.deferred").increment();
        }
    }

    void onFailure(Delivery d, Outcome o) {
        if (clock.instant().isAfter(d.createdAt().plus(MAX_AGE))) { deadLetters.publish(d, o); return; }
        int attempt = d.attempt() + 1;
        long delay = Math.min(BASE_DELAY_MS * (1L << attempt), MAX_DELAY_MS) + jitter(0.2);
        redis.zadd(DELAYED, clock.millis() + delay, d.withAttempt(attempt).key());
    }
}

// DelayedPoller.java — une instance par pod, qui ne traite que ses 2 partitions
@Scheduled(fixedDelay = 100)
void drain() {
    for (String key : redis.zrangeByScore(DELAYED, 0, clock.millis(), 0, 2_000)) {
        if (!ownership.owns(DeliveryKey.partition(key))) continue;
        if (redis.zrem(DELAYED, key) == 1) lane.submit(deliveries.load(key));   // corps lu dans PostgreSQL
    }
}
```


Tentatives par catégorie d'endpoint, le 28/09 de 12:00 à 13:00 UTC (moyennes) :
```text
Catégorie                  Endpoints   Tentatives/s   dont relances   Latence moyenne   Succès
Sains                      19 930      5 760          90              0,24 s            99,3 %
Lents (p50 > 8 s)          1 900       690            210             8,2 s             64 %
Moins de 5 % de succès     310         3 550          3 400           1,45 s            1,1 %
Total                      22 140      10 000         3 700
```
Les 310 endpoints de la dernière ligne portent 88 % des éléments de retry:delayed, jusqu'à 412 000 pour un seul endpoint. Un événement destiné à un endpoint qui échoue toujours reçoit environ 23 tentatives en 72 h. Threads d'envoi occupés : 44 pods à 100 %, 4 pods entre 78 % et 97 %.


Historique de quelques endpoints sur les 72 dernières heures :
```text
ep-40117  Carrelune (1 des 212)   TLS handshake_failure depuis le 21/09 17:40, aucun succès ; aucune date de retour annoncée
ep-11873  Fromagerie Vasseur      503 de 01:00 à 04:30 chaque nuit, 99,8 % de succès le reste du temps
ep-20954  Ludinéo                 p50 9,1 s, 38 % de timeouts, chaque événement livré au 2e ou au 3e essai
ep-07731  Atelier Bruneau         410 Gone depuis le 12/09, abonnement toujours actif
ep-15602  Voyages Kerlan          aucun succès de 02:10 à 02:55 le 27/09, puis 97 %
```


Primaire Redis en eu-1 (client-output-buffer-limit replica 256mb 64mb 60 ; repl-backlog-size 64mb) et chronologie du 24/09 :
```text
41:M 24 Sep 2026 09:06:04.114 # Client id=88213 addr=10.8.2.14:41822 flags=S omem=268437504 cmd=psync scheduled to be closed ASAP for overcoming of output buffer limits.
41:M 24 Sep 2026 09:06:04.201 # Connection with replica 10.8.2.14:6379 lost.
41:M 24 Sep 2026 09:06:18.882 * Replica 10.8.2.14:6379 asks for synchronization
41:M 24 Sep 2026 09:06:18.882 * Unable to partial resync with replica 10.8.2.14:6379 for lack of backlog (Replica request was: 918224177365).
41:M 24 Sep 2026 09:06:18.883 * Starting BGSAVE for SYNC with target: disk
41:M 24 Sep 2026 09:11:52.610 * Background saving terminated with success
```
La même séquence (déconnexion puis resynchronisation complète de 7 à 14 min) apparaît 11 fois depuis le 21/09. Chronologie UTC : 09:12:03 perte de eu-1 ; 09:24 décision de bascule ; 09:31 réplica promu, 48 pods démarrés en eu-2, dernier offset Kafka lu dans Redis daté de 09:03:27 ; 09:57 pods de eu-1 mis à l'échelle zéro à la main ; 09:59 retour de eu-1. Doublons : ≈ 3,2 M livraisons dont le X-Event-Id avait déjà un 2xx dans delivery_attempts. Retard de la réplication PostgreSQL vers eu-2 au moment de la panne : non collecté.


Contrat webhooks v1 (publié en 2021) et enquête marchands :
```text
- POST JSON ; en-têtes obligatoires X-Event-Id (UUIDv4) et
  X-Signature-V1 = HMAC-SHA256(secret du marchand, X-Event-Id + "." + corps)
- réponse 2xx attendue sous 10 s ; tout autre code, ou le dépassement du délai, vaut échec
- livraison au moins une fois, relances pendant 72 h, aucun ordre garanti ;
  le marchand doit dédupliquer sur X-Event-Id
- ajout d'en-têtes optionnels autorisé ; les SDK marchands (Java, PHP, Node) ignorent les en-têtes inconnus
Enquête du 25/09 : 14 marchands ne dédupliquent pas (9 ont expédié des commandes en double,
5 ont doublé des écritures comptables). Aucune mesure n'existe de la dépendance réelle des
marchands à l'ordre des événements.
```


### Contraintes

- compatibilité API stricte — contrat webhooks v1 figé : corps JSON, en-têtes X-Event-Id et X-Signature-V1, réponse 2xx attendue sous 10 s, livraison au moins une fois avec relances pendant 72 h ; seuls des en-têtes optionnels peuvent être ajoutés ; GET /v1/deliveries (historique des tentatives exposé aux marchands) garde son schéma
- SLA élevé — 99,9 % des événements destinés à un endpoint sain livrés en moins de 5 min, mesuré par jour (sain : au moins 95 % de 2xx sur l'heure glissante précédente) ; bascule de région en moins de 15 min
- legacy non remplaçable à court terme — Redis 6.2 (primaire unique en eu-1, réplica asynchrone en eu-2, 25 Go de mémoire au plus) et le module d'envoi webhook-sender (Java 17, Apache HttpClient 4.5 bloquant, signature) restent en place au moins 9 mois ; ni Redis Cluster ni module Redis ; un nouveau composant en Java 21 peut être ajouté à côté

### Objectifs

- Expliquer, chiffres à l'appui, la croissance silencieuse de retry:delayed, la dégradation du SLA des endpoints sains et le point de reprise de la bascule du 24/09, en séparant faits, hypothèses et inconnues.
- Formuler l'allocation de la capacité d'envoi comme un problème d'optimisation sous contraintes, avec une règle explicite de classement d'un endpoint sous incertitude et le coût de chaque type d'erreur de classement.
- Spécifier un protocole de livraison et de bascule compatible avec le contrat v1 et le legacy, avec des bornes explicites sur les doublons et les pertes.
- Définir comment résorber le stock actuel de 41,7 M éléments sans rompre la promesse de 72 h ni dégrader davantage les endpoints sains.

### Livrables

- Note de diagnostic : mécanismes, calculs de capacité établis à partir des mesures fournies, hypothèses examinées avec un verdict chiffré pour chacune (dont celle qui impute tout à Carrelune) et mesures manquantes.
- Spécification du protocole : états d'un endpoint et transitions avec leurs seuils, ordonnancement des envois et des relances, en-têtes optionnels éventuels, procédure de bascule entre régions (état répliqué, protection contre le retour de l'ancienne région, reprise), invariants et borne de doublons.
- Formulation d'optimisation (variables, objectif, contraintes) et politique de décision sous incertitude, avec une analyse de sensibilité aux paramètres inconnus.
- Code Java 21 du cœur de l'ordonnanceur, intégré au Redis et au webhook-sender existants, avec tests unitaires et une simulation à événements discrets qui rejoue le profil du 20 au 29 septembre et une perte de région à un instant quelconque.
- Liste des métriques et alertes à ajouter, et runbook de bascule révisé.

### Critères de réussite

- Simulation du profil du 28/09 avec 12 288 appels simultanés : au moins 99,9 % des événements destinés aux endpoints sains livrés en moins de 5 min, globalement et sur chacun des 48 pods.
- Les endpoints en échec persistant consomment au plus 5 % de la capacité d'envoi ; quand l'un d'eux redevient disponible, son premier événement en attente part en moins de 5 min et tout événement dont l'échéance de 72 h tombe plus de 5 min après la reprise est livré avant cette échéance.
- Pire cas simulé (310 endpoints en échec pendant 72 h au débit du 28/09) : mémoire Redis ≤ 10 Go et aucune perte de synchronisation du réplica.
- Perte de eu-1 simulée à 50 instants aléatoires : aucun événement perdu, doublons limités à 5 s de livraisons réussies (≈ 31 000), service rétabli en moins de 15 min et aucun envoi depuis l'ancienne région après la bascule.
- Contrat v1 inchangé, vérifié par les tests de conformité des SDK Java, PHP et Node ; une croissance de retry:delayed comparable à celle du 20 au 29/09 déclenche une alerte en moins de 15 min.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T008 — Réacheminement de passagers pendant un orage : décisions non reproductibles au rejeu et schéma de données à reconcevoir

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | raisonnement logique et décision |
| Type | planification multi-objectifs |
| Langage | TypeScript |
| Charge | prototype (10 req/s, 10 GB) |
| Architecture | stream processing |
| Incident | saturation d'un sous-ensemble de nœuds |
| Failure mode | rejouement d'événements |
| Mode | conception de schéma de données |

### Contexte

Ventora est une compagnie aérienne régionale européenne de 72 appareils, avec des hubs à Lyon et à Nantes. Lors d'irrégularités d'exploitation (orage, grève, fermeture de piste), ses agents réacheminent aujourd'hui les passagers à la main. Depuis juillet 2026, un prototype en TypeScript automatise ce travail pour le hub de Lyon : il consomme un flux d'environ 10 événements/s en pointe, choisit un nouveau vol pour chaque réservation touchée, pose un blocage de sièges dans l'inventaire et déclenche la notification du passager.

Le 2 septembre 2026, un orage a fait annuler 118 vols à Lyon. Le prototype a produit 9 420 décisions pour 16 390 passagers. À 16:07 UTC, un incident réseau en eu-west-3 a entraîné une bascule vers eu-central-1 : 412 passagers ont alors reçu une seconde notification, dont 61 contradictoires avec la première. Le rejeu de la journée depuis l'archive du flux, avec le même code et les mêmes règles, donne 1 318 décisions différentes sur 9 420. Pendant le pic, trois partitions sur douze étaient saturées et la latence de décision atteignait 4,2 s au p99.

L'équipe propose de passer à 48 partitions et de doubler les instances avant d'étendre le système à tout le réseau, avec une cible de 2 000 passagers à réacheminer par minute au pic d'un orage. La direction des opérations refuse toute extension tant que les décisions ne sont pas reproductibles et justifiables : chaque réacheminement doit pouvoir être rejoué et expliqué à un passager comme à l'autorité de l'aviation civile.

### Architecture existante

- **Flux** : cluster Kafka en eu-west-3, topic irops-events de 12 partitions, clé = numéro de vol + date. Trois systèmes sources y publient FlightCancelled, FlightDelayed, SeatInventoryChanged et BookingChanged. MirrorMaker 2 le réplique vers eu-central-1. L'archive est conservée 30 jours (≈ 9 Go).
- **rebook-engine (Node.js 22, TypeScript 5.5)** : un processus mono-vCPU par partition. L'état (blocages actifs, décisions en attente de confirmation) est en mémoire, avec un snapshot vers PostgreSQL et un commit des offsets toutes les 5 min.
- **Services appelés** : système de réservation (réservations d'un vol), horaires (alternatives à 1 ou 2 segments sur 30 h), inventaire (disponibilités, blocages de 90 s via l'API HTTP de l'éditeur).
- **Règles** : fichier YAML versionné, chargé au démarrage : contraintes dures, priorités et poids.
- **Notifications** : le service de notification consomme RebookingDecided et envoie un SMS, un push et un e-mail par événement reçu.
- **Bascule** : eu-central-1 garde 12 consommateurs à froid qui chargent le dernier snapshot et reprennent le flux répliqué aux offsets correspondants.

### Problème

Il faut établir pourquoi une même journée ne produit pas les mêmes décisions, pourquoi la bascule a produit des notifications contradictoires et pourquoi trois partitions saturent quand les autres sont presque inactives, puis dire si la proposition de l'équipe répond à ces problèmes.

Le livrable central est un schéma de données : événements, décisions, blocages d'inventaire, notifications, et toute entité supplémentaire jugée nécessaire. Il doit rendre chaque décision reproductible et justifiable, supporter le rejeu et la bascule sans effet visible pour le passager, et permettre un partitionnement qui tienne la latence cible. La formulation multi-objectifs doit traiter les cas où aucune option ne respecte toutes les règles, et distinguer ce que l'ingénierie peut trancher de ce qui revient au métier.

### Preuves


Événements du 02/09, tels qu'archivés :
```json
{"type":"FlightCancelled","flight":"VT3312","date":"2026-09-02","origin":"LYS","destCity":"BIQ","std":"2026-09-02T14:20:00+02:00","reason":"WX","emittedAt":"2026-09-02T11:43:57.120Z","pax":164}
{"type":"SeatInventoryChanged","flight":"VT3316","date":"2026-09-02","cabin":"Y","available":3,"source":"inv-gw","ts":1788349432806}
{"type":"RebookingDecided","pnr":"J3XW9P","from":"VT3312","to":"VT3316|2026-09-02","holdTtlMs":90000,"region":"eu-west-3","at":"2026-09-02T11:43:57.294Z"}
```


Rejeu du 02/09 depuis l'archive (410 000 événements, 0,7 Go), code 0.9.4 et règles 2026-08-28.3 inchangés, simulateur d'inventaire alimenté par les SeatInventoryChanged archivés ; décisions appariées par réservation et événement déclencheur ; heures de vol locales ; « partition » = celle de l'événement déclencheur :
```text
Vitesse   Écart avec la production    Écart entre deux rejeux à la même vitesse
×1        9,8 %                       5,9 %
×8        14,0 % (1 318 / 9 420)      6,1 %
×32       21,5 %                      6,4 %

PNR      Production                                   Rejeu ×8                                 Note
QX4T7A   VT1402 LYS→ORY 17:05                         VT1502 LYS→CDG 17:05                     score identique : 62,0
J3XW9P   VT3316 LYS→BIQ 16:40                         aucune option                            VT3316 vu à 3 sièges en production, à 1 au rejeu
M2VD8R   VT3317 BIQ→LYS arr. 18:40 (partition 4)      VT3317 BIQ→LYS arr. 18:40 (partition 4)  correspondance dont les deux vols sont annulés ;
         + VT1402 LYS→ORY dép. 17:05 (partition 9)    + VT1410 LYS→ORY dép. 18:05 (part. 9)    deux notifications en production
```


Extrait du moteur :
```ts
// src/engine/rebook.ts — rebook-engine 0.9.4
export async function onFlightCancelled(ev: FlightCancelled, ctx: Ctx): Promise<void> {
  const pnrs = await ctx.pss.pnrsOn(ev.flight, ev.date);
  const alts = await ctx.schedule.alternatives(ev.origin, ev.destCity, ev.std, { maxLegs: 2, horizonH: 30 });
  const options = new Map<string, Option>();
  await Promise.all(alts.map(async (alt) => {
    const inv = await ctx.inventory.availability(alt.legs);
    options.set(alt.key, { ...alt, free: inv.minFree - ctx.holds.activeSeats(alt.legs, Date.now()) });
  }));
  for (const pnr of [...pnrs].sort(byStatusThenBookingDate)) decide(pnr, ev, options, ctx);
}

export async function onSeatInventoryChanged(ev: SeatInventoryChanged, ctx: Ctx): Promise<void> {
  for (const d of ctx.pending.touching(ev.flight)) {
    if (ev.available >= ctx.holds.activeSeats([ev.flight], Date.now())) continue;
    decide(d.pnr, d.trigger, await ctx.optionsFor(d.pnr, d.trigger), ctx);
  }
}

function decide(pnr: Pnr, trigger: FlightCancelled, options: Map<string, Option>, ctx: Ctx): void {
  let best: { opt: Option; score: number } | undefined;
  for (const opt of options.values()) {
    if (opt.free < pnr.pax.length || !rules.hardOk(pnr, opt)) continue;
    const score = rules.weights.delay * opt.arrivalDelayMin
                + rules.weights.status * statusPenalty(pnr)
                + rules.weights.downgrade * opt.cabinDowngrades;
    if (!best || score < best.score) best = { opt, score };
  }
  if (best) {
    best.opt.free -= pnr.pax.length;
    ctx.holds.place(best.opt.legs, pnr.pax.length, Date.now() + 90_000);   // fire-and-forget : ne pas ralentir la boucle de décision
  }
  const decision: RebookingDecided = { type: "RebookingDecided", pnr: pnr.locator, from: trigger.flight,
    to: best ? best.opt.key : null, holdTtlMs: 90_000, region: ctx.region, at: new Date().toISOString() };
  ctx.pending.upsert(pnr.locator, decision);
  ctx.emit("irops-decisions", pnr.locator, decision);
}
```


Jeu de règles en vigueur et cas remonté par l'escale de Lyon :
```yaml
# rules/2026-08-28.3.yaml (extrait)
version: "2026-08-28.3"
hard:
  MCT: { domestic: 40, schengen: 50, non_schengen: 70 }   # minutes
  UMNR: "mineur non accompagné : vol direct uniquement, arrivée avant 21:00 locale"
  FAMILY: "les passagers d'une même réservation comprenant un enfant ne sont jamais séparés"
priority:
  - "Platinum et Gold sont servis avant les autres statuts (engagement du programme de fidélité)"
  - "Les mineurs non accompagnés passent avant tout autre passager (procédure sol LYS-OPS-114)"
weights: { delay: 1.0, status: 40.0, downgrade: 25.0 }
```
Après l'annulation de VT3312 (LYS→BIQ 14:20), VT3316 (16:40, dernier direct arrivant avant 21:00) avait 3 sièges libres et VT3318 (19:55, arrivée 21:15) en avait 2 ; le direct suivant partait le lendemain à 07:10. Parmi les passagers concernés : R8NC1D (Platinum, seul), une famille de quatre répartie sur deux réservations liées (K7Q2LM : un parent Gold et deux enfants ; K7Q2LN : l'autre parent) et le mineur non accompagné J3XW9P. En production, R8NC1D, J3XW9P et K7Q2LN ont été placés sur VT3316, K7Q2LM via ORY avec une arrivée à 22:35 ; l'escale a replacé la famille à la main le lendemain. La documentation métier se limite à ce fichier.


Partitions pendant le pic du 02/09 (15:30 à 16:30 UTC) :
```text
Partition   Clés les plus actives   Événements/s   dont SeatInventoryChanged   CPU        Retard max (messages)   Décision p99
2           VT1402, VT1502          3,9            91 %                        100 %      41                      4,2 s
7           VT1410, VT3316          3,1            88 %                        100 %      33                      3,7 s
9           VT1406, VT1398          2,7            90 %                        98 %       24                      3,1 s
9 autres    —                       0,05 à 0,3     35 à 60 %                   2 à 7 %    < 5                     0,18 s
Profil CPU (partition 2) : 64 % dans decide() et rules.hardOk, 14 % JSON.parse, 11 % ramasse-miettes
71 % des SeatInventoryChanged du pic suivent de moins d'une seconde, sur le même vol, un blocage posé par rebook-engine
```


Bascule du 02/09 et dépendances :
```text
16:07:55 UTC  perte du cluster de flux en eu-west-3
16:09:40 UTC  bascule déclenchée
16:10:52 UTC  les 12 consommateurs de eu-central-1 chargent le snapshot PostgreSQL de 16:03:10
              et reprennent le flux répliqué aux offsets correspondants
Notifications : un envoi par RebookingDecided reçu, sans clé d'idempotence ; 412 passagers ont reçu
  une seconde notification, dont 61 contradictoires avec la première
Inventaire : l'API de l'éditeur n'accepte pas de clé d'idempotence ; son comportement face à deux
  blocages identiques posés depuis deux régions n'est pas documenté
Archive : horodatages mixtes selon la source (ISO 8601 ou epoch en ms), aucun numéro de version de schéma
```


### Contraintes

- multi-région — deux régions, eu-west-3 (active) et eu-central-1 (passive) ; flux répliqué par MirrorMaker 2 avec un retard p99 de 2 s ; système de réservation et inventaire (éditeur, hors périmètre) centralisés à Paris, à 9 ms aller-retour de eu-central-1
- résilience à la panne d'une région — reprise en moins de 2 min après la perte de la région active ; aucune décision déjà notifiée ne doit être contredite, aucun siège bloqué deux fois pour un même passager, aucune décision perdue
- p99 très faible — ≤ 300 ms p99 entre la réception d'une annulation et l'émission de la décision de chaque réservation concernée, au rythme cible de 2 000 passagers/min, sur toutes les partitions ; les blocages de sièges de l'inventaire durent 90 s

### Objectifs

- Expliquer les trois symptômes (divergence au rejeu, notifications contradictoires après la bascule, saturation de trois partitions) à partir des preuves, et évaluer la proposition de l'équipe.
- Concevoir un schéma de données qui rend chaque décision reproductible, justifiable et sûre face au rejeu et à la bascule de région.
- Formuler le choix de réacheminement comme un problème multi-objectifs explicite, traiter les cas infaisables et isoler les questions qui relèvent du métier.
- Choisir un partitionnement et un modèle d'exécution qui tiennent 300 ms au p99 au rythme cible.

### Livrables

- Diagnostic écrit : mécanisme de chaque symptôme, preuves utilisées, hypothèses écartées et avis motivé sur le passage à 48 partitions.
- Schéma de données complet : types TypeScript et schémas validés à l'exécution pour chaque entité, règles d'évolution des versions et stratégie de lecture des archives existantes.
- Fonction de décision en TypeScript, avec les propriétés qu'elle garantit, et tests de rejeu qui établissent que sa sortie ne dépend que des entrées enregistrées.
- Formulation multi-objectifs justifiée (lexicographique, pondérée ou hybride), traitement des cas infaisables et questions à trancher par le métier, illustrées sur les cas du 02/09.
- Protocole de bascule et de rejeu (ce qui est recalculé, ce qui est relu, comment une décision notifiée est préservée, comment un blocage n'est jamais posé deux fois) et plan de test de charge au rythme cible.

### Critères de réussite

- Le 02/09 rejoué deux fois à ×1, ×8 et ×32 produit des enregistrements de décision identiques octet pour octet dans toutes les exécutions.
- 50 bascules simulées à des instants aléatoires du rejeu : aucune notification contradictoire, aucun siège bloqué deux fois pour un même passager, aucune décision perdue, reprise en moins de 2 min.
- Aucune décision émise ne viole MCT, UMNR ou FAMILY ; chaque cas infaisable aboutit à une décision explicite de prise en charge par un agent, qui cite les règles en conflit.
- Pic du 02/09 extrapolé à 2 000 passagers/min : décision ≤ 300 ms au p99 sur chaque partition, CPU ≤ 70 % par processus.
- Les 410 000 événements archivés du 02/09 sont relus sans perte par les nouveaux consommateurs, et l'empreinte de chaque décision suffit à retrouver ses entrées exactes.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T009 — Clause d'un autre client dans un résumé juridique : forensique d'un cache KV partagé entre deux régions actives

| Axe | Valeur |
|---|---|
| Piste | Machine Learning |
| Domaine | deep learning |
| Type | NLP long-context |
| Langage | Python |
| Charge | high-scale (100k req/s, 100 TB) |
| Architecture | multi-région actif/actif |
| Incident | régression de sécurité |
| Failure mode | partition réseau |
| Mode | forensic debugging |

### Contexte

Cartulis fournit à 640 clients (cabinets, assureurs, directions juridiques) une plateforme d'analyse de contrats longs, jusqu'à 128 k tokens. La passerelle reçoit ≈ 100 k req/s en pointe, dont ≈ 1 800 req/s de génération longue (`summarize`) et ≈ 6 k req/s de revues de clauses isolées (`clause-review`). Les documents stockés représentent ≈ 100 To. Deux régions actif/actif, eu-west et eu-central, servent chacune leurs clients rattachés.

Le 15/09, la version 2.4 du moteur d'inférence `lexserve` a introduit la « déduplication des clauses types » : découpage des documents aligné sur les clauses, et réutilisation, d'un document à l'autre, du cache KV des blocs présents dans un catalogue de 1,9 M clauses fréquentes. Activée le jeudi 17/09 à 06:00 UTC, elle a fait passer le taux de hit du cache de 31 % à 58 %.

Le lundi 21/09 à 08:45 UTC, le client T-0412 signale qu'un résumé produit le 18/09 attribue une clause de non-concurrence « au profit de Delmar SAS, pendant 24 mois », alors que son contrat désigne Orlane Logistique pour 18 mois. À 13:00, l'équipe sécurité confirme que ces deux éléments figurent dans le document D-77-5531 du client T-0077, l'un des 38 clients sous isolation stricte. L'article 11 est identique mot pour mot dans les deux contrats ; il renvoie au « Bénéficiaire » et à « la durée fixée à l'article 2.4 », définis ailleurs dans chaque document.

Il est 15:00 UTC ; tu pilotes l'enquête forensique, la notification, la remédiation et sa vérification. Travail strictement défensif : aucune reproduction hors d'un environnement de test isolé sur données synthétiques.

### Architecture existante

- **lexserve** (Python 3.11, PyTorch) : modèle de 34 Md de paramètres, 48 couches, cache KV en fp8 (96 Kio par token). Par région, 256 nœuds de 8 GPU, deux réplicas TP4 par nœud, jusqu'à 48 séquences simultanées par réplica.
- **Cache de préfixes** : le gabarit place le document avant l'instruction et le segmenteur coupe toujours à cette frontière, en blocs de 256 tokens au plus. Leurs KV sont stockés dans un magasin NVMe régional (≈ 560 To, ≈ 31 M entrées) partagé par tous les réplicas, via un index régional : clé de 8 octets → emplacement, région d'origine, date de création, dernier accès, nombre de hits. Le cache est activable par pool et par API via la configuration.
- **Inter-régions** : les entrées chaudes (≈ 6 % de l'index) sont répliquées vers l'autre région pour absorber une bascule ; la configuration est diffusée par gossip (`cfgd`), avec un numéro de version par changement.
- **Isolation stricte** : les 38 clients concernés ont un pool dédié (nœuds n001 à n048 de chaque région), qui consulte l'index régional commun en vertu de la décision ARCH-114 (mars 2026) : « les clés sont des empreintes, aucune donnée client n'est partagée ».
- **Canari** : 2 000 requêtes/h par région (résumés et revues de clauses) sur des contrats synthétiques ; l'alerte QA-ENT-01 suit la part de réponses citant une entité absente du document source.

### Problème

Un cas confirmé ne dit ni combien de clients sont touchés, ni depuis quand, ni si l'exposition a cessé. Il faut reconstituer les fenêtres d'exposition réelles de chaque région, en tenant compte de la divergence de configuration autour de la partition réseau du 18/09 et de la réplication de l'index. Il faut ensuite établir quelles requêtes ont pu recevoir des informations issues du document d'un autre client, par quelle voie, et quels clients sont source, destinataires, ou les deux.

Les journaux utiles expirent avant l'échéance de notification, n'identifient pas le client et ne peuvent pas être recoupés avec les documents déjà supprimés. Il faut enfin faire cesser toute réutilisation contaminée sans purge totale du cache, dans un créneau de déploiement de 3 h et sur un lien inter-régions toujours instable, puis démontrer, région par région, que la remédiation est effective.

### Preuves


Journaux de configuration et de réseau (UTC) :
```text
2026-09-17T06:00:03Z cfgd[ew] CFG-2291 set kv.clause_dedup=true scope=global version=4471
2026-09-17T06:00:09Z cfgd[ec] CFG-2291 applied version=4471 nodes=256/256
2026-09-17T22:50:00Z netmon eu-west<->eu-central loss=1-9% (TR-5520)
2026-09-18T01:10:00Z alert QA-ENT-01 eu-west batch=daily window=24h value=2.1% threshold=1.0%
2026-09-18T01:10:00Z alert QA-ENT-01 eu-central batch=daily window=24h value=2.4% threshold=1.0%
2026-09-18T01:30:12Z cfgd[ew] CFG-2297 set kv.clause_dedup=false scope=global version=4472
2026-09-18T01:30:41Z cfgd[ew] CFG-2297 applied eu-west nodes=256/256
2026-09-18T01:33:12Z cfgd[ew] gossip eu-central ack timeout (3/3), deferred to anti-entropy
2026-09-18T02:10:07Z netmon eu-west<->eu-central unreachable
2026-09-18T02:31:40Z cfgd[ec] CFG-2299 set kvstore.evict_watermark=0.82 scope=eu-central version=4472
2026-09-18T02:55:31Z netmon eu-west<->eu-central restored
2026-09-18T02:55:40Z kvrepl[ec->ew] resume backlog entries=104870 (1.9 TB)
2026-09-18T04:20:17Z kvrepl[ec->ew] backlog drained
2026-09-18T07:33:12Z cfgd[ew] anti-entropy eu-central digest version=4472 == local 4472: in sync
2026-09-19T01:10:00Z alert QA-ENT-01 eu-central batch=daily window=24h value=2.8% threshold=1.0%
2026-09-19T11:40:02Z cfgd[ec] CFG-2297 applied eu-central nodes=256/256 (forced push, audit AUD-0919)
```


Dérivation des clés et planification du prefill (lexserve 2.4) :
```python
# lexserve/kvcache/keys.py
_DIGEST_BYTES = 8

def block_key(model_id: str, parent: bytes | None, tokens: Sequence[int],
              *, clause_dedup: bool = False) -> bytes:
    h = hashlib.blake2b(digest_size=_DIGEST_BYTES, person=b"lexkv-v3")
    h.update(model_id.encode())
    if parent is not None and not clause_dedup:
        h.update(parent)
    h.update(np.asarray(tokens, dtype=np.int32).tobytes())
    return h.digest()

# lexserve/kvcache/manager.py
def plan_prefill(self, req: Request) -> PrefillPlan:
    plan, parent, chain_ok = PrefillPlan(), None, True
    segments = self.segmenter.split(req.doc_tokens, clause_aligned=self.cfg.clause_dedup)
    for i, seg in enumerate(segments):
        dedup = self.cfg.clause_dedup and self.catalog.contains(seg.digest)
        key = block_key(self.model_id, parent, seg.tokens, clause_dedup=dedup)
        entry = self.index.lookup(key) if (chain_ok or dedup) else None
        if entry is not None:
            plan.reuse(i, entry, pos=seg.start, rope_delta=seg.start - entry.start_pos)
        else:
            chain_ok = False
            plan.compute(i, key=key, pos=seg.start)
        parent = key
    return plan
```


Extraits de kvtrace (une ligne par opération sur un bloc ; `seq` est local au réplica) et de la passerelle :
```text
2026-09-17T09:14:52.118Z ec ec-n041-r1 seq=551902 insert blk=38 key=a41f0c9e27d3b815 dedup=1 origin=ec pos=9143 entry_pos=9143
2026-09-18T07:48:09.004Z ew ew-n133-r1 seq=413377 hit    blk=0  key=a41f0c9e27d3b815 dedup=0 origin=ec pos=0    entry_pos=9143
2026-09-18T16:05:31.640Z ec ec-n117-r0 seq=880413 hit    blk=21 key=a41f0c9e27d3b815 dedup=1 origin=ec pos=5087 entry_pos=9143
2026-09-18T16:05:31.652Z ec ec-n117-r0 seq=880413 insert blk=22 key=0be7d51c9a6f2e40 dedup=0 origin=ec pos=5268 entry_pos=5268

2026-09-18T07:48:08.871Z gw req=r-2c90aa tenant=T-0203 api=clause-review region=ew replica=ew-n133-r1 doc=- prompt_tokens=233 temp=0
2026-09-18T16:05:31.402Z gw req=r-7f31c2 tenant=T-0412 api=summarize region=ec replica=ec-n117-r0 doc=D-412-0918 prompt_tokens=41877 temp=0 t_end=16:05:49.915Z
```


Taux de hit du cache et indicateur du canari (part des réponses citant une entité absente du document source) :
```text
Période (UTC)               eu-west                     eu-central
                            drapeau  hit   canari       drapeau  hit   canari
16/09 (référence)           off      31 %  0,4 %        off      30 %  0,4 %
17/09 06:00 → 18/09 01:30   on       57 %  2,6 %        on       58 %  2,9 %
18/09 01:30 → 02:10         off      33 %  0,5 %        on       58 %  3,0 %
18/09 02:10 → 03:20         off      34 %  0,6 %        on       n/d   n/d
18/09 03:20 → 19/09 11:40   off      36 %  0,9 %        on       57 %  2,8 %
19/09 11:40 → 21/09 14:00   off      32 %  0,5 %        off      34 %  0,7 %
```
n/d : métriques d'eu-central non reçues (agrégées en eu-west, tampon de l'agent saturé). En eu-west, la part des hits servis par des entrées d'origine eu-central était de 0,2 % le 16/09, de 1,7 % du 18/09 03:20 au 19/09 11:40 et de 1,1 % depuis. Volumes `summarize` : ≈ 54 M/jour en eu-west et ≈ 45 M/jour en eu-central ; eu-central en a servi ≈ 93 M entre le 17/09 06:00 et le 19/09 11:40, dont 61 % avec au moins un hit sur un bloc du catalogue.


Inventaire des données disponibles pour l'enquête :
```text
Source                     Rétention                    Contenu et limites
kvtrace (Parquet)          7 j, partition du jour J     ts, région, réplica, seq, op, blk, clé, dedup, origine, pos, entry_pos ;
                           purgée à J+7 05:30 UTC       ni client ni request_id ; ≈ 1,6 To et ≈ 48 G lignes pour 7 jours
Journal de la passerelle   90 j                         request_id, client, API, région, réplica, t_début, t_fin,
                                                        prompt_tokens, doc_id, gabarit, température
Correspondance seq → req   journal DEBUG                échantillon de 1 % des séquences
Documents et résultats     politique du client ; 30 j   112 clients en mode éphémère (document et résultat supprimés après
                           pour les résultats           réponse) : 23 % des requêtes summarize, 41 % des clause-review
Index du cache             —                            ni client ni version du format de clé par entrée
```
Machine d'analyse isolée : 64 cœurs, 512 Go de RAM, sans GPU. Le DPO autorise le calcul automatisé d'empreintes sur les documents conservés, sans lecture humaine hors cas confirmés. 8 % des requêtes `summarize` utilisent l'option « rédaction » (température 0,7, graine non journalisée), les autres un décodage glouton.

- Cellule de crise de 14:00 : l'équipe plateforme soupçonne une collision de clés (8 octets, ≈ 62 M entrées dans les deux index) ; le SRE soupçonne un « split-brain » de l'index répliqué pendant la partition ; l'équipe modèle rappelle que « Delmar SAS » figure dans 212 documents conservés de 9 clients et y voit une hallucination favorisée par le réalignement de position des blocs réutilisés. Capacité : une purge totale du magasin KV ferait monter la charge GPU de 38 % au pic, avec retour à la normale en ≈ 36 h ; la marge au pic est de 20 % ; SLO : p99 du premier token `summarize` < 4 s. L'API de l'index supprime ≈ 40 k entrées/s par région, par clé uniquement ; aucun outil de purge sélective n'existe.

### Contraintes

- multi-tenant — 640 clients, dont 38 sous isolation stricte : aucune donnée dérivée de leurs documents, cache compris, ne doit servir à un autre client ; chaque client concerné, source ou destinataire, doit être notifié individuellement avant le jeudi 24/09 13:00 UTC ; la direction juridique exclut une notification indifférenciée des 640 clients
- fenêtre de migration courte — un seul créneau de déploiement de code du moteur avant le gel de fin de trimestre : mercredi 23/09 01:00–04:00 UTC ; ensuite, jusqu'au 05/10, seules les modifications de configuration et les opérations sur l'index sont permises ; redémarrage d'un nœud ≈ 7 min, au plus 5 % des nœuds d'une région à la fois
- réseau partiellement instable — jusqu'au 30/09 au moins, le lien eu-west ↔ eu-central perd 0,5 à 4 % des paquets et subit des coupures de 30 s à 3 min (incident de transit TR-5520) ; la diffusion de configuration et la réplication de l'index peuvent diverger sans alerte ; chaque région doit pouvoir être confinée, corrigée et vérifiée de façon autonome

### Objectifs

- Reconstituer une chronologie vérifiable et les fenêtres d'exposition réelles de chaque région, en évaluant chiffres à l'appui les hypothèses de la cellule de crise et en séparant faits établis, hypothèses et inconnues.
- Établir le périmètre : requêtes, clients sources et clients destinataires, classés par niveau de certitude, à partir de données partielles qui expirent et sans lecture humaine des documents clients.
- Faire cesser toute réutilisation contaminée et rétablir l'isolation contractuelle des 38 clients stricts, sans purge totale ni violation du SLO, dans les contraintes de déploiement et de réseau.
- Démontrer, région par région, que la remédiation est effective et qu'une récidive serait détectée.

### Livrables

- Rapport forensique : chronologie horodatée, voies d'exposition et fenêtres par région, évaluation chiffrée des trois hypothèses de la cellule de crise, inconnues restantes et mesures permettant de les réduire.
- Pipeline Python d'attribution (kvtrace, passerelle, empreintes recalculées depuis les documents conservés) : conception, code des étapes clés, règles de classement, estimation de durée et de mémoire sur la machine d'analyse, plan de gel des preuves et registre de conservation.
- Dossier de notification : critères d'inclusion par niveau de certitude, contenu type pour un client source et pour un client destinataire, traitement des clients en mode éphémère, calendrier compatible avec l'échéance du 24/09.
- Correctif Python de la couche de cache de `lexserve`, compatible avec des versions mixtes pendant le déploiement : mesures de confinement applicables immédiatement sans redéploiement, correction durable conforme aux engagements d'isolation, purge sélective des entrées suspectes, tests unitaires et tests de propriété sur corpus synthétique, plan de déploiement dans le créneau du 23/09 avec retour arrière.
- Protocole de vérification et de surveillance continue (invariants, métriques, alertes) et recommandation argumentée sur l'avenir de la déduplication des clauses.

### Critères de réussite

- Toutes les partitions kvtrace depuis le 16/09 et les journaux associés sont gelés avant la purge du 23/09 05:30 UTC, avec empreintes SHA-256 et registre de conservation (qui, quand, quoi).
- 100 % des requêtes servies entre le 17/09 06:00 UTC et la fin de la remédiation sont classées (exposition certaine, probable, possible, écartée) par des règles écrites et reproductibles ; la part attribuée à un client de façon exacte est chiffrée ; le pipeline s'exécute en ≤ 10 h sur la machine d'analyse avec ≤ 400 Go de RAM.
- Liste de notification (clients source et destinataires, période, volume, niveau de certitude, limites connues) validée par le juridique avant le 24/09 13:00 UTC ; aucun client écarté sans règle traçable.
- Confinement effectif dans les deux régions avant le 22/09 00:00 UTC sans redéploiement ; correctif déployé dans le créneau du 23/09 avec au plus 5 % des nœuds d'une région redémarrés simultanément ; surcharge GPU au pic ≤ +15 % dans chaque région et p99 du premier token `summarize` < 4 s pendant la réchauffe.
- Vérification autonome par région, sans s'appuyer sur `cfgd` : zéro hit sur une entrée classée suspecte et zéro lecture d'entrée entre domaines d'isolation sur 72 h (audit de l'index et de kvtrace) ; indicateur du canari ≤ 0,4 % dans les deux régions.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T010 — Serving C++ de recommandations pour un média public : architecture hexagonale à partir d'un PoC qui se bloque et d'un audit incohérent

| Axe | Valeur |
|---|---|
| Piste | Machine Learning |
| Domaine | recommender systems |
| Type | model serving |
| Langage | C++ |
| Charge | small-production (500 req/s, 500 GB) |
| Architecture | architecture hexagonale |
| Incident | deadlocks rares |
| Failure mode | horloge dérivante |
| Mode | architecture greenfield |

### Contexte

Rivéa, groupe audiovisuel public régional (14 éditions locales, 6 médias partenaires), personnalise le bloc « Pour vous » de son application et de son site. Le service reçoit 310 req/s en moyenne, ≈ 500 req/s en soirée et jusqu'à 1 400 req/s lors d'actualités majeures, pic atteint moins d'une minute après une notification push. Les données de recommandation représentent ≈ 500 Go (13 mois d'interactions, features, catalogue).

Le prototype Python ne tenait pas au-delà de 300 req/s : depuis le 01/09, un PoC C++ livré par un prestataire sert tout le trafic. Il tient la latence visée (p99 60 ms), mais le chien de garde l'a redémarré 9 fois en 18 jours et il coûte 3 100 €/mois. Le contrat du prestataire s'achève le 31/10 ; la direction technique a décidé de concevoir un composant cible en C++20 (GCC 13), en ne reprenant du PoC que ce qui se justifie.

Le cahier des charges de service public impose, dans chaque top 10, au moins 2 sources distinctes et au plus 30 % d'un même thème, et chaque recommandation affichée doit être justifiable devant le régulateur. Deux constats fragilisent ce point : le dimanche 13/09, un article sous embargo jusqu'à 20:00:00 a été recommandé à 19:59:24 selon le CDN, alors que le journal d'audit indique 20:00:05 ; l'auditeur interne a aussi trouvé des entrées dont l'ordre contredit celui des chargements de modèles.

Tu es l'architecte principal du composant cible ; nous sommes le lundi 21/09.

### Architecture existante

- **PoC** (C++17, GCC 9.4, Ubuntu 20.04, ONNX Runtime 1.16, spdlog, nlohmann::json) : 6 VM de 16 vCPU derrière un répartiteur L4 (sonde /healthz toutes les 5 s), serveur HTTP à 64 threads, chien de garde qui tente un dump gdb puis redémarre le processus après 30 s sans progrès.
- **Chaîne de requête** : tour utilisateur du two-tower et recherche HNSW en mémoire (≈ 60 k articles éligibles) → 2 000 candidats → features lues dans un Redis managé et gardées dans un cache local de 64 shards (TTL : 10 s pour la popularité, 10 min pour le profil, 30 min pour les articles) → reranker ONNX de 180 Mo (dont 162 Mo d'embeddings) → règles de pluralisme et d'embargo → top 10 → journal d'audit (JSON compressé, envoyé chaque minute vers le stockage objet, conservé 30 jours).
- **Registre** : un bundle (modèles et transformations de features par version de schéma) est publié toutes les 2 h ; les règles éditoriales changent toutes les 5 min. Les deux passent par `ModelRegistry::swap`.
- **Repli** : si le service ne répond pas, l'application affiche la liste « populaires » du prototype Python.
- **Temps** : synchronisation NTP interne par chrony, fourni par l'image de base des VM.

### Problème

Il faut concevoir un composant de serving qui absorbe les pics, respecte les règles éditoriales et produise un journal d'audit exploitable par le régulateur, pour un budget inférieur de 23 % au coût actuel. Cela suppose d'abord d'expliquer, à partir des dumps et du code du PoC, pourquoi il se bloque, et ce que les anomalies d'embargo et d'audit révèlent de sa gestion du temps : sans ce diagnostic, le composant cible reproduira les mêmes défauts.

L'architecture doit rendre ces défaillances impossibles par construction, ou à défaut détectables, isoler chaque dépendance derrière un port testable, et arbitrer explicitement entre coût, latence, exhaustivité de l'audit et coût de l'observabilité.

### Preuves


Dump capturé par le chien de garde (vm-reco-2, 11/09 16:00:32, 74 threads, extrait) :
```text
Thread 9 (LWP 21877) "registry-reload":
#0  futex_abstimed_wait_cancelable (...) at ../sysdeps/unix/sysv/linux/futex-internal.h:320
#1  __pthread_cond_timedwait (...) at pthread_cond_wait.c:667
#2  std::condition_variable::__wait_until_impl<std::chrono::duration<long, std::ratio<1, 1000000000> > > (...)
#3  recsvc::ModelRegistry::swap (this=0x55d0c2a1e2c0, next=...) at registry.cc:48
Thread 23 (LWP 21891) "http-12":
#0  __lll_lock_wait (futex=0x55d0c2a1e2c8, private=0) at lowlevellock.c:52
#1  recsvc::ModelRegistry::transform_for (this=0x55d0c2a1e2c0, schema=11) at registry.cc:71
#2  recsvc::FeatureCache::get_or_load (this=0x55d0c3f04000, id=4418217) at feature_cache.cc:41
#3  recsvc::Recommender::handle (...) at recommender.cc:88
Threads 24-26 "http-13".."http-15":
#0  __lll_lock_wait (futex=0x55d0c3f04f60, private=0) at lowlevellock.c:52
#1  recsvc::FeatureCache::get_or_load (this=0x55d0c3f04000, id=...) at feature_cache.cc:33
Les 60 autres threads "http-*":
#0  __lll_lock_wait (futex=0x55d0c2a1e2c8, private=0) at lowlevellock.c:52
#1  recsvc::ModelRegistry::current (this=0x55d0c2a1e2c0) at registry.cc:62
Threads 2-8 "ort-intra-0".."ort-intra-6":
#0  futex_wait (...) in onnxruntime::concurrency::ThreadPoolTempl<onnxruntime::Env>::WaitForWork (...)
(gdb) p registry.mu_.__data.__owner            $1 = 21877
(gdb) p cache.shards_[41].mu.__data.__owner    $2 = 21891
(gdb) p registry.inflight_                      $3 = {_M_i = 4}
```


Extraits du PoC :
```cpp
// registry.cc
void ModelRegistry::swap(std::shared_ptr<const Bundle> next) {
  std::unique_lock<std::mutex> reg(mu_);
  spdlog::info("registry: swap begin {}", next->id);
  std::unique_lock<std::mutex> lk(inflight_mu_);
  while (!inflight_cv_.wait_for(lk, std::chrono::seconds(2), [&] { return inflight_ == 0; }))
    spdlog::warn("registry: drain slow inflight={}", inflight_.load());
  current_ = std::move(next);  // l'ancienne session ONNX ne doit plus servir
  spdlog::info("registry: swap done");
}
std::shared_ptr<const Bundle> ModelRegistry::current() {
  std::lock_guard<std::mutex> g(mu_);
  return current_;
}
std::shared_ptr<const Transform> ModelRegistry::transform_for(int schema) {
  std::lock_guard<std::mutex> g(mu_);
  return current_->transforms.at(schema);
}
InflightGuard::~InflightGuard() { --reg_.inflight_; reg_.inflight_cv_.notify_all(); }

// feature_cache.cc
FeatureVec FeatureCache::get_or_load(ItemId id) {
  Shard& s = shards_[id % kShards];  // kShards = 64
  std::lock_guard<std::mutex> g(s.mu);
  auto it = s.map.find(id);
  if (it != s.map.end() && std::chrono::system_clock::now() - it->second.fetched_at < ttl_for(id))
    return it->second.vec;
  RawFeatures raw = redis_.fetch(id);  // ≈ 0,4 ms
  if (raw.schema != registry_.schema_version())  // lecture atomique
    raw = registry_.transform_for(raw.schema)->apply(raw);
  s.map[id] = Entry{raw.vec, std::chrono::system_clock::now()};
  return s.map[id].vec;
}

// recommender.cc
Response Recommender::handle(const Request& rq) {
  auto bundle = registry_.current();
  InflightGuard guard(registry_);  // ++inflight_
  auto cands = ann_.search(bundle->user_tower(rq.user), 2000);
  for (auto& c : cands) c.features = cache_.get_or_load(c.item);
  auto top = bundle->rules().apply(bundle->rerank(rq, cands), std::chrono::system_clock::now());
  audit_.append(rq, *bundle, top, std::chrono::system_clock::now());
  return to_response(top);
}
```


Redémarrages par le chien de garde du 01/09 au 18/09 (heure des VM), extrait des 9 cas :
```text
03/09 18:00:02  vm-reco-2  registry: swap begin b-0903-1800  puis « drain slow inflight=3 » toutes les 2 s  dump : oui
08/09 21:35:00  vm-reco-6  registry: swap begin r-0908-2135  puis « drain slow inflight=2 » toutes les 2 s  dump : oui
11/09 16:00:02  vm-reco-2  registry: swap begin b-0911-1600  puis « drain slow inflight=4 » toutes les 2 s  dump : oui
16/09 10:05:00  vm-reco-5  registry: swap begin r-0916-1000  aucune ligne pendant 30 s                     dump : non (gdb hors délai)
```
Les 8 dumps disponibles montrent la même configuration de threads que celui du 11/09. Hors redémarrages, 31 remplacements ont duré entre 2,00 et 2,01 s (médiane des autres : 4 ms), chacun avec un p99 > 2 s sur la minute. Le prestataire attribue les blocages au pool intra-op d'ONNX Runtime (threads « ort-intra » en attente dans chaque dump) et propose `intra_op_num_threads=1`, qui porterait le reranker de 8 à 27 ms au p50. L'exploitation, elle, relie les blocages aux sauts d'horloge à cause du cas du 16/09.


Horloges, embargo et audit :
```text
audit  2026-09-13T20:00:05.118Z vm-reco-5 top10[3]=art-918233 embargo_until=2026-09-13T20:00:00Z
CDN    première impression de art-918233 : 2026-09-13T19:59:24Z (horloge de référence)
Sep 14 03:12:09 vm-reco-3 cloud-agent[402]: maintenance event: live migration completed
Sep 14 03:12:09 vm-reco-3 chronyd[611]: System clock wrong by -0.812344 seconds
Sep 14 03:12:09 vm-reco-3 chronyd[611]: System clock was stepped by -0.812344 seconds
Sep 16 10:04:55 vm-reco-5 systemd[1]: Started chrony.service (OPS-3391 : chronyd absent de l'image du 01/09)
Sep 16 10:05:02 vm-reco-5 chronyd[20331]: System clock wrong by -49.284117 seconds
Sep 16 10:05:02 vm-reco-5 chronyd[20331]: System clock was stepped by -49.284117 seconds
```
Contrôle de l'auditeur (17/09) : 2 214 entrées de vm-reco-5 le 16/09 et 7 entrées de vm-reco-3 le 14/09 portent un horodatage antérieur à celui d'une entrée déjà écrite par la même VM ; le journal n'a ni numéro de séquence ni chaînage. Sur vm-reco-5, le taux de hit du cache de features passe de 96,8 % à 99,7 % pendant les 49 s qui suivent le saut.


Coûts et profil du PoC :
```text
Coût mensuel                                  Profil CPU par requête (perf, 500 req/s)
6 VM c-16 (16 vCPU, 32 Go) × 395 €   2 370 €  reranker ONNX fp32, 2 000 candidats    30,0 ms
Redis managé 64 Go                     410 €  features (Redis, désérialisation)       3,1 ms
Stockage objet (modèles, audit 30 j)    85 €  tour utilisateur et ANN                 1,8 ms
Métriques et logs (SaaS)               235 €  logs DEBUG synchrones et métriques      1,6 ms
Total                                3 100 €  audit (JSON + zstd, 1,9 Ko/requête)     0,9 ms
                                              règles éditoriales                      0,6 ms
```
Tarifs : VM c-8 (8 vCPU, 16 Go) 205 €, c-16 395 €, c-32 770 € ; Redis managé 32 Go 215 € (jeu chaud mesuré : 21 Go) ; stockage objet standard 0,021 €/Go/mois, archive 0,004 €/Go/mois (restitution sous 12 h, 0,02 €/Go lu) ; logs SaaS 0,45 €/Go ingéré. Démarrage d'une VM avec chargement des modèles : ≈ 3 min. Qualité actuelle : nDCG@10 hors ligne 0,367, taux de clic du bloc 6,8 %.

- Questions ouvertes : le service juridique n'a pas encore dit si « justifiable » impose de conserver les scores des 2 000 candidats ou seulement ce qui permet de les recalculer ; la direction éditoriale n'a fixé aucune priorité quand les deux règles de pluralisme ne peuvent pas être satisfaites ensemble (0,7 % des requêtes de nuit, quand une seule source publie) ; l'hébergeur ne publie ni la fréquence des migrations à chaud ni de borne d'erreur d'horloge.

### Contraintes

- budget mensuel plafonné — 2 400 €/mois tout compris à partir du 01/11 (calcul, feature store, stockage dont le journal d'audit conservé 13 mois, observabilité), contre 3 100 €/mois pour le PoC ; aucun GPU ; tarifs en preuve
- observabilité sans surcharge excessive — au plus 3 % du CPU des instances de serving pour métriques, traces et logs (4,2 % pour le PoC) ; échantillonnage permis pour les traces et les logs, jamais pour le journal d'audit
- auditabilité complète — 100 % des recommandations affichées justifiables pendant 13 mois : versions du modèle et des règles, features utilisées, raison de la présence de chaque article, respect du pluralisme et de l'embargo ; journal ordonné et infalsifiable ; réponse à toute demande du régulateur sous 30 jours

### Objectifs

- Établir, preuves à l'appui, les mécanismes des blocages du PoC et de ses anomalies temporelles, en distinguant ce qui est démontré, ce qui reste ambigu (cas du 16/09) et comment le trancher.
- Concevoir une architecture hexagonale dont l'absence d'interblocage est argumentée par construction et qui reste correcte face aux défaillances d'horloge observées sur les VM.
- Concevoir un journal d'audit complet, ordonné et infalsifiable, qui permette de justifier chaque recommandation pendant 13 mois dans le budget.
- Tenir 1 400 req/s avec la perte d'une VM, un p99 ≤ 60 ms, 2 400 €/mois et 3 % de CPU d'observabilité, en arbitrant explicitement le coût d'inférence du reranker.

### Livrables

- Architecture cible : ports et adaptateurs (candidats, features, runtime de modèles, règles éditoriales, audit, temps), comportement dégradé de chaque adaptateur, topologie et dimensionnement, décisions argumentées sur ce qui est repris du PoC.
- Diagnostic des blocages à partir des dumps et du code, puis modèle de concurrence cible : chemin de requête, publication et retrait des bundles et des règles, libération des anciennes versions, argument écrit d'absence d'interblocage et de famine.
- Modèle du temps et conception du journal d'audit : horloges utilisées pour les TTL, l'embargo et l'audit, réaction à une dérive ou un saut détecté, ordre vérifiable entre VM, format et taille d'une entrée, mécanisme rendant le journal infalsifiable, procédure de justification, coût de rétention sur 13 mois.
- Squelette C++20 compilable (chemin de requête, rechargement, adaptateur d'audit, port Temps) et plan de tests : ThreadSanitizer, endurance avec rechargements forcés, injection de sauts et de dérives d'horloge, rejeu du journal.
- Modèle de coût mensuel et budget CPU de l'observabilité, avec au moins deux options de réduction du coût du reranker (précision, nombre de candidats, cascade) et le protocole qui mesure leur effet sur la qualité et sur le pluralisme.

### Critères de réussite

- Endurance de 72 h à 1 400 req/s avec un rechargement de bundle toutes les 30 s et de règles toutes les 5 s : aucun blocage, aucune requête au-delà de 250 ms et aucun rapport ThreadSanitizer sur la suite de concurrence.
- p99 ≤ 60 ms à 500 req/s et à 1 400 req/s avec une VM en moins, y compris sur les fenêtres de 1 s qui suivent chaque rechargement de bundle ou de règles.
- Sous injection de sauts de ±60 s et d'une dérive de 500 ppm : aucun article recommandé avant la fin de son embargo selon l'horloge de référence, aucune feature servie au-delà de son TTL augmenté d'une marge fixée et justifiée, entrées d'audit dans un ordre total vérifiable, toute suppression ou modification d'entrée étant détectée.
- Pour 1 000 recommandations tirées au hasard sur la période de rétention, le journal permet en moins de 5 min chacune d'établir versions, features utilisées, raison de présence de chaque article et respect du pluralisme.
- Coût mensuel ≤ 2 400 € en régime établi, 13 mois d'audit compris, et observabilité ≤ 3 % du CPU mesurée par profilage à 500 req/s, sans baisse du nDCG@10 hors ligne de plus de 0,005.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T011 — Migration progressive d'encodeur pour une recherche d'offres d'emploi : un A/B négatif après une dérive de schéma et la perte d'une zone

| Axe | Valeur |
|---|---|
| Piste | Machine Learning |
| Domaine | embeddings et retrieval |
| Type | retrieval et reranking |
| Langage | Python |
| Charge | high-scale (100k req/s, 100 TB) |
| Architecture | event-driven |
| Incident | dérive de schéma |
| Failure mode | panne d'une zone |
| Mode | migration progressive |

### Contexte

Postelio exploite une place de marché européenne d'offres d'emploi : 41 M offres actives, ≈ 90 k req/s en pointe sur la recherche (autocomplétion comprise), dont ≈ 22 k req/s de recherche sémantique, et ≈ 100 To de données (offres, candidatures, journaux de recherche). Les offres viennent pour 77 % de flux partenaires (ATS) et pour 23 % du back-office employeurs. Elles circulent sous forme d'événements `offer.created` / `offer.updated` (≈ 3,4 M par jour) et sont embarquées à l'ingestion.

L'équipe recherche migre l'encodeur v1 (768 d, entraîné sur le français, l'anglais et l'allemand) vers v2 (1 024 d, multilingue). Sur le benchmark annoté de juillet, v2 gagne 6 % de recall@100. Un test A/B lancé le 08/09 sur 10 % des utilisateurs conclut pourtant, le 21/09, à une baisse de 3,1 % du taux de candidature dans le traitement. Le produit veut arrêter la migration ; l'équipe ML soupçonne un problème de mesure.

Entre-temps, l'équipe Offres a livré le 03/09 une nouvelle version de son API et du schéma Avro des événements, et la zone eu-west-1b a été indisponible le 16/09 au matin. Le taux de candidature global est passé de 4,40 % à 4,14 % depuis début septembre, ce que le produit attribue à la rentrée.

Tu es l'ingénieur principal chargé de décider de la suite de la migration ; nous sommes le mardi 22/09.

### Architecture existante

- **Worker d'embedding** (Python 3.12, asyncio, confluent-kafka, fastavro) : consomme le topic compacté `offers`, désérialise avec le schéma de l'écrivain lu dans le registre, construit le texte, appelle les encodeurs sur un pool de GPU L4, puis écrit dans les index. Depuis le 07/09, chaque événement est embarqué en v1 et en v2.
- **Index** : HNSW, 16 shards géographiques (shards 5 à 8 : France, 15,2 M offres). v1 : 3 réplicas par shard, un par zone. v2 : un seul réplica par shard pendant la migration, shards 5 à 8 en eu-west-1b. L'index v2 a été construit du 05/09 au 07/09 par le job batch `backfill-v2`, qui relit le topic compacté et réutilise la fonction de construction du texte du worker.
- **Requête** : encodage de la requête → ANN (top 400) → reranker cross-encoder commun aux deux bras (top 50) → règles métier. Le routeur choisit l'index selon le bras de l'utilisateur (hachage de user_id) et consigne le bras attribué dans le journal d'exposition.
- **Registre de schémas** : compatibilité BACKWARD par défaut ; aucun test de contrat côté consommateurs. Onze groupes de consommateurs lisent `offers`, dont trois seulement ont un propriétaire identifié.

### Problème

Le résultat de l'A/B ne peut être ni accepté ni rejeté en l'état. Il faut établir ce que l'expérience mesure réellement compte tenu des événements de septembre, et quantifier tout ce qui, en dehors de l'encodeur, a pu peser sur l'écart observé.

Il faut ensuite remettre la migration sur des bases saines : contrat de schéma entre producteurs et consommateurs, correction des vecteurs et des index touchés sans interruption ni dégradation de la latence, nouvelle expérience dont la règle de décision est fixée à l'avance, et migration progressive réversible à chaque palier. Le tout avec une équipe de trois personnes et sans GPU supplémentaire.

### Preuves


Registre de schémas et job de resynchronisation (UTC) :
```text
2026-09-02T17:42:10Z schema-registry PUT /config/offers-value {"compatibility":"NONE"} user=svc-offer-api (OFR-882 « débloquer offer-api 5.0 »)
2026-09-03T09:40:55Z schema-registry POST /subjects/offers-value/versions -> id=412 version=4
2026-09-03T11:00:03Z offer-resync start source=backoffice records=9104377 (updated_at conservé)
2026-09-03T15:21:47Z offer-resync done
```
```json
// offers-value v3
{"name": "description", "type": ["null", "string"]},
{"name": "skills", "type": {"type": "array", "items": "string"}}
// offers-value v4
{"name": "description_html", "type": ["null", "string"]},
{"name": "skills", "type": {"type": "array", "items": {"type": "record", "name": "Skill",
  "fields": [{"name": "name", "type": "string"}, {"name": "level", "type": ["null", "string"]}]}}}
```


Extraits du worker et du reranker :
```python
# embedder/worker.py
async def handle(self, msg: Message) -> None:
    offer = self.deserialize(msg.value())  # fastavro, schéma de l'écrivain
    key = offer["offer_id"]
    if self.state.last_updated_at(key) == offer["updated_at"]:
        return
    vecs = await self.encoders.embed(build_text(offer))  # {"v1": 768 d, "v2": 1 024 d}
    await self.index.upsert(key, vecs, shard=shard_of(offer["country"], offer.get("region")))
    self.state.set_last_updated_at(key, offer["updated_at"])

def build_text(offer: dict) -> str:
    return f"{offer.get('title', '')}\n{offer.get('description', '')}"

# reranker/features.py
def rerank_text(offer: dict) -> str:
    skills = " · ".join(str(s) for s in offer.get("skills", []))
    return f"Titre : {offer.get('title', '')} | Compétences : {skills} | {offer.get('description', '')[:1200]}"
```
Entrée du reranker journalisée le 18/09 pour une offre du back-office : `Titre : Soudeur TIG H/F | Compétences : {'name': 'Soudure TIG', 'level': 'confirmé'} · {'name': 'Lecture de plans', 'level': None} | `


Longueur du texte embarqué, relevée dans les métadonnées des vecteurs le 21/09 :
```text
Index  Source            Offres   Tokens embarqués (médiane)             Part < 32 tokens
v1     flux partenaires  31,6 M   224                                    0,4 %
v1     back-office        9,4 M   212 (vecteurs antérieurs au 03/09)     38 %
                                   19 (vecteurs écrits depuis le 03/09)
v2     flux partenaires  31,6 M   226                                    0,4 %
v2     back-office        9,4 M   19                                     99,1 %
```
Les offres du back-office représentent 52 % des offres françaises (shards 5 à 8) et 5,9 % des offres des autres marchés.


Résultats de l'A/B du 08/09 au 21/09 (taux de candidature par session de recherche, bras attribué par hachage de user_id) :
```text
Segment                                   Contrôle v1   Traitement v2   Écart relatif [IC 95 %]
Global                                    4,150 %       4,021 %         −3,1 % [−3,4 ; −2,8]
France (shards 5 à 8)                     3,880 %       3,610 %         −7,0 % [−7,5 ; −6,5]
Autres marchés                            4,310 %       4,265 %         −1,0 % [−1,4 ; −0,6]
Requêtes hors français, anglais, allemand 2,940 %       3,090 %         +5,1 % [+3,9 ; +6,3]
France, journée du 16/09                  3,850 %       3,010 %         −21,8 %
```
Recall@100 sur le benchmark de juillet (18 k requêtes annotées) : v1 0,712, v2 0,755. Recall de l'ANN face à une recherche exacte (10 k requêtes, ef_search = 128) : v1 0,962, v2 0,948.


Panne de zone du 16/09 (UTC) :
```text
2026-09-16T04:12:30Z az-health eu-west-1b unavailable
2026-09-16T04:12:41Z search-router v2 shards=5,6,7,8 unreachable -> fallback index=v1 for affected queries
2026-09-16T06:47:10Z az-health eu-west-1b available
2026-09-16T06:50:02Z ann-v2-shard-5 local volume empty -> backfill-v2 --shards 5-8 --source offers(compacted)
2026-09-16T06:58:15Z search-router v2 shard=5 ready (GET /healthz 200) docs=112400
2026-09-16T08:30:00Z ann-v2-shard-5 docs=1941200/3812000
2026-09-16T10:52:44Z ann-v2-shard-8 backfill complete docs=3798350
```

- Capacité et hypothèses : le pool de 12 GPU L4 est partagé entre l'encodage des requêtes (prioritaire) et l'ingestion ; il est utilisé à 40 % en moyenne et 75 % en pointe, avec ≈ 190 offres/s par GPU pour v1 et v2 ensemble, et aucun GPU supplémentaire n'est possible avant novembre. En préproduction, 300 mises à jour/s sur un shard HNSW portent le p99 de sa recherche de 21 à 24 ms, 1 200 mises à jour/s à 58 ms ; chaque nœud d'index héberge un réplica v1 et, le cas échéant, un shard v2, et sa mémoire n'admet pas un troisième index. Le produit attribue la baisse globale à la rentrée ; un ingénieur ML pense que l'encodeur multilingue « dilue » le français ; l'infrastructure soupçonne des paramètres HNSW non réglés pour 1 024 dimensions. Personne n'a vérifié si `description_html` contient le même texte que l'ancien champ `description`.

### Contraintes

- équipe réduite — 3 ingénieurs (2 ML, 1 backend) pour toute la recherche, astreinte comprise ; ≈ 6 semaines-personne disponibles d'ici le 31/10 ; aucune nouvelle brique d'infrastructure à opérer
- zero downtime — la recherche ne s'interrompt jamais : 22 k req/s de retrieval en pointe, p99 ≤ 120 ms de bout en bout dont ≤ 35 ms pour l'ANN ; toute bascule d'index, d'encodeur ou de schéma se fait à chaud, sans fenêtre de maintenance
- déploiement progressif — toute exposition de v2 ou d'un index reconstruit passe par des paliers (1 %, 5 %, 25 %, 50 %, 100 %) avec des critères d'arrêt fixés avant le démarrage ; retour à l'état précédent en moins de 5 min à chaque palier

### Objectifs

- Établir ce que mesure réellement l'A/B : identifier et quantifier chaque facteur de confusion, estimer l'effet propre de l'encodeur quand c'est possible, et séparer faits, hypothèses et inconnues.
- Rétablir des vecteurs et des index corrects dans les deux versions, sans interruption, sans dépasser les budgets de latence et sans GPU supplémentaire.
- Empêcher qu'une évolution de schéma côté producteur dégrade à nouveau silencieusement un consommateur.
- Reprendre la migration v1 → v2 par paliers réversibles, avec une décision fondée sur une expérience fiable et robuste à la perte d'une zone.

### Livrables

- Analyse de l'expérience : facteurs de confusion identifiés et chiffrés, estimation de l'effet de l'encodeur débarrassé de chacun d'eux ou démonstration qu'elle n'est pas possible avec les données actuelles, réponse argumentée au produit sur l'arrêt de la migration.
- Contrat de schéma : politique de compatibilité du registre, modèles de message typés côté consommateur, tests de contrat exécutés en CI chez le producteur et chez les consommateurs, procédure d'évolution (ajout, renommage, changement de type), plan pour les consommateurs sans propriétaire.
- Backfill idempotent en Python : sélection des offres à ré-embarquer, versionnement des vecteurs, ordre vis-à-vis des mises à jour en direct, limitation du débit d'écriture dans l'index, reprise après interruption ; code et tests (pytest, tests de propriété).
- Protocole de la nouvelle expérience : unité de randomisation, métrique primaire et garde-fous, durée et effet minimal détectable, segments préenregistrés, règle de décision écrite avant le démarrage, traitement des incidents survenant pendant l'expérience.
- Plan de migration progressive : paliers et critères d'arrêt, reconstruction et bascule d'index à chaud, retour arrière en moins de 5 min, comportement en cas de perte d'une zone, charge de travail estimée pour l'équipe.

### Critères de réussite

- Après correction, dans chaque index et pour chaque source d'offres, la médiane des tokens embarqués s'écarte de moins de 10 % de celle des vecteurs v1 antérieurs au 03/09 pour la même source, et un contrôle quotidien automatisé alerte au-delà de ce seuil.
- Le backfill respecte en permanence un p99 ANN ≤ 35 ms et un p99 de bout en bout ≤ 120 ms sur la capacité GPU existante ; exécuté deux fois, ou interrompu puis repris, il produit les mêmes vecteurs et n'écrase aucune mise à jour plus récente (tests automatisés).
- Un changement de schéma incompatible sur un champ lu par un consommateur (renommage, changement de type) est bloqué en CI avant publication, démontré par un test rejouant le cas du 03/09.
- La nouvelle expérience a une règle de décision écrite avant son lancement, une puissance ≥ 80 % pour un effet relatif de ±1 % sur le taux de candidature et des garde-fous par marché ; un incident simulé (perte d'une zone) pendant l'expérience apparaît dans les données d'analyse au niveau de la session, sans intervention manuelle.
- À chaque palier, un exercice de retour à l'état précédent aboutit en moins de 5 min sans erreur visible pour les utilisateurs ; une perte de zone simulée, suivie de la reconstruction des shards concernés, ne fait baisser à aucun moment le recall@100 des requêtes touchées de plus d'un point.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T012 — Diagnostic probabiliste d'une dérive de coût de 63 % sur un pipeline d'événements ClickHouse à 1,4 M événements/s

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | raisonnement probabiliste |
| Type | diagnostic sous information incomplète |
| Langage | SQL |
| Charge | extreme-scale (1M+ req/s, 1 PB+) |
| Architecture | event-driven |
| Incident | coût cloud qui dérive |
| Failure mode | disque lent |
| Mode | conception d'un système résilient |

### Contexte

Vireolab édite trois jeux mobiles, dont Rift Tactics, pour 68 M de joueurs actifs par mois. Tous les événements de jeu, télémétrie technique des clients comprise, alimentent une chaîne analytique : 1,05 M événements/s en moyenne, 1,4 M en pointe, ≈ 180 To sur disques chauds et ≈ 1,3 Po sur S3.

Le 28 septembre 2026, l'équipe FinOps donne l'alerte. Le coût hebdomadaire du compte cloud analytics est passé de 23,2 k€ en semaine 33 à 37,8 k€ en semaine 39 (+63 %), alors que le volume d'événements n'a crû que de 18 %. Sur la période :
- 14 août : sept nœuds ClickHouse sont recréés après une mise hors service matérielle programmée par l'hébergeur ;
- 17 août : lancement de la saison 7 de Rift Tactics ;
- 20 août : `log_queries_probability = 0.1` est ajouté au profil `default` pour alléger `system.query_log` ;
- 26 août : mise en service du tableau de bord LiveOps Pulse, affiché en continu sur les écrans des salles LiveOps de Lyon et de Montréal.

Quatre équipes avancent quatre explications : la croissance naturelle (FinOps), le tableau de bord (SRE), les disques (plateforme), le trafic inter-zones (réseau). L'export de facturation n'attribue par étiquette qu'environ 70 % du coût de septembre. Le comité budgétaire du 9 octobre attend une attribution chiffrée du surcoût et un plan qui empêche la récidive malgré la croissance prévue.

Le diagnostic et la conception te sont confiés.

### Architecture existante

- **Collecte** : collecteurs HTTP → Kafka sur 3 zones ; topic principal de 192 partitions.
- **ClickHouse auto-géré** : 48 nœuds de 16 vCPU et 64 Go, soit 24 shards × 2 réplicas placés dans deux zones différentes. Chaque nœud consomme 4 partitions via une table moteur Kafka et une vue matérialisée, puis insère localement dans `events.game_events` (ReplicatedMergeTree, partition par jour). L'autre réplica récupère les parts par le port interserveur 9009. Les requêtes passent par la table Distributed `game_events_all` (`load_balancing = random`).
- **Stockage** : politique `hot_cold`. Chaud : volume réseau de type gp3 de 3,75 To par nœud, débit provisionné à 500 Mo/s dans le gabarit standard. Froid : bucket S3 atteint par un point de terminaison de passerelle (sans frais de transfert), cache disque local de 50 Go par nœud ; chaque réplica garde sa propre copie des parts froides.
- **Rétention** : événements bruts 7 jours sur le chaud, puis S3 jusqu'à 60 jours ; agrégats horaires (AggregatingMergeTree, `sumState`, `uniqState`) conservés 25 mois.
- **Lecteurs** : ETL horaire, analystes et outil interne de tableaux de bord, qui interroge ClickHouse sans cache de résultats.

### Problème

Le surcoût de 14,6 k€ par semaine doit être réparti entre les explications concurrentes et leurs éventuelles interactions, avec une incertitude explicite. Les sources sont lacunaires :
- 30 % du coût n'est pas attribué ;
- `query_log` est échantillonné depuis une date proche du début de la dérive ;
- les journaux de flux réseau ne couvrent qu'une zone ;
- certaines configurations ne sont pas accessibles.

Il faut dire quelles mesures peu coûteuses départageraient les hypothèses, et dans quel ordre les lancer. Il faut ensuite concevoir une chaîne d'ingestion, de stockage et de requêtes dont le coût reste prévisible quand un disque ralentit ou qu'une requête coûteuse apparaît. Elle doit absorber la croissance attendue sans mémoire supplémentaire, et chaque changement doit être réversible.

### Preuves


Coût hebdomadaire du compte analytics (k€, export de facturation). « Non attribué » regroupe les postes sans étiquette : transfert inter-zones, passerelles NAT, journaux, ressources d'autres équipes hébergées sur le compte.
```text
Semaine 2026              S33   S34   S35   S36   S37   S38   S39
Calcul ClickHouse (48)    6,5   6,5   6,5   6,5   6,5   6,5   6,5
Collecteurs + Kafka       2,4   2,5   2,6   2,6   2,7   2,8   2,8
Volumes chauds gp3        3,1   3,1   3,1   3,1   3,1   3,1   3,1
S3 capacité               5,2   5,3   5,4   5,6   5,7   5,9   6,0
S3 requêtes (GET + PUT)   0,5   0,9   3,6   5,1   6,4   7,3   8,0
Non attribué              5,5   6,9   7,6   8,8   9,9  10,8  11,4
Total                    23,2  25,2  28,8  31,7  34,3  36,4  37,8
```
Événements ingérés : 538 G en S33, 635 G en S39. Métriques du bucket froid, moyenne par jour : S33 : 180 M GET et 1,1 M PUT ; S39 : 3 050 M GET et 3,4 M PUT. Tarifs : GET 0,37 € par million, PUT 4,6 € par million, transfert inter-zones 0,018 €/Go (deux sens cumulés).


Métriques disque et ingestion de la semaine 39 (exporteur de nœud, p95 sur 06:00–23:00 UTC) :
```text
Groupe de nœuds                     Débit disque   Utilisation   Attente E/S   iowait   Retard Kafka     Mémoire résidente
ch-05, 11, 18, 22, 29, 36, 44       125 Mo/s (*)   99 %          38 ms         31 %     jusqu'à 14 min   52 Go
leurs 7 réplicas pairs              310 Mo/s       58 %          2,4 ms        4 %      < 5 s            39 Go
34 autres nœuds                     270 Mo/s       49 %          1,9 ms        3 %      < 5 s            37 Go
(*) plateau constant de 06:00 à 23:00, lecture et écriture cumulées
```
Ces sept nœuds sont ceux recréés le 14 août. L'export d'inventaire ne contient pas les paramètres de débit de leurs volumes (non disponible) ; dans la facturation, le coût de chacun de leurs volumes est à 5 % près celui des autres. Taux de remplissage du volume chaud : 69 % en S33, 81 % en S39.


Requête lancée le 28 septembre sur tout le cluster, complétée par la même agrégation sur `system.replication_queue` et `system.part_log` :
```sql
SELECT hostName() AS noeud,
       countIf(active) AS parts_actives,
       countIf(active AND disk_name = 's3_cold') AS parts_froides,
       countIf(active AND disk_name = 's3_cold' AND max_date >= today() - 30) AS parts_froides_30j,
       round(avgIf(bytes_on_disk, active) / 1e9, 2) AS taille_moy_go
FROM clusterAllReplicas('ev', system.parts)
WHERE database = 'events' AND table = 'game_events'
GROUP BY noeud;
```
```text
Médianes par groupe   Parts actives   dont froides   froides < 30 j   Taille moy. (Go)   File de réplication   dont MERGE_PARTS
7 lents               24 900          18 700         11 300            0,96              2 960                 2 710
7 pairs                1 260             980            410           19,4                 140                    96
34 autres              1 220             950            400           19,6                  38                    30

system.part_log, moyenne par nœud et par jour sur 7 jours
Groupe      NewPart (Go)   MergeParts écrits (Go)   DownloadPart réussis (Go)   DownloadPart en erreur (nombre)
7 lents     214            380                      520                         2 380 (code 209, SOCKET_TIMEOUT)
7 pairs     219            2 150                    228                         4
34 autres   216            2 210                    221                         3
```


Extrait de `system.query_log` du jeudi 24 septembre : requêtes initiales, `type = 'QueryFinish'`, compteurs S3 sommés sur les sous-requêtes des shards via `initial_query_id`.
```text
Utilisateur   Requête                            Lignes journalisées   GET S3 moy.   Lu moy.   Mémoire moy.   Durée p50
pulse_ro      Pulse « Revenu 30 j »              596                   186 000       41 Go     7,1 Go         31,8 s
pulse_ro      Pulse « Rétention 30 j »           581                   171 000       38 Go     6,4 Go         29,5 s
etl_agg       INSERT des agrégats horaires       239                         0        1,8 Go   2,2 Go          4,1 s
analyst_*     ad hoc (1 204 formes distinctes)   3 912                   4 100        0,9 Go   0,6 Go          1,2 s
```
Note SRE du 28 septembre : « D'après query_log, Pulse pèse 7 % des GET S3 du bucket : ce n'est pas lui. » L'utilisateur `pulse_ro` relève du profil `readonly_bi`, défini dans un fichier de configuration géré par l'équipe BI (non fourni). Le nombre d'onglets ouverts sur Pulse en dehors des deux écrans est inconnu.


Schéma de la table brute et requête d'un panneau de Pulse :
```sql
CREATE TABLE events.game_events ON CLUSTER ev
(
    event_date   Date,
    event_time   DateTime64(3, 'UTC'),
    game_id      LowCardinality(String),
    event_type   LowCardinality(String),
    player_id    UInt64,
    country      LowCardinality(String),
    revenue_eur  Decimal(18, 6),
    payload      String CODEC(ZSTD(3))
    -- ... 74 autres colonnes
)
ENGINE = ReplicatedMergeTree('/clickhouse/{shard}/game_events', '{replica}')
PARTITION BY event_date
ORDER BY (game_id, event_type, event_time, player_id)
TTL event_date + INTERVAL 7 DAY TO VOLUME 'cold',
    event_date + INTERVAL 60 DAY DELETE
SETTINGS storage_policy = 'hot_cold';

-- LiveOps Pulse, panneau « Revenu 30 j », rafraîchi toutes les 60 s
SELECT event_date AS jour, game_id,
       sumIf(revenue_eur, event_type = 'purchase')          AS revenu,
       uniqExactIf(player_id, event_type = 'purchase')      AS payeurs,
       uniqExactIf(player_id, event_type = 'session_start') AS actifs
FROM events.game_events_all
WHERE event_date >= today() - 30
  AND event_type IN ('purchase', 'session_start')
GROUP BY jour, game_id
ORDER BY jour, game_id;
```
Note BI : les agrégats horaires existants ont été écartés pour Pulse, car LiveOps rapproche chaque semaine le nombre de joueurs payants à l'unité avec la finance.


Journaux de flux réseau activés seulement sur le sous-réseau de la zone c (16 nœuds ClickHouse, dont ch-11, ch-29 et ch-44), échantillonnés à 1/100 et extrapolés ×100. Trafic entrant depuis les zones a et b, en To par jour :
```text
Port (usage)                           S33 (moy./jour)   S39 (moy./jour)
9009 (interserveur, parts)             3,2               16,3
9000 (sous-requêtes distribuées)       0,4                4,2
9092 (Kafka vers consommateurs CH)     3,8                4,5
```
En S39, 82 % du trafic entrant sur le port 9009 a pour destination ch-11, ch-29 et ch-44. Aucune donnée équivalente n'existe pour les zones a et b.


### Contraintes

- forte croissance des données — +9 % de volume par mois attendus sur 12 mois (≈ ×2,8 d'ici septembre 2027) ; la conception retenue doit tenir cette trajectoire sans refonte, et son coût doit être chiffré à 6 et à 12 mois
- faible consommation mémoire — nœuds de 64 Go dont 40 Go au plus pour l'exécution des requêtes, aucune montée de gamme avant janvier 2027 ; une requête de tableau de bord ne doit pas dépasser 2 Go
- rollback obligatoire — toute modification de politique de stockage, de TTL, de schéma ou de vue matérialisée doit pouvoir être annulée en moins d'1 h, sans perte d'événement ni réécriture massive des parts déjà déplacées vers S3

### Objectifs

- Attribuer le surcoût de 14,6 k€/semaine (S33 → S39) aux explications concurrentes et à leurs interactions, avec a priori, vraisemblances et intervalles explicites, en corrigeant les biais des sources (échantillonnage, coût non attribué, couverture réseau partielle).
- Nommer les inconnues qui peuvent changer la décision et ordonner des mesures ou expériences discriminantes selon leur coût, leur durée, leur risque et l'information attendue.
- Concevoir une chaîne d'ingestion, de stockage et de requêtes dont le coût reste stable et prévisible face à un disque lent, à une requête coûteuse et à +9 % de volume par mois, dans le budget mémoire actuel.
- Planifier le déploiement de chaque changement avec un retour arrière vérifié en moins d'1 h et sans perte d'événement.

### Livrables

- Note d'attribution : tableau explication → part du surcoût (estimation centrale et intervalle), hypothèses de calcul, interactions entre explications, et observations qui feraient réviser l'estimation.
- Requêtes SQL de diagnostic sur les tables système (parts, part_log, replication_queue, query_log corrigé de l'échantillonnage, sous-requêtes par réplica), avec leur coût mémoire borné et le résultat attendu sous chaque hypothèse.
- Plan d'expériences discriminantes chiffrées (durée, coût, risque, critère de décision), dont au moins une expérience réversible limitée à un seul shard.
- Conception résiliente : DDL ClickHouse (tables, politiques de stockage, TTL, profils, quotas et toute structure dérivée proposée), protections contre un disque lent et contre une requête coûteuse, modèle de coût à 6 et 12 mois.
- Plan de déploiement et de rollback par étape : commande d'annulation, durée mesurée, critère d'abandon et preuve d'absence de perte.

### Critères de réussite

- Chaque explication reçoit une part du surcoût avec un intervalle à 80 % ; les estimations centrales somment à 14,6 k€/semaine à ±5 % ; après les expériences, l'économie mesurée tombe dans l'intervalle prédit pour au moins 3 postes de facturation sur 4 concernés.
- Coût ≤ 45 € par milliard d'événements ingérés dans les 4 semaines suivant le déploiement (43,1 € en S33, 59,5 € en S39), et ≤ 45 € dans le modèle à 12 mois avec +9 %/mois.
- Test d'injection : un nœud par zone bridé à 125 Mo/s pendant 72 h → ≤ 2 000 parts actives par nœud pour `game_events`, retard Kafka ≤ 60 s, trafic interserveur inter-zones ≤ 1,2 fois le nominal.
- Chaque panneau de Pulse ≤ 2 Go de mémoire, ≤ 2 s au p95 et ≤ 5 000 GET S3 par exécution, avec des valeurs identiques à la requête actuelle pour le revenu (au centime) et les payeurs (à l'unité) ; pour les joueurs actifs, valeur exacte ou écart accepté par écrit par LiveOps.
- Chaque étape annulée en répétition en moins d'1 h, avec un rapprochement exact, partition par partition, entre les offsets Kafka consommés et les lignes présentes dans ClickHouse.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T013 — Reproduire en test de charge l'effondrement d'une recherche d'itinéraires B2B, puis valider un algorithme sous budget de temps

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | optimisation combinatoire |
| Type | conception d'algorithme efficace |
| Langage | C# |
| Charge | production (10k req/s, 10 TB) |
| Architecture | microservices |
| Incident | backpressure insuffisante |
| Failure mode | latence d'un fournisseur externe |
| Mode | conception de tests de charge |

### Contexte

Ventalys exploite une plateforme de voyages d'affaires utilisée par 1 100 entreprises. Son API de recherche assemble vols et hôtels pour des itinéraires de 1 à 4 segments. Chaque résultat doit respecter la politique voyage de l'entreprise : plafond par nuit, compagnies préférées, classe autorisée, budget total du déplacement. L'API reçoit 8 900 recherches/s en pointe ordinaire et 10 000 lors des pics de rentrée. Tarifs en cache, disponibilités et historique des recherches représentent ≈ 9 To.

Le mardi 8 septembre 2026 à 14:02, la latence p99 du fournisseur A, un GDS historique, passe de 0,8 s à 6 s. À 14:06, le client Tellurion lance depuis son outil de crise le réacheminement de 4 000 voyageurs bloqués par une grève du contrôle aérien : 36 000 recherches, la plupart à 3 ou 4 segments. De 14:11 à 14:58, entre 18 et 61 % des requêtes de tous les clients reçoivent un 503. Le service ne redevient normal qu'à 15:20, après le redémarrage des pods.

Le test de charge d'août avait pourtant validé 12 000 recherches/s avec un p99 de 420 ms. La directrice technique refuse désormais toute mise en production d'un nouvel algorithme ou d'un mécanisme de régulation tant qu'une campagne de tests n'a pas d'abord reproduit l'incident, puis montré que la nouvelle version y résiste.

Ton rôle : concevoir cette campagne, ainsi que l'algorithme et la régulation qu'elle devra valider.

### Architecture existante

- **Passerelle d'API** : timeout de 10 s ; renvoie 503 quand aucun pod n'est prêt ou quand sa file amont dépasse 2 000 requêtes.
- **search-orchestrator** (.NET 8, ASP.NET Core) : 40 pods de 8 vCPU, limite mémoire de 12 Go, GC serveur. Autoscaling sur le CPU (cible 60 %, 60 pods au plus, ≈ 3 min pour ajouter un pod). Sonde `/health/ready` avec un timeout de 1 s.
- **Adaptateurs fournisseurs** : A en SOAP, client généré par dotnet-svcutil (`SendTimeout` de 30 s) ; B et C en REST, via `HttpClient` avec le timeout par défaut ; hôtels via l'agrégateur H.
- **Cache de disponibilité** (Redis) : clé (segment, date, fournisseur), TTL de 10 min, 93 % de succès.
- **policy-service** : sert les politiques en JSON ; l'orchestrateur les garde en mémoire et les recharge après 5 min.
- **booking-service** : garantit le prix d'un devis pendant 15 min.
- **Clients** : les SDK des partenaires réessaient immédiatement sur un 504 ; l'outil de crise de Tellurion envoie ses lots avec une concurrence de 600.

### Problème

La cascade du 8 septembre n'a jamais été reproduite. Le test d'août ne l'avait pas vue venir, et l'équipe ne s'accorde ni sur ce qui l'a déclenchée ni sur ce qui l'a entretenue pendant près d'une heure.

Il faut d'abord concevoir une campagne de tests de charge capable de la reproduire de façon fiable, à partir d'un modèle de charge tiré des traces. Il faut ensuite concevoir deux mécanismes :
- un algorithme de recherche qui, dans un budget de temps fixé, rend un résultat conforme à la politique avec un écart à l'optimum borné et connu ;
- une régulation de charge équitable entre tenants, qui limite l'exposition à un fournisseur lent.

La campagne doit enfin prouver que la nouvelle version tient là où l'ancienne s'effondre, sans interruption de service ni observabilité trop coûteuse.

### Preuves


Métriques agrégées sur les 40 pods pendant l'incident du 8 septembre (p95 entre pods pour la file et la mémoire) :
```text
Heure  Req/s      Recherches  A p99   Appels     File du pool   GC gen2/min      Mémoire  Pods     503
       entrantes  en vol              en vol A   de threads     (pause max)      pod      prêts
13:55   8 900      3 100      0,8 s     290             0        2 (45 ms)       3,1 Go   40/40    0 %
14:05   9 100      7 800      6,0 s   1 350           120        4 (110 ms)      4,6 Go   40/40    0 %
14:08  10 400     21 500     6,2 s   3 100         9 800        9 (480 ms)      8,2 Go   40/40    0,4 %
14:11  13 100     38 200      6,1 s   4 700        41 000       14 (1 240 ms)   11,0 Go   31/40   18 %
14:15   9 700     29 900      5,8 s   4 200        37 500       12 (1 310 ms)   10,7 Go   22/40   61 %
14:30   8 200     24 100      5,9 s   3 600        30 200       11 (1 150 ms)   10,4 Go   24/40   47 %
14:45   8 400     17 800      1,2 s   2 100        22 000        8 (890 ms)      9,6 Go   29/40   22 %
15:20   8 800      3 300      0,8 s     300             0        2 (50 ms)       3,4 Go   40/40    0 %
```
Ventilation des 13 100 req/s de 14:11 : 3 400 réessais clients (même `X-Request-Id` qu'une requête reçue moins de 15 s plus tôt), 110 recherches Tellurion, le reste en trafic ordinaire. L'autoscaler n'a ajouté aucun pod : le CPU moyen est resté entre 31 et 52 %. Latence p50 de A : 0,24 s à 13:55, 0,9 s à 14:05, entre 1,3 et 1,5 s de 14:08 à 14:40. La page d'état de A signale un incident de 14:02 à 14:44.


Extraits de l'orchestrateur (v3.14) :
```csharp
// SearchOrchestrator.cs
public async Task<SearchResult> SearchAsync(SearchRequest req, CancellationToken ct)
{
    TravelPolicy policy = _policies.Get(req.TenantId);
    var fareTasks = new List<Task<ProviderFares>>();
    foreach (var seg in req.Segments)
        foreach (var provider in _providers)                      // A, B, C
            fareTasks.Add(_cache.GetOrFetchAsync(seg, provider, ct));
    var rateTasks = req.Stays.Select(s => _hotels.GetRatesAsync(s, ct)).ToList();
    await Task.WhenAll(fareTasks.Cast<Task>().Concat(rateTasks));

    var perSegment = req.Segments.Select((_, i) => fareTasks
            .Skip(i * _providers.Count).Take(_providers.Count)
            .SelectMany(t => t.Result.Flights)
            .OrderBy(f => f.TotalPrice).Take(60).ToList())
        .ToList();
    var perStay = rateTasks.Select(t => t.Result.Rates).ToList();

    List<Itinerary> combos = Combinator.Cartesian(perSegment, perStay)
        .Where(it => it.ConnectionsValid())
        .Take(2_000_000)
        .ToList();
    return new SearchResult(combos
        .Where(it => policy.Allows(it))
        .OrderBy(it => Scoring.Score(it, policy))
        .Take(50)
        .ToList());
}

// PolicyCache.cs
public TravelPolicy Get(string tenantId)
{
    if (_entries.TryGetValue(tenantId, out var e) && e.LoadedAt > DateTime.UtcNow.AddMinutes(-5))
        return e.Policy;
    TravelPolicy fresh = _client.GetPolicyAsync(tenantId).GetAwaiter().GetResult();
    _entries[tenantId] = new CachedPolicy(fresh, DateTime.UtcNow);
    return fresh;
}

// ProviderAAdapter.cs
public async Task<ProviderFares> GetFaresAsync(Segment seg, CancellationToken ct)
{
    SearchFaresResponse resp = await _soapClient.SearchFaresAsync(ToSoap(seg));
    return FromSoap(resp);
}
```


Diagnostics capturés à 14:12 sur le pod `search-orch-7f9c-12` :
```text
dotnet-counters
  ThreadPool Thread Count                          612
  ThreadPool Queue Length                       41 380
  ThreadPool Completed Work Item Count / 1 s     2 140
  % Time in GC since last GC                        38
  Gen 2 GC Count / 60 s                             14
  LOH Size (B)                           3 118 000 000
  GC Fragmentation (%)                              27
  Allocation Rate (B / 1 s)              1 870 000 000

dotnet-dump analyze, clrstack -all : répartition des 612 threads
  311  PolicyCache.Get → TaskAwaiter.GetResult → ManualResetEventSlim.Wait
  164  Enumerable.ToList → Combinator.Cartesian (MoveNext)
   97  attente de fin de GC
   40  autres
```


Test de charge d'août, présenté en comité comme la preuve que la plateforme tient 12 000 recherches/s :
```csharp
// LoadTests/SearchLoad.cs (NBomber)
var scenario = Scenario.Create("search_roundtrip", async ctx =>
    {
        SearchRequest req = Fixtures.RoundTrip(ctx.Random, tenant: "loadtest-01"); // 2 segments, 1 nuit
        using var resp = await http.PostAsJsonAsync("/v2/search", req);
        return resp.IsSuccessStatusCode ? Response.Ok() : Response.Fail();
    })
    .WithWarmUpDuration(TimeSpan.FromSeconds(30))
    .WithLoadSimulations(Simulation.KeepConstant(copies: 2_000, during: TimeSpan.FromMinutes(10)));
// A, B, C et H simulés par WireMock.Net, latence fixe de 150 ms ; cache Redis préchauffé.
```
Rapport : 12 050 req/s, p50 160 ms, p99 420 ms, 0 erreur, CPU moyen des pods 71 % (autoscaling désactivé en préproduction).


Profil de trafic (traces échantillonnées à 1 %, semaine du 31 août) : 1 segment 25 %, 2 segments 68 %, 3 segments 4 %, 4 segments 3 % ; 47 % des recherches incluent au moins un séjour hôtelier. Lots Tellurion du 8 septembre : 71 % à 3 ou 4 segments.

Coût mesuré par recherche sur un pod isolé :
- 2 segments et 1 nuit : 17 ms de CPU, 34 Mo alloués ;
- 4 segments et 3 séjours : 210 ms de CPU, 390 Mo alloués, plafond de 2 000 000 de combinaisons atteint.

Qualité hors ligne sur 1 000 recherches réelles à 4 segments, comparées à l'optimum exact calculé par un solveur en nombres entiers (9 h sur 64 cœurs, sur les 200 vols par segment et 150 hôtels par séjour) :
- le meilleur résultat conforme renvoyé dépasse l'optimum de 14,2 % en médiane ;
- 11,3 % des recherches ne renvoient aucun résultat conforme alors qu'il en existe un ;
- sur des recherches à 2 segments, l'écart médian n'est que de 0,4 %.

Quand une recherche ne renvoie aucun résultat conforme, l'outil de Tellurion la relance en élargissant les dates de ±1 jour, jusqu'à 3 fois.


Informations contractuelles et opérationnelles :
- Fournisseur A : ≈ 38 M d'appels par jour ; quota de 1 800 appels simultanés par compte, au-delà duquel A met les appels en file de son côté ; chaque appel au-delà de 45 M par jour est facturé 0,0004 €.
- Le contrat ne dit pas si un appel abandonné par le client reste compté dans le quota jusqu'à sa fin côté A. Une question a été envoyée le 10 septembre, sans réponse à ce jour.
- Pour l'incident, seules les latences p50 et p99 par minute de A sont disponibles ; les histogrammes n'ont pas été conservés.
- Observabilité actuelle : traces OpenTelemetry pour 100 % des appels fournisseurs, soit 6,4 % de CPU mesuré par pod ; 31 000 séries de métriques actives.
- La direction produit n'a pas tranché : un réacheminement de crise de voyageurs bloqués doit-il passer avant les recherches ordinaires des autres clients ?


### Contraintes

- multi-tenant — 1 100 entreprises clientes, dont les 20 plus grosses font 46 % des recherches ; 140 tenants Premium ont un p95 contractuel inférieur à 2,5 s ; aucun tenant ne doit faire monter le taux d'erreur des autres de plus de 0,1 point
- zero downtime — aucune fenêtre de maintenance ; déploiement pod par pod sur 40 pods, ancienne et nouvelle version en parallèle pendant au moins 7 jours ; un devis affiché reste réservable 15 min, y compris pendant la bascule
- observabilité sans surcharge excessive — au plus 2 % de CPU par pod pour métriques, journaux et traces (le traçage actuel de 100 % des appels fournisseurs en coûte 6,4 %) ; au plus 50 000 séries de métriques pour tout le service

### Objectifs

- Établir, à partir des preuves, une chaîne causale testable de la cascade du 8 septembre, et expliquer pourquoi le test d'août ne pouvait pas la révéler.
- Concevoir une campagne de tests de charge qui reproduit l'incident de façon fiable, puis sert de critère d'acceptation pour la nouvelle version, à coût d'observabilité maîtrisé.
- Concevoir un algorithme de recherche contraint par la politique voyage, borné en temps, avec une complexité analysée et un écart à l'optimum garanti que le produit peut afficher.
- Concevoir une régulation de charge qui isole les tenants les uns des autres et limite l'exposition au fournisseur lent, sans dépasser le quota ni le seuil de facturation de A.

### Livrables

- Plan de campagne : modèle de charge tiré des traces (formes de recherche, tenants, taux d'arrivée), scénarios (nominal, fournisseur lent, tenant bruyant, réessais, combinaison du 8 septembre, déploiement pendant le test), méthode de mesure justifiée, seuils de réussite et d'échec.
- Outillage de test en C# : générateur de charge, simulateurs de fournisseurs injectant latence et erreurs paramétrées à partir des seules p50/p99 disponibles, résultats ventilés par classe de tenant.
- Conception de l'algorithme : formulation, bornes, complexité en temps et en mémoire, comportement à l'expiration du budget, et comparaison d'au moins deux approches sur le jeu des 1 000 recherches.
- Code C# du cœur de recherche et de la régulation (par fournisseur et par tenant), avec tests unitaires et des tests générés qui vérifient que l'écart annoncé majore toujours l'écart réel.
- Plan d'observabilité respectant les plafonds de CPU et de séries, et plan de déploiement sans interruption avec ses critères d'arrêt.

### Critères de réussite

- Sur la version actuelle en préproduction, la campagne reproduit la cascade (A à p50 1,4 s et p99 6 s, lot Tellurion de 36 000 recherches envoyé avec une concurrence de 600, réessais clients) : au moins 30 % de 503 en moins de 10 min, sur 3 exécutions sur 3.
- Même scénario sur la nouvelle version : au plus 0,5 % de 503 pour les tenants autres que Tellurion, p95 inférieur à 2,5 s pour les Premium, mémoire par pod ≤ 6 Go, pause GC gen2 ≤ 100 ms, file du pool de threads ≤ 100.
- Sur les 1 000 recherches à 4 segments, avec un budget de 800 ms : écart à l'optimum ≤ 2 % en médiane et ≤ 5 % au p95 ; au plus 0,5 % de réponses vides quand une solution conforme existe ; l'écart annoncé par l'algorithme n'est jamais inférieur à l'écart réel.
- Jamais plus de 1 500 appels simultanés vers A, et au plus 5 % d'appels supplémentaires vers A (doublons, relances), soit ≤ 1,9 M par jour au volume actuel.
- Surcoût d'observabilité mesuré ≤ 2 % de CPU par pod pendant toute la campagne, ≤ 50 000 séries ; un déploiement pod par pod exécuté pendant le scénario nominal n'augmente pas le taux d'erreur de plus de 0,1 point.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T014 — Déboguer un planificateur multi-agent de robots d'entrepôt non déterministe et préparer son rollback

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | planification et recherche |
| Type | débogage d'un système non déterministe |
| Langage | C# |
| Charge | prototype (10 req/s, 10 GB) |
| Architecture | architecture hexagonale |
| Incident | timeouts intermittents |
| Failure mode | panne d'une zone |
| Mode | plan de rollback |

### Contexte

Dromos Robotique développe un planificateur de trajets pour flottes de robots mobiles d'entrepôt. Deux entrepôts pilotes l'utilisent pour le même client logisticien : Lyon (64 robots) et Saragosse (48 robots), en activité 24 h/24. Chaque nouvelle mission ou déviation déclenche la replanification d'une fenêtre d'au plus 12 robots sur 40 pas. Cela représente ≈ 10 requêtes par seconde au total ; plans et historique des réservations occupent ≈ 7 Go.

La v0.6 planifiait les robots un par un, par ordre de priorité. Le 7 septembre 2026, la v0.7 l'a remplacée par une recherche multi-agent optimale de type Conflict-Based Search, à expansion parallélisée, dont les trajets sont en moyenne 6 % plus courts. Depuis :
- 3 % des requêtes dépassent la deadline de 2 s du gestionnaire de flotte, qui réessaie alors jusqu'à deux fois ;
- Saragosse est sous 99,5 % de commandes à l'heure depuis trois semaines.

Le 17 septembre, la perte d'une zone de disponibilité en eu-par a imposé la restauration de la table de réservations de Lyon, suivie de 11 arrêts d'urgence de robots, sans collision.

Le client exige un plan de retour à la v0.6 pour le 2 octobre. L'équipe (4 développeurs) préférerait corriger la v0.7, mais n'arrive pas à reproduire ses échecs : la même entrée ne donne pas deux fois le même plan.

On te demande d'établir ce qui se passe, de rédiger le plan de rollback et de fixer les conditions d'un éventuel retour en avant.

### Architecture existante

Service .NET 8 en architecture hexagonale, une instance active par entrepôt :
- **Domaine** (`Dromos.Planning.Core`) : `CbsPlanner` de la v0.7 (niveau haut sur un arbre de contraintes, niveau bas en A* espace-temps, pas de 250 ms) ; le `PriorityPlanner` de la v0.6 (pas de 500 ms) reste compilé dans la solution.
- **Ports** : `IReservationStore`, `IWarehouseMap`, `IClock`, `IPlanPublisher`.
- **Adaptateurs** : API HTTP appelée par le gestionnaire de flotte du fabricant des robots (logiciel fermé, installé dans chaque entrepôt) ; Redis pour la table de réservations, snapshot RDB toutes les 5 min vers le stockage objet de la région, AOF désactivé ; publication des plans en MQTT.
- **Données** : une requête porte la position courante des robots à replanifier ; celle des autres robots n'est connue que par la table de réservations.
- **Déploiement** : par région, une VM de 8 vCPU (planificateur) et une VM de 2 vCPU (Redis) dans la même zone ; secours à froid de l'autre entrepôt (images et configuration prêtes, instances démarrées à la demande).
- **Sécurité embarquée** : un robot s'arrête d'urgence si son lidar voit un obstacle à moins de 0,6 m.

### Problème

Trois questions liées doivent être traitées ensemble.

1. D'où viennent le non-déterminisme et les dépassements de deadline de la v0.7 ? Une explication non étayée ne suffit pas : il faut pouvoir reproduire à la demande ce qui échoue.
2. Comment revenir à la v0.6 sans jamais violer la sécurité (deux robots sur la même cellule au même pas) ? Le format de la table de réservations a changé, des robots exécutent des plans v0.7 au moment de la bascule, et la région de secours doit rester compatible.
3. À quelles conditions mesurables une v0.7 corrigée pourra-t-elle revenir en production, compte tenu du SLA et du budget ?

### Preuves


Rejeu en préproduction de la requête `req-5d21` (Saragosse, 11 robots, dont deux face à face dans le couloir de largeur 1 de l'allée 14), 50 fois avec la même entrée et le même état de réservations :
```text
Empreinte du plan   Coût (somme des pas)   Occurrences   Durée médiane
p-3f1a              212                    19            0,41 s
p-9c07              212                     9            0,44 s
p-51de              212                     6            0,52 s
p-c2b4              213                     5            0,97 s
p-77e0              214                     4            1,12 s
p-0a9b              216                     2            1,48 s
p-e613              219                     2            1,71 s
dépassement > 2 s   —                       3            —
```
La v0.6, rejouée 50 fois sur la même entrée, donne toujours le même plan : 114 pas de 500 ms (soit 228 pas de 250 ms), en 0,18 s.


Production v0.7, du 7 au 27 septembre :
```text
                                                    Lyon     Saragosse
Requêtes de planification                           8,1 M    6,9 M
Dépassements de la deadline de 2 s                  1,9 %    4,3 %
Résultats NoSolution                                0,2 %    0,3 %
Couloirs de largeur 1 dans l'entrepôt               5        14
Part des dépassements sur des requêtes comptant
deux robots face à face dans un couloir             68 %     73 %
(ces requêtes font 9 % du total)
```
Sur un échantillon de 412 requêtes terminées en NoSolution puis rejouées avec la v0.6, 409 obtiennent un plan valide.

Journal du planificateur de Saragosse :
```text
2026-09-22T15:12:07.114Z POST /v1/plans mission=M-88123 X-Fleet-Attempt=1
2026-09-22T15:12:09.118Z POST /v1/plans mission=M-88123 X-Fleet-Attempt=2
2026-09-22T15:12:09.402Z plan ok mission=M-88123 plan=p-a41c attempt=1 durée=2 288 ms réservations validées=31
2026-09-22T15:12:10.051Z plan ok mission=M-88123 plan=p-6be2 attempt=2 durée=933 ms réservations validées=29
```
L'équipe attribue les dépassements à la contention du verrou : le compteur `Monitor Lock Contention Count` monte jusqu'à 1 900/s pendant les pics. Elle propose de remplacer la liste verrouillée par un `ConcurrentBag`, de passer `MaxDegreeOfParallelism` de 4 à 16 et de porter la deadline à 5 s.


Extraits du code de la v0.7.3 :
```csharp
// Dromos.Planning.Core/Cbs/CbsPlanner.cs
public sealed class CbsPlanner : IPathPlanner
{
    private static readonly IComparer<CtNode> ByCost =
        Comparer<CtNode>.Create((a, b) => a.Cost.CompareTo(b.Cost));
    private readonly SpaceTimeAStar _lowLevel;
    private readonly int _batchSize = 8;

    public PlanResult Plan(PlanningProblem problem, DateTime deadlineUtc)
    {
        var open = new SortedSet<CtNode>(ByCost);          // Min en O(log n)
        open.Add(CtNode.Root(problem, _lowLevel));
        while (open.Count > 0)
        {
            if (DateTime.UtcNow > deadlineUtc)
                return PlanResult.Timeout(open.Count);
            var batch = new List<CtNode>(_batchSize);
            while (batch.Count < _batchSize && open.Count > 0)
            {
                CtNode node = open.Min!;
                open.Remove(node);
                if (node.FirstConflict() is null)
                    return PlanResult.Ok(node.Paths, node.Cost);
                batch.Add(node);
            }
            var children = new List<CtNode>();
            Parallel.ForEach(batch, new ParallelOptions { MaxDegreeOfParallelism = 4 }, node =>
            {
                foreach (Constraint c in node.FirstConflict()!.Split())
                {
                    CtNode? child = node.WithConstraint(c, _lowLevel);   // replanifie un seul robot
                    if (child is null) continue;
                    lock (children) children.Add(child);
                }
            });
            foreach (CtNode child in children)
                open.Add(child);
        }
        return PlanResult.NoSolution();
    }
}

// Dromos.Planning.Http/PlanEndpoints.cs
app.MapPost("/v1/plans", async (PlanRequest dto, CbsPlanner planner, IReservationStore store) =>
{
    PlanningProblem problem = await PlanningProblem.LoadAsync(dto, store);
    PlanResult result = planner.Plan(problem, DateTime.UtcNow.AddSeconds(2));
    if (result.Status == PlanStatus.Ok)
        await store.CommitAsync(dto.MissionId, result.Paths);
    return result.ToHttpResult();
});
```


Journaux du 17 septembre (UTC) :
```text
10:35:02 redis-lyon    snapshot RDB ok → s3://dromos-par-snap/resa-lyon-20260917T103502.rdb (64 clés, 1 277 cellules réservées)
10:39:47 infra         zone eu-par-b indisponible : planner-lyon et redis-lyon injoignables
10:39:49 fleet-lyon    planificateur injoignable ; nouvelles missions retenues, robots en fin de plan courant
10:47:40 ops           démarrage du secours en eu-mad : planner v0.7.3 + redis
10:52:11 ops           restauration de resa-lyon-20260917T103502.rdb ; 37 réservations obsolètes supprimées (to < pas courant)
10:52:30 planner-mad   lyon : service rétabli
10:53:06 fleet-lyon    R-27 ARRÊT D'URGENCE (obstacle à 0,4 m) cellule (6,19)
...
11:04:51 fleet-lyon    R-08 ARRÊT D'URGENCE (obstacle à 0,5 m) cellule (3,11)
```
Onze arrêts d'urgence ont eu lieu entre 10:53 et 11:04, aucun ensuite. Pour chaque arrêt, heure à laquelle le gestionnaire de flotte a reçu le plan le plus récent parmi les robots impliqués : 10:35:41, 10:36:12, 10:36:58, 10:37:30, 10:37:33, 10:38:02, 10:38:47, 10:39:05, 10:39:18, 10:39:29, 10:39:44. Les journaux de planner-lyon sont restés sur la VM perdue. La zone est revenue à 11:26 ; Lyon est resté servi depuis eu-mad jusqu'au 18 septembre à 06:00.


Formats de la table de réservations, illustrés par le même déplacement du robot R-12 (pas comptés depuis 2026-01-01T00:00:00Z) :
```text
# v0.6 : une clé par (pas, cellule), pas de 500 ms, plus une clé de stationnement par robot
resa:lyon:44830811:14:7  → {"robot":"R-12","kind":"wait"}
resa:lyon:44830812:14:7  → {"robot":"R-12","kind":"move"}
resa:lyon:44830812:14:8  → {"robot":"R-12","kind":"move"}
park:lyon:R-12           → {"cell":"14-08","since":44830813}

# v0.7 : une clé par robot, pas de 250 ms, "to": null = stationné jusqu'au prochain plan
resa2:lyon:R-12 → {"v":2,"plan":"p-7d02","mission":"M-40517",
                   "cells":[{"x":14,"y":7,"from":89661620,"to":89661625},
                            {"x":14,"y":8,"from":89661624,"to":null}],
                   "edges":[{"a":[14,7],"b":[14,8],"t":89661624}]}
```
La v0.6 ne lit pas les clés `resa2:` et la v0.7 ne lit pas les clés `resa:`. En v0.6, un déplacement réserve la cellule de départ et celle d'arrivée au même pas.


Budget et SLA :
```text
Poste mensuel (€)                              Montant
Planificateur eu-par (VM 8 vCPU)               310
Planificateur eu-mad (VM 8 vCPU)               310
Redis eu-par et eu-mad (VM 2 vCPU chacune)     150
Snapshots, stockage objet, transfert            90
Observabilité (SaaS, 40 Go de journaux/mois)   360
Runners CI et rejeu                            240
Total                                        1 460   (plafond : 1 800)

Commandes à l'heure (%)   S36 (v0.6)   S37    S38    S39
Lyon                      99,7         99,6   99,2   99,5
Saragosse                 99,6         99,3   99,4   99,2
```
CPU moyen des VM du planificateur : 38 % à Lyon, 51 % à Saragosse, avec des pics à 97 % pendant les rafales de réessais. Le fabricant des robots répondra sous 3 semaines sur deux points : la possibilité d'envoyer une clé d'idempotence ou de désactiver les réessais, et le comportement d'un robot qui reçoit deux plans pour la même mission. Son API `GET /fleet/positions` donne les positions courantes, mais sa fraîcheur pendant une coupure réseau n'est pas documentée.


### Contraintes

- SLA élevé — 99,5 % des commandes préparées à l'heure, par entrepôt et par semaine (pénalité de 4 000 € par semaine sous le seuil) ; aucun arrêt d'urgence de robot imputable au planificateur
- multi-région — Lyon est planifié depuis la région eu-par, Saragosse depuis eu-mad (28 ms aller-retour) ; chaque région sert de secours à froid à l'autre et doit reprendre l'autre entrepôt en moins de 10 min, avec la même version du planificateur et le même format de réservations
- budget mensuel plafonné — 1 800 €/mois pour toute l'infrastructure du pilote, dont 1 460 € déjà engagés ; runners de rejeu, capacité de secours et double exécution v0.6/v0.7 doivent tenir dans les 340 € restants

### Objectifs

- Rendre le comportement de la v0.7 reproductible à la demande, puis classer, preuves à l'appui, les sources de non-déterminisme et de dépassement de deadline en séparant faits, hypothèses et inconnues.
- Établir un plan de rollback v0.7 → v0.6, par entrepôt et par région, qui préserve les invariants de sécurité à chaque instant, y compris pour les robots en mouvement et en cas de perte de zone pendant l'opération.
- Définir les correctifs de la v0.7 et des critères go/no-go chiffrés pour un retour en avant, compatibles avec le SLA et le budget.

### Livrables

- Stratégie de débogage : harnais de rejeu déterministe construit sur les ports existants (horloge, réservations, carte), maîtrise de l'ordonnancement du parallélisme, hypothèses classées avec l'expérience qui confirme ou réfute chacune.
- Plan de rollback séquencé : ordre des opérations (entrepôts, régions, secours), conversion v2 → v1 de la table de réservations et conversion inverse, invariants vérifiés avant, pendant et après, critères d'arrêt, durée et fenêtre choisie.
- Correctifs C# du planificateur et de l'adaptateur HTTP, avec tests de déterminisme et tests de propriété sur petites grilles comparés à une recherche exhaustive.
- Procédure de reconstitution de la table de réservations après perte de zone ou bascule de région, avec son coût mensuel.
- Critères go/no-go du retour à la v0.7 et chiffrage de l'ensemble (rejeu, double exécution, secours) dans le budget.

### Critères de réussite

- Harnais : 1 000 rejeux de chacune des 50 requêtes de référence (dont `req-5d21`) avec le même ordonnancement imposé donnent des plans identiques à l'octet ; avec des ordonnancements différents, toutes les exécutions résolues ont le même coût.
- Sur 10 000 instances aléatoires (grilles ≤ 6×6, ≤ 4 robots, horizon ≤ 20 pas, robots face à face en couloir inclus), le coût égale l'optimum de la recherche exhaustive dans 100 % des cas, sans aucun NoSolution quand une solution existe.
- Répétition du rollback en préproduction sur le rejeu du 17 septembre : 0 cellule occupée par deux robots au même pas et 0 échange de cellules entre deux robots dans la table convertie (contrôle indépendant du planificateur), ≤ 15 min par entrepôt, aucune mission perdue.
- Après correctifs, sur le rejeu des requêtes du 7 au 27 septembre : ≤ 0,3 % de dépassements de 2 s par site, p99 ≤ 1,2 s, et aucune mission ne conserve de réservations issues de plus d'un plan.
- Bascule simulée d'un entrepôt vers l'autre région en moins de 10 min, sans arrêt d'urgence sur 2 h de rejeu ; SLA ≥ 99,5 % par entrepôt pendant 4 semaines consécutives ; coût total ≤ 1 800 €/mois.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T015 — Revue d'une PR « focal loss » après l'effondrement du rappel d'un détecteur sonore de détresse

| Axe | Valeur |
|---|---|
| Piste | Machine Learning |
| Domaine | speech/audio ML |
| Type | class imbalance |
| Langage | Python |
| Charge | small-production (500 req/s, 500 GB) |
| Architecture | actor model |
| Incident | perte ou retard d'événements |
| Failure mode | checkpoint corrompu ou incomplet |
| Mode | code review |

### Contexte

Hestiane assure la téléassistance de personnes âgées vivant seules. Dans chaque logement, un boîtier écoute en continu et envoie des fenêtres audio de 2 s au service `ecoute`, qui détecte trois événements de détresse : chute, bris de verre, cri. Environ 1 000 boîtiers sont actifs, soit ≈ 500 fenêtres/s (43,2 M par jour). Environ 500 Go d'audio sont conservés pour l'entraînement et l'audit : un échantillon aléatoire de 0,5 % des fenêtres sur 30 jours, les fenêtres positives et le contexte des incidents audités. Les événements sont extrêmement rares : ≈ 1 fenêtre positive pour 40 000.

Chaque alerte part vers le logiciel certifié du centre d'appels, qui rappelle le bénéficiaire. Le contrat plafonne les fausses alarmes à 0,05 par boîtier-jour. Chaque incident connu par un autre canal (bouton d'appel, aidant, secours) est rapproché des alertes. Il compte comme détecté si une alerte du bon type est arrivée en moins de 30 s.

La PR #412 a été fusionnée et déployée le 15/09/2026 avec le modèle v15. Elle introduit une focal loss, un recalibrage automatique du seuil et une nouvelle politique de redémarrage des acteurs. Depuis, le rappel sur incidents audités est passé de 0,81 à 0,52, alors que le rapport joint à la PR annonçait 0,93.

Le 25/09, le responsable qualité a gelé les déploiements et exige une revue a posteriori de la PR avant toute remise en production. Le produit réclame un retour immédiat à v14. L'équipe ML propose au contraire de poursuivre avec γ = 3 et davantage de positifs. Tu es chargé de cette revue.

### Architecture existante

- **Boîtiers** (firmware 2.3.x) : chaque fenêtre de 2 s (PCM 16 kHz int16, 64 000 octets, numéro de séquence) part par WebSocket. Le boîtier garde 60 s d'audio et réémet toute fenêtre non acquittée.
- **Service `ecoute`** (Python 3.11, asyncio) : 5 hôtes de 4 vCPU et 2 Go, 200 acteurs par hôte (un par session de boîtier), boîte aux lettres bornée. Le runtime d'acteurs est maison : un superviseur par hôte, politique de redémarrage `preserve_mailbox` ou `fresh` (nouvelle boîte aux lettres). La passerelle acquitte une fenêtre dès son dépôt dans la boîte aux lettres.
- **Inférence** : un modèle par hôte, partagé par les 200 acteurs et exécuté dans un pool de 3 threads (`torch.set_num_threads(1)`). CNN sur log-mel 64×200, 5,3 M paramètres (21,2 Mo en float32), tête `head` = Linear(512, 256) → ReLU → Linear(256, 3) à sorties sigmoïdes. Alerte si la probabilité maximale atteint le seuil.
- **Registre** : l'entraînement publie `weights.tstream`, `manifest.json` (taille, sha256) et `calibration.json` (seuil). Le format maison `.tstream` (2024) enchaîne les tenseurs pour les copier un à un dans le modèle vivant sans doubler la mémoire. Un thread recharge le modèle à chaud quand le pointeur `current` change.
- **API d'alerte v2** : `confidence` y est documentée comme « probabilité estimée que l'événement soit réel ». Le logiciel certifié affiche en priorité « faible », traitée après les autres, toute alerte de confidence < 0,5.

### Problème

La revue doit établir quelles modifications de la PR #412 expliquent la chute de rappel, les fenêtres perdues et les alertes tardives, et dans quelle proportion. Les autres causes avancées doivent être confirmées ou écartées avec les données disponibles ou des mesures à préciser : firmware 2.3.1, patch noyau de l'hôte h4, rareté « naturelle » des positifs. Aucune conclusion ne doit reposer sur les seules métriques du rapport d'évaluation.

Elle doit ensuite dire ce qui doit changer avant tout redéploiement, et si le retour à v14 est sûr avec le code actuellement en production. Il faut enfin définir comment le modèle sera évalué, seuillé et calibré pour une prévalence de 1/40 000, et avec quelle sémantique les fenêtres seront livrées aux acteurs. Le schéma d'alerte v2, le budget de 2 Go par hôte et la contrainte de latence ne doivent pas bouger.

### Preuves


PR #412, 2 approbations. Description : focal loss (γ = 2, α = 0,9) à la place de BCE + suréchantillonnage des positifs (×400) ; seuil recalculé en fin d'entraînement pour viser un rappel de 0,93 ; nouvelle tête FocalHead (buffer `prior_logit` pour l'initialisation) et `strict=False` « pour pouvoir recharger v14 en cas de retour arrière » ; acteurs redémarrés à neuf après un crash ou un rechargement (état PCEN de session réinitialisé) ; boîte aux lettres réduite « pour tenir dans 2 Go », NACK au boîtier si elle est pleine. Diff côté entraînement :
```python
# training/losses.py (nouveau)
class FocalLoss(nn.Module):
    """Focal loss binaire multi-label (Lin et al., 2017).
    alpha : poids de la classe positive (rare) ; gamma : focalisation."""

    def __init__(self, alpha: float = 0.9, gamma: float = 2.0) -> None:
        super().__init__()
        self.alpha, self.gamma = alpha, gamma

    def forward(self, logits: Tensor, targets: Tensor) -> Tensor:
        p = torch.sigmoid(logits)
        ce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        p_t = p * targets + (1 - p) * (1 - targets)
        alpha_t = self.alpha * (1 - targets) + (1 - self.alpha) * targets
        return (alpha_t * (1 - p_t) ** self.gamma * ce).mean()

# training/calibrate.py (nouveau)
def choose_threshold(model, splits, target_recall: float = 0.93):
    scores, labels = predict(model, splits["test_bal"])  # max des 3 sorties, « au moins un événement »
    order = np.argsort(-scores)
    recall = np.cumsum(labels[order]) / labels.sum()
    k = int(np.searchsorted(recall, target_recall))
    thr = float(scores[order][k])
    return thr, {"threshold": thr, "recall": float(recall[k]),
                 "roc_auc": float(roc_auc_score(labels, scores)),
                 "accuracy_natural": accuracy(model, splits["holdout_natural"], thr)}
```
```diff
# training/train.py
-    sampler = WeightedRandomSampler(weights, num_samples=len(ds), replacement=True)
-    loader = DataLoader(ds, batch_size=256, sampler=sampler, num_workers=8)
+    loader = DataLoader(ds, batch_size=256, shuffle=True, num_workers=8)
```


Diff côté service (chargement du modèle) et lecteur `.tstream` existant :
```diff
# ecoute/model_store.py
     def reload(self, uri: str) -> None:
         path = self._fetch(uri)
-        self.model.load_state_dict(dict(tstream.iter_tensors(path)))
-        self.threshold = settings.THRESHOLD
+        res = self.model.load_state_dict(dict(tstream.iter_tensors(path)), strict=False)
+        if res.missing_keys or res.unexpected_keys:
+            log.warning("load_state_dict: missing=%s unexpected=%s uri=%s",
+                        res.missing_keys, res.unexpected_keys, uri)
+        self.threshold = self._fetch_json(uri, "calibration.json")["threshold"]
         self.version = uri
```
```python
# ecoute/tstream.py (inchangé depuis 2024)
def iter_tensors(path):
    with open(path, "rb") as f:
        while len(hdr := f.read(2)) == 2:
            name = f.read(struct.unpack("<H", hdr)[0]).decode()
            code, ndim = f.read(2)
            shape = struct.unpack(f"<{ndim}I", f.read(4 * ndim))
            (nbytes,) = struct.unpack("<Q", f.read(8))
            buf = f.read(nbytes)
            if len(buf) < nbytes:
                return
            yield name, torch.frombuffer(bytearray(buf), dtype=DTYPES[code]).reshape(shape)
```


Diff côté acteurs et passerelle :
```diff
# ecoute/actors.py
 class SessionActor(Actor):
-    mailbox_size = 64
+    mailbox_size = 8

     async def on_message(self, win: AudioWindow) -> None:
         p = await self.loop.run_in_executor(self.pool, self.store.score, win.pcm, self.pcen)
         if p.max() >= self.store.threshold:
             await self.alerts.publish(AlertV2(
                 device_id=self.device_id, event_type=EVENTS[int(p.argmax())],
                 confidence=float(p.max()), ts=win.ts_end))

-SUPERVISION = Supervision(restart="preserve_mailbox", max_restarts=3, within_s=60)
+SUPERVISION = Supervision(restart="fresh", max_restarts=1, within_s=60)
+
+async def on_model_reloaded(registry, supervisor) -> None:
+    for actor in list(registry.actors()):
+        await supervisor.restart(actor)
+        await asyncio.sleep(0.05)

# ecoute/gateway.py
     async def on_window(self, dev: str, win: AudioWindow) -> None:
         actor = self.registry.get_or_spawn(dev)
-        await actor.mailbox.put(win)
-        await self.ack(dev, win.seq)
+        try:
+            actor.mailbox.put_nowait(win)
+        except asyncio.QueueFull:
+            await self.nack(dev, win.seq)
+            return
+        await self.ack(dev, win.seq)
```


Journaux (UTC), hôtes h2 et h4 ; les mêmes avertissements apparaissent sur les 5 hôtes le 15/09.
```text
2026-09-14T23:40:18Z trainer   INFO    publish models/v15 manifest.size=21212632 sha256=4be1…c07a calibration.threshold=0.27
2026-09-15T09:41:12Z ecoute-h2 WARNING load_state_dict: missing=['head.prior_logit'] unexpected=[] uri=models/v14/weights.tstream
2026-09-15T10:05:03Z ecoute-h2 INFO    reload uri=models/v15/weights.tstream fetched_bytes=21210521
2026-09-15T10:05:04Z ecoute-h2 WARNING load_state_dict: missing=['head.2.weight', 'head.2.bias'] unexpected=[] uri=models/v15/weights.tstream
2026-09-15T10:05:04Z ecoute-h2 INFO    actors: rolling restart n=200 policy=fresh
2026-09-15T10:05:17Z ecoute-h2 INFO    actors: rolling restart done dropped_windows=9
2026-09-19T06:10:31Z ecoute-h4 INFO    boot kernel=6.8.0-47 (patch de sécurité, précédemment 6.8.0-45)
2026-09-19T06:10:44Z ecoute-h4 WARNING load_state_dict: missing=['head.2.weight', 'head.2.bias'] unexpected=[] uri=models/v15/weights.tstream
```


Rapport joint à la PR (modèle v15 évalué dans l'environnement d'entraînement) et rapprochement des incidents audités :
```text
seuil 0,27 · rappel 0,93 · ROC-AUC 0,991   test_bal : 3 100 positives, 3 100 négatives tirées du catalogue de sons confondants
accuracy 99,97 %                            holdout_natural : 4,32 M fenêtres de l'échantillon aléatoire, dont 108 positives

période / hôtes                          incidents   détectés < 30 s   rappel
01–14/09, tous (v14, seuil 0,62)               212               172     0,81
15–24/09, h1–h3 et h5                          123                71     0,58
15–18/09, h4                                    11                 5     0,45
19–24/09, h4                                    13                 0     0,00
15–24/09 par firmware : 2.3.0 → 52/99 (0,53) ; 2.3.1 → 24/48 (0,50)
71 incidents manqués depuis le 15/09 : 5 alertés entre 31 et 44,8 s, 66 jamais alertés (dont 1 dont les fenêtres ont été acquittées puis abandonnées)
```


Exploitation, 01–14/09 puis 15–24/09 : fausses alarmes 0,031 puis 0,036 par boîtier-jour (h4 n'a émis aucune alerte, vraie ou fausse, depuis le 19/09 06:10) ; p99 détection → alerte 1,4 s puis 4,9 s (maximum 44,8 s) ; p99 d'inférence 41 puis 43 ms ; NACK : aucun, puis 1,2 % des fenêtres, concentrés dans les 2 min qui suivent une reconnexion de boîtier ; redémarrages d'acteurs sur exception : ≈ 290 par jour avant comme après le 15/09, surtout des `ValueError` sur des fenêtres de taille impaire envoyées à la reconnexion par le firmware 2.3.1 (un tiers des boîtiers depuis août) ; fenêtres acquittées puis abandonnées : aucune, puis ≈ 2 300 par jour ; RSS par hôte 1,58 puis 1,62 Go, avec un pic à 1,93 Go pendant les redémarrages progressifs ; part des alertes de confidence < 0,5 : 9 % puis 64 %. Extrait du schéma v2 :
```json
{"$id": "alert-v2", "type": "object", "additionalProperties": false,
 "required": ["device_id", "event_type", "confidence", "ts"],
 "properties": {"device_id": {"type": "string", "pattern": "^HB-[0-9]{6}$"},
                "event_type": {"enum": ["FALL", "GLASS_BREAK", "SCREAM"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "ts": {"type": "string", "format": "date-time"}}}
```
Non disponibles : la politique de réémission du firmware 2.3 (délais, nombre d'essais), les journaux de l'outil d'upload du registre (conservés 7 jours, effacés), et l'usage que le logiciel certifié fait de `confidence` au-delà de l'affichage.


### Contraintes

- p99 très faible — détection → alerte p99 < 3 s, mesuré de la fin de la fenêtre sur le boîtier à la publication de l'alerte ; inférence CPU p99 < 80 ms par fenêtre
- faible consommation mémoire — 2 Go de RAM par hôte (limite cgroup, OOM-kill au-delà) pour 200 acteurs ; modèle servi ≤ 25 Mo ; une fenêtre PCM pèse 64 000 octets
- compatibilité API stricte — schéma d'alerte v2 figé (device_id, event_type ∈ {FALL, GLASS_BREAK, SCREAM}, confidence ∈ [0, 1], ts), validé strictement par le logiciel certifié du centre d'appels ; toute modification, y compris de la sémantique documentée de confidence, impose une recertification de 6 mois

### Objectifs

- Relier chaque modification de la PR #412 à ses effets observables en production et répartir la chute de rappel (0,81 → 0,52) entre les causes établies, avec des intervalles de confiance, en séparant faits, hypothèses et inconnues.
- Fixer les conditions d'un redéploiement ou d'un retour à v14 sûrs, pour le modèle comme pour le code de service.
- Définir un protocole d'évaluation, de choix du seuil et de calibration de `confidence` adapté à une prévalence de 1/40 000 et au plafond de fausses alarmes, sans modifier l'API v2.
- Redéfinir la sémantique de livraison des fenêtres aux acteurs (perte, doublon, retard) dans 2 Go par hôte et sous p99 < 3 s.

### Livrables

- Revue écrite de la PR #412 : commentaires classés bloquant / majeur / mineur, chacun rattaché à des lignes du diff, à une preuve de production et à un effet estimé ; verdict et conditions de levée du gel.
- Analyse chiffrée de la chute de rappel : décomposition par cause, intervalles adaptés à quelques dizaines d'incidents, et liste des rejeux hors ligne à exécuter pour trancher, avec les artefacts nécessaires.
- Code Python et tests : chargement et remplacement du modèle servi, et livraison des fenêtres aux acteurs, avec les garanties retenues (intégrité, concurrence, mémoire, perte, doublon, retard) et un test de redémarrage sous charge.
- Protocole d'évaluation et de calibration : découpage des données, métriques retenues et rejetées avec justification, point de fonctionnement exprimé en fausses alarmes par boîtier-jour, méthode de calibration de `confidence` et vérification de compatibilité avec le logiciel certifié.
- Plan de remise en production : ordre des changements, canari, critères d'arrêt, retour arrière et métriques de surveillance compatibles avec le budget mémoire.

### Critères de réussite

- Au rejeu hors ligne des 147 incidents audités du 15 au 24/09 avec le modèle et le seuil proposés : rappel ≥ 0,80 avec une borne inférieure de Wilson à 95 % ≥ 0,72, pour ≤ 0,05 fausse alarme par boîtier-jour, borne supérieure de l'intervalle à 95 % comprise, estimée sur au moins 2 000 boîtier-jours de trafic à prévalence naturelle.
- Aucun artefact incomplet ou incohérent avec son manifest n'est servi : test d'injection sur 1 000 artefacts altérés aléatoirement (troncature, octets modifiés, clé absente ou en trop) ; le modèle précédent reste servi et une alerte d'exploitation part en moins de 1 min.
- Test de charge à 500 fenêtres/s avec redémarrage progressif des 5 hôtes et rechargement de modèle : 0 fenêtre acquittée perdue (vérifié par les numéros de séquence), 0 alerte en double reçue par le centre d'appels, p99 détection → alerte < 3 s et inférence p99 < 80 ms.
- RSS ≤ 1,9 Go par hôte à tout instant de ce test, boîtes aux lettres pleines et rechargement en cours compris ; modèle servi ≤ 25 Mo.
- Toutes les alertes émises valident le JSON Schema v2 certifié ; erreur de calibration (ECE sur 10 intervalles) de `confidence` ≤ 0,05, mesurée sur les alertes émises à prévalence naturelle, et ≤ 10 % des vraies alertes affichées en priorité « faible ».

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T016 — Forensic en Bash d'une fuite mémoire synchronisée sur le démon d'autorisation fermé d'une banque

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | problèmes multi-étapes |
| Type | raisonnement probabiliste |
| Langage | Bash |
| Charge | high-scale (100k req/s, 100 TB) |
| Architecture | multi-région actif/passif |
| Incident | fuite mémoire progressive |
| Failure mode | panne d'une région |
| Mode | forensic debugging |

### Contexte

La banque Solverin autorise les paiements par carte de ses clients : environ 100 k messages ISO 8583 par seconde en journée, 145 k/s à la pointe de midi, 6,1 milliards par jour. Deux régions de 200 hôtes Linux fonctionnent en actif/passif. La région passive traite en miroir tous les messages, réponses ignorées, pour garder ses compteurs et ses caches à jour.

Chaque hôte exécute authd, le démon d'autorisation d'un éditeur, livré en binaire fermé. Depuis l'été, des hôtes sont tués par l'OOM killer après une dizaine de jours de fonctionnement, sans que personne n'ait relié ces incidents entre eux. Le 21/09/2026, entre 12:58 et 13:45 UTC, 38 hôtes de la région primaire ont été tués. Le p99 a atteint 1,9 s ; la bascule vers la région passive a été décidée à 13:52 et terminée à 14:20. Les 200 hôtes de cette région avaient tous été redémarrés dans la nuit du 18 au 19/09 pour un correctif du noyau.

Nous sommes le 22/09 à 08:00 UTC. L'éditeur attribue le phénomène à la fragmentation de malloc. La direction des risques veut savoir quand, et avec quelle probabilité, la région désormais active risque la même défaillance groupée, et comment l'éviter jusqu'au correctif. La conformité exige que chaque conclusion repose sur des preuves collectées, horodatées et archivées. Tu mènes l'investigation.

### Architecture existante

- **Hôtes** : RHEL 8 (noyau 4.18), 16 vCPU, 32 Go de RAM, sans swap. Outils présents : bash 4.4, coreutils, gawk 4.2, procps-ng (ps, pmap), sysstat (historique `sar` de 28 jours), journald (14 jours) ; les journaux sont aussi archivés dans le SIEM. Ni gdb ni perf.
- **authd 4.7.2** : un processus parent forke au démarrage 8 workers, qui portent le même nom de processus et traitent les messages. Les tables de BIN et de clés chargées par le parent sont partagées en copie sur écriture. Si un worker meurt sur un signal, le parent arrête tous les workers et sort : c'est la « garde d'intégrité » documentée par l'éditeur. systemd relance alors le service en 11 à 14 min (clés chargées depuis l'HSM, préchauffage des caches). L'HSM de chaque région accepte au plus 6 chargements de clés simultanés.
- **Répartition** : les acquéreurs ouvrent des connexions TCP persistantes, réparties par un équilibreur L4 et attachées à un hôte jusqu'à leur coupure. Un hôte tient 950 messages/s avec un p99 < 150 ms.
- **Supervision** : un agent existant relève toutes les 5 min le VmRSS de chaque processus authd et la MemAvailable de l'hôte (35 jours de rétention). Un cron de garde écrit par la banque en 2019 tourne toutes les 5 min sur chaque hôte.
- **Accès** : uniquement par le bastion SSH, 50 sessions simultanées au plus, commandes exécutées via sudo avec journalisation des entrées/sorties.

### Problème

Il faut reconstituer, preuves à l'appui, la chaîne qui mène d'une croissance mémoire lente à la perte de 38 hôtes en 47 minutes, puis à la bascule. Il faut aussi expliquer pourquoi les garde-fous existants n'ont rien empêché, et départager les hypothèses sur l'origine de la croissance, dont celle de l'éditeur, sans accès au code ni débogueur.

Il faut ensuite estimer, avec un modèle probabiliste explicite, le risque de défaillances simultanées dans la région désormais active d'ici la fin du mois, puis jusqu'au correctif. Enfin, il faut un plan d'action : redémarrages échelonnés, garde mémoire, éventuel retour sur la région primaire. Ce plan doit respecter la capacité, la limite de l'HSM et les pointes de fin de mois. Toute collecte passe par des scripts Bash en lecture seule compatibles avec les exigences d'audit.

### Preuves


Chronologie reconstituée et journaux d'un hôte tombé le 21/09 :
```text
10/09 02:00        vague 1 du correctif authd 4.7.2 : 64 hôtes primaires redémarrés
13/09 02:00        vague 2 : 68 hôtes ; 16/09 02:00 : vague 3, 68 hôtes
17/09 → 20/09      6 OOM isolés (4 de la vague 1, 2 de la vague 2), tickets clos « défaillance matérielle probable »
18/09 22:00 → 01:40  redémarrage des 200 hôtes passifs (correctif noyau)
21/09 12:58 → 13:45  38 OOM : 29 de la vague 1, 7 de la vague 2, 2 de la vague 3 (ces deux derniers après 13:30)
21/09 13:00 → 15:00  part des messages 0420 (annulations) : 11 %, contre 3,9 % d'ordinaire

2026-09-21T13:05:12Z h-p-052 kernel: authd invoked oom-killer: gfp_mask=0x6280ca(GFP_HIGHUSER_MOVABLE|__GFP_ZERO), order=0, oom_score_adj=0
2026-09-21T13:05:12Z h-p-052 kernel: Out of memory: Killed process 118834 (authd) total-vm:5712344kB, anon-rss:3361208kB, file-rss:9212kB, shmem-rss:702144kB, UID:1207 pgtables:7412kB oom_score_adj:0
2026-09-21T13:05:13Z h-p-052 authd[4127]: E7713 worker 6 (pid 118834) terminated by signal 9: integrity guard, stopping all workers
2026-09-21T13:05:14Z h-p-052 systemd[1]: authd.service: Main process exited, code=exited, status=77/n/a
2026-09-21T13:25:52Z h-p-052 authd[90211]: I0001 ready: 8 workers, keys loaded (HSM queue 7m41s), caches warm
```


Cron de garde, identique sur les 400 hôtes. Dans l'archive SIEM, sa dernière entrée date du 2025-11-03 (h-s-117).
```bash
#!/bin/bash
# /usr/local/sbin/authd-watchdog — cron */5, banque, 2019
PIDFILE=/var/run/authd/authd.pid
LIMIT_PCT=90
pid=$(cat "$PIDFILE") || exit 0
rss_kb=$(ps -o rss= -p "$pid")
total_kb=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
if (( rss_kb * 100 > total_kb * LIMIT_PCT )); then
    logger -t authd-watchdog "rss=${rss_kb}kB > ${LIMIT_PCT}% of ${total_kb}kB, restarting authd"
    systemctl restart authd
fi
```


Échantillon de la région primaire, relevé le 20/09 à 12:00 par la supervision. La pente est celle d'une régression linéaire sur 72 h (points toutes les 5 min) de la somme des VmRSS des 8 workers ; pour h-p-023, elle ne couvre que la période depuis son redémarrage.
```text
hôte     vague  dernier démarrage   messages/j   part 0420   pente Σ VmRSS workers
h-p-008  1      10/09 02:04         30,9 M       3,7 %       1 548 Mo/j
h-p-023  1      17/09 10:47 (OOM)   29,4 M       6,1 %       2 461 Mo/j
h-p-052  1      10/09 02:11         31,2 M       3,6 %       1 539 Mo/j
h-p-071  2      13/09 02:06         28,7 M       3,9 %       1 507 Mo/j
h-p-102  2      13/09 02:15         34,8 M       3,3 %       1 590 Mo/j
h-p-137  2      13/09 02:09         30,1 M       5,8 %       2 339 Mo/j
h-p-164  3      16/09 02:02         29,8 M       4,0 %       1 641 Mo/j
h-p-188  3      16/09 02:12         31,6 M       3,4 %       1 452 Mo/j
```

- Relevés complémentaires : une heure après le démarrage d'authd, la MemAvailable vaut ≈ 18,4 Go. Sur h-p-052, elle baisse chaque jour d'environ 1,1 Go entre 10:00 et 13:00 (0,6 Go le dimanche), puis remonte. La RSS du processus parent reste entre 186 et 193 Mo depuis le 10/09. La part des messages 0420 dans le trafic total était de 1,2 % en septembre 2025, 2,6 % en mars 2026 et 3,9 % en septembre 2026. Le 20/09 à 16:12, un `pmap -X` lancé à la main sur un worker de h-p-071 a coïncidé avec un p99 de 212 ms sur cet hôte pendant 40 s (lien non établi).
- Réponse de Kerval Systems (ticket KS-88213) : « croissance attribuée à la fragmentation des arenas glibc ; recommandation : MALLOC_ARENA_MAX=2 ». Pour ouvrir un correctif, l'éditeur exige des courbes mémoire par worker sur au moins 7 jours, les versions exactes (binaire, glibc, noyau), les corrélations éventuelles avec des types de messages et un fichier de trafic ISO 8583 anonymisé qui reproduise le phénomène sur son banc.
- Région désormais active : sur 23 hôtes échantillonnés le 20/09 à 12:00, soit 36 h après leur redémarrage, la pente médiane vaut 1,55 Go/j, le p90 1,68 et le maximum 2,44 (2 hôtes au-delà de 2 Go/j). Depuis la bascule, les connexions des acquéreurs se sont rétablies sur cette région, mais leur répartition par hôte n'a pas été relevée. Capacité : 153 hôtes nécessaires à la pointe ordinaire (145 k/s), 187 aux pointes de fin de mois (30/09 et 01/10, ≈ 177 k/s), 33 au creux de 02:00 à 05:00 (≈ 31 k/s). L'arrêt propre d'un hôte avec vidage de ses connexions n'est documenté qu'à partir d'authd 4.8 ; son comportement en 4.7.2 est inconnu. Un retour sur la région primaire exige une fenêtre de changement de 45 min.

### Contraintes

- forte croissance des données — trafic d'autorisation +31 %/an et pointes de fin de mois +22 % ; journal des autorisations ≈ 0,3 To compressé par jour (≈ 120 To sur 13 mois glissants) ; les relevés et scripts doivent rester exploitables quand le parc et les volumes grossissent
- auditabilité complète — toute commande passe par le bastion SSH et sudo avec journalisation des entrées/sorties ; chaque sortie collectée est horodatée en UTC, hachée (sha256) et versée au coffre de preuves, conservé 10 ans ; toute action qui n'est pas en lecture seule exige un ticket de changement approuvé
- legacy non remplaçable à court terme — binaire C fermé authd 4.7.2 (éditeur Kerval Systems), non remplaçable avant 2028 ; ni recompilation, ni instrumentation, ni préchargement de bibliothèque ; pas de gdb ni de nouvel agent en production ; correctif éditeur livré sous 90 jours après un dossier de preuves recevable, puis 4 semaines de certification

### Objectifs

- Reconstituer la chaîne causale de la défaillance du 21/09, de la croissance mémoire jusqu'à la bascule, et expliquer l'inefficacité des garde-fous existants, en séparant faits établis, hypothèses et inconnues.
- Départager les hypothèses sur l'origine de la croissance, dont la fragmentation avancée par l'éditeur, par des mesures discriminantes réalisables en lecture seule et sans perturber l'autorisation.
- Quantifier le risque de défaillances simultanées dans la région désormais active, d'ici la fin du mois puis jusqu'au correctif, en distinguant l'incertitude sur les paramètres de la variabilité entre hôtes.
- Définir un plan de maîtrise du risque (redémarrages, garde mémoire, retour éventuel sur la région primaire) compatible avec la capacité, l'HSM et l'audit.

### Livrables

- Plan d'investigation en étapes : question traitée, données et commandes, coût pour la production, critère de passage à l'étape suivante.
- Scripts Bash avec leurs tests : collecte en lecture seule via le bastion (parallélisme borné, délais, reprise idempotente, horodatage UTC, sha256, manifeste), agrégation gawk des pentes par worker et par hôte avec leur incertitude, et garde mémoire utilisable jusqu'au correctif.
- Modèle probabiliste du temps avant OOM par hôte et du nombre d'hôtes perdus à une même pointe : hypothèses, paramètres estimés, analyse de sensibilité et rétro-test sur la région primaire.
- Plan de redémarrages échelonnés et décision argumentée sur un retour vers la région primaire : calendrier, contraintes respectées, risque résiduel chiffré, critères d'arrêt.
- Dossier de preuves pour l'éditeur et description de la chaîne de traçabilité de chaque artefact.

### Critères de réussite

- Un passage de collecte couvre les 400 hôtes en ≤ 30 min avec ≤ 50 sessions simultanées, n'écrit rien hors du répertoire de travail déclaré et ne lit aucun fichier `smaps` d'un worker pendant les pointes ; deux passages sur des données inchangées produisent des manifestes identiques hors horodatage, chaque fichier étant référencé par son sha256 dans un manifeste lui-même haché et versé au coffre.
- Rétro-test : calé uniquement sur les données antérieures au 17/09, le modèle donne au 21/09 une probabilité ≥ 10 % à la perte d'au moins 25 hôtes à la même pointe, et un nombre attendu d'OOM isolés du 17 au 20/09 compris entre 3 et 9.
- Le plan retenu ramène sous 1 % la probabilité de perdre plus de 10 hôtes à une même pointe d'ici le correctif, sous des hypothèses de croissance explicites, avec en permanence au moins 153 hôtes disponibles aux pointes ordinaires, 187 aux pointes de fin de mois, et au plus 6 redémarrages simultanés par région.
- Rejoué sur les 35 jours de relevés de la supervision, le garde mémoire proposé aurait signalé au moins 24 h à l'avance au moins 95 % des OOM observés, avec au plus une fausse alerte par semaine sur les 400 hôtes.
- Le dossier éditeur contient toutes les pièces exigées par Kerval, chacune rattachée à une entrée du journal sudo et à son sha256, sans aucune donnée de carte en clair (PAN masqués, conformément à PCI DSS).

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": false,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T017 — Doubles affectations d'un dispatch de coursiers Node.js en pleine migration ville par ville

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | problem solving sous contraintes |
| Type | approximation sous contrainte de temps |
| Langage | JavaScript |
| Charge | small-production (500 req/s, 500 GB) |
| Architecture | service mesh |
| Incident | duplication sporadique d'opérations |
| Failure mode | perte de cache |
| Mode | migration progressive |

### Contexte

Gamelo livre des repas dans 40 villes françaises. Depuis juin, l'équipe Dispatch migre ville par ville l'affectation des commandes aux coursiers, du monolithe PHP vers un service Node.js. Le monolithe donne chaque commande au coursier libre le plus proche, pour un délai moyen de prise en charge de 8,6 min. Le service Node recalcule à chaque appel l'affectation optimale de toute la zone par l'algorithme hongrois, et le délai tombe à 7,9 min. 26 villes sont migrées ; 14 restent à faire avant le gel des changements du 16/11, qui précède le pic de fin d'année (Black Friday le 27/11).

En pointe, le service Node reçoit ≈ 500 req/s pour les villes migrées : ≈ 450/s de positions de coursiers, ≈ 4 appels/s à POST /assign, le reste en lectures. Les historiques de commandes et de positions sur 90 jours pèsent ≈ 480 Go.

Environ 0,3 % des commandes des villes migrées subissent une double affectation : deux coursiers pour une même commande, ou un coursier engagé sur deux commandes sans rapport. Chaque doublon coûte en moyenne 4,10 € de course payée, plus d'éventuels remboursements. L'équipe soupçonne les bascules de ville, pendant lesquelles les deux systèmes pourraient servir la même ville. Au pic, les zones les plus denses devraient compter jusqu'à 260 coursiers disponibles, contre 180 aujourd'hui.

Nous sommes le 26/10/2026. Tu dois décider comment finir la migration à temps, sans doublons et avec un temps de calcul maîtrisé.

### Architecture existante

- **Service mesh** : Istio (sidecars Envoy) dans 2 régions. Chaque ville est rattachée à une région et bascule vers l'autre en cas de panne.
- **order-flow** (équipe Commandes, 2 développeurs) : appelle `POST /v1/zones/{zone}/assign` quand une commande devient à affecter. Il pose `x-zone-id` et `x-dispatch-backend` (`node` ou `legacy`), valeur lue par ville dans le service de configuration avec un cache de 60 s. Une commande reste « à affecter » tant qu'order-flow n'a pas reçu de réponse positive ; après un 409, il rappelle 3 s plus tard.
- **dispatch-node** (Node.js 20, 6 à 9 pods de 1 vCPU / 1 Gio par région, HPA sur le retard p99 de la boucle d'événements) : chaque pod sert les zones que lui attribue le hachage cohérent de `x-zone-id`. Positions et statuts des coursiers sont dans Redis ; les ETA viennent du service de routage (matrice origine-destination). Le coursier retenu reçoit une offre qu'il a 90 s pour accepter, et l'affectation est publiée sur Kafka (`assignment.created`).
- **dispatch-legacy** (PHP 8.1) : glouton ; le statut des coursiers est verrouillé dans MySQL (`SELECT … FOR UPDATE`), primaire en région 1, réplique asynchrone en région 2, promotion manuelle en ≈ 12 min.
- **App coursier** : accepte ou refuse chaque offre et permet de porter jusqu'à deux commandes à la fois. Une nouvelle version met ≈ 2 semaines à passer par les stores.

### Problème

Il faut établir, preuves à l'appui, d'où viennent les doubles affectations et dans quelles conditions elles apparaissent, sans s'arrêter à l'hypothèse des bascules de ville. Il faut aussi dire ce que deviennent les engagements en cours lors d'un redémarrage de pod, d'un changement du nombre de pods, d'un retour arrière de ville et d'une panne de région.

Il faut ensuite un calcul d'affectation dont le temps est borné quelle que soit la taille de la zone. Sa perte de qualité par rapport à l'optimum doit être mesurée, et il doit conserver l'essentiel du gain sur le délai de prise en charge avec 260 coursiers dans une zone. Enfin, il faut réordonner la migration des 14 villes restantes pour tenir le gel avec 3 développeurs, en décidant ce qui doit être corrigé avant, pendant ou après.

### Preuves


Configuration du mesh pour le dispatch :
```yaml
# mesh/dispatch.yaml — généré depuis le gabarit « standard-http » de l'équipe plateforme (mars 2025)
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata: { name: dispatch, namespace: logistics }
spec:
  hosts: [dispatch.logistics.svc.cluster.local]
  http:
    - match: [{ headers: { x-dispatch-backend: { exact: node } } }]
      route: [{ destination: { host: dispatch-node } }]
      timeout: 1s
      retries: { attempts: 2, perTryTimeout: 150ms, retryOn: "5xx,reset,connect-failure,retriable-4xx" }
    - route: [{ destination: { host: dispatch-legacy } }]
      timeout: 2s
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata: { name: dispatch-node, namespace: logistics }
spec:
  host: dispatch-node
  trafficPolicy:
    loadBalancer: { consistentHash: { httpHeaderName: x-zone-id } }
```


Route d'affectation du service Node :
```javascript
// src/routes/assign.js — dispatch-node 1.9.2 (inchangé en 1.9.3)
const reservations = new Map(); // courierId -> { orderId, expiresAt }

router.post('/v1/zones/:zoneId/assign', async (req, res) => {
  const zone = req.params.zoneId;
  const { orderId } = req.body;
  const t = timer();
  const pool = await orders.pendingInZone(zone);            // commandes à affecter de la zone
  const now = Date.now();
  const couriers = (await courierIndex.available(zone))    // statut « libre » dans Redis
    .filter((c) => !((reservations.get(c.id)?.expiresAt ?? 0) > now));
  const eta = await t.lap('routing', routing.table(pool.map((o) => o.pickup), couriers.map((c) => c.pos)));
  const n = Math.max(pool.length, couriers.length);
  const match = t.lapSync('hungarian', () => hungarian(padSquare(eta, n, 1e9)));  // O(n³)
  const i = pool.findIndex((o) => o.id === orderId);
  const j = i < 0 ? -1 : match[i];
  if (j < 0 || j >= couriers.length || eta[i][j] >= 1e9) {
    return res.status(409).json({ orderId, retryAfterMs: 3000 });
  }
  const courier = couriers[j];
  reservations.set(courier.id, { orderId, expiresAt: Date.now() + 90_000 });
  await push.offer(courier.id, { orderId, etaS: eta[i][j] });
  await bus.publish('assignment.created', { orderId, courierId: courier.id, zone }, { key: orderId });
  log.info({ orderId, courierId: courier.id, etaS: eta[i][j], nCouriers: couriers.length, ...t.laps() }, 'assign');
  res.json({ orderId, courierId: courier.id, etaS: eta[i][j] });
});
```


Journaux de deux cas signalés le 24/10 (UTC, champs abrégés) :
```text
20:14:03.021 dispatch-node@10.4.2.17 assign order=o-5528120 courier=c-81233 etaS=312 nCouriers=176 routing_ms=39 hungarian_ms=97 gc_ms=52
20:14:03.134 dispatch-node@10.4.2.17 assign order=o-5528120 courier=c-80417 etaS=344 nCouriers=175 routing_ms=41 hungarian_ms=71 gc_ms=0
20:14:03.139 order-flow order=o-5528120 assign → 200 courier=c-80417 en 321 ms (1 appel)

21:42:41.310 dispatch-node@10.4.2.17 assign order=o-5561377 courier=c-77120 etaS=188 nCouriers=58
21:42:55.004 dispatch-node@10.4.2.17 SIGTERM (déploiement 1.9.3)
21:43:10.502 dispatch-node@10.4.3.9  start version=1.9.3
21:43:31.877 dispatch-node@10.4.3.9  assign order=o-5561904 courier=c-77120 etaS=205 nCouriers=64
21:43:40.120 courier-app c-77120 accept order=o-5561377
21:43:52.004 courier-app c-77120 accept order=o-5561904
```


Soirée du samedi 24/10, villes migrées :
```text
heure  appels /assign  p99 /assign  tentatives rejouées  commandes  doubles  événements
18h         9 870          97 ms          0,3 %            8 410        3     —
19h        13 540         176 ms          3,1 %           12 960       61     HPA : 6 → 9 pods à 19:05
20h        14 410         243 ms          4,4 %           13 820      108     —
21h        11 520         151 ms          1,6 %           11 030       21     déploiement 1.9.3 pod par pod, 21:40 → 22:12
22h         6 530          89 ms          0,1 %            6 250       26     (suite du déploiement)
```

- Autres constats : aucune bascule de ville n'a eu lieu le 24/10. Du 19 au 25/10, on compte 1 830 doubles (0,3 % des 610 k commandes des villes migrées), dont 71 % dans des villes migrées depuis plus d'un mois. Les doublons Kafka d'`assignment.created` portant le même coursier touchent 0,05 % des commandes et sont dédupliqués par order-flow. À 20h le 24/10, 229 des 634 tentatives rejouées par Envoy suivaient une réponse 409. Lors de l'exercice de bascule de région du 08/10 à 20:30 (villes de la région 1 vers la région 2), 41 doubles sont apparus dans les 6 minutes suivantes.
- Profil de POST /assign sur un pod (1 vCPU, Node 20), le 24/10 : matrice d'ETA du service de routage p50 38 ms, p99 71 ms ; algorithme hongrois sur matrice complétée au carré, hors GC, 18 ms à 100 coursiers, 52 ms à 150, 94 ms (p50) et 148 ms (p99) à 180 ; pauses GC majeures jusqu'à 52 ms. Pendant ce calcul, le pod ne traite rien d'autre, positions comprises. Au rejeu du 24/10, un glouton « coursier libre le plus proche » réécrit en Node donne 8,5 min en 3 ms au p99, contre 7,9 min pour le hongrois ; aucune variante intermédiaire n'a été mesurée. Prévision : jusqu'à 260 coursiers par zone dense et 1,6 fois plus de commandes le 27/11. Non disponibles : le contenu de l'unique livraison possible d'order-flow avant le gel (non arbitré), le comportement de l'app face à deux offres pour la même commande, et les journaux des pods pendant l'exercice du 08/10 (perdus au redémarrage).

### Contraintes

- équipe réduite — 3 développeurs backend, dont 1 d'astreinte, et pas de SRE dédié ; l'équipe Commandes, qui appelle le dispatch, ne peut livrer qu'une seule modification avant le gel
- résilience à la panne d'une région — chaque ville est rattachée à l'une des 2 régions ; en cas de panne, ses villes basculent vers l'autre en ≤ 10 min, sans double affectation ni commande perdue
- fenêtre de migration courte — 14 villes à migrer du 26/10 au 13/11 (le 11/11 est férié ; gel des changements le 16/11 avant le pic de fin d'année), au plus 2 bascules de ville par jour ouvré entre 15:00 et 17:00, retour arrière d'une ville en moins de 5 min

### Objectifs

- Expliquer les doubles affectations par mécanisme et par condition de déclenchement (latence, redémarrages, changements du nombre de pods, bascules), preuves à l'appui, en séparant faits, hypothèses et inconnues.
- Garantir qu'une commande n'est engagée qu'une fois et qu'un coursier n'a jamais deux engagements non voulus, à travers les rejeux du mesh, les redémarrages de pods, les retours arrière de ville et la panne d'une région.
- Concevoir une affectation à temps borné, avec une garantie ou une mesure de qualité par rapport à l'optimum, tenable à 260 coursiers par zone sur un pod Node.js d'un vCPU.
- Replanifier la migration des 14 villes restantes pour tenir le gel du 16/11 avec 3 développeurs, avec un retour arrière de ville en moins de 5 min.

### Livrables

- Diagnostic écrit : mécanismes, part des doubles attribuable à chacun (calculée à partir des preuves), hypothèses écartées ou restant à trancher et mesures pour le faire.
- Conception de bout en bout de l'engagement des commandes et des coursiers (appelant, mesh, dispatch Node, monolithe, app) : invariants visés, comportement en cas de panne partielle, changements par équipe compatibles avec une seule livraison d'order-flow.
- Algorithme d'affectation à temps borné : au moins trois stratégies comparées en complexité, en qualité mesurée au rejeu et en comportement à l'échéance ; code JavaScript de la stratégie retenue, avec ses tests et son intégration au runtime Node (boucle d'événements, GC).
- Harnais de rejeu en JavaScript de soirées de pointe, avec kills de pods, changements du nombre de pods, latence injectée sur le service de routage, retour arrière de ville et bascule de région.
- Plan de migration daté des 14 villes : ordre, prérequis, critères de passage et d'arrêt, procédure de retour arrière et charge estimée en jours-personne.

### Critères de réussite

- Au rejeu de la soirée du 24/10 à 1,6 fois le volume, avec un kill de pod toutes les 5 min, deux changements du nombre de pods, 100 à 400 ms de latence injectée sur le service de routage, un retour arrière de ville et une bascule de région : 0 commande engagée auprès de deux coursiers et 0 coursier engagé sur deux commandes non groupées volontairement.
- Temps de calcul de l'affectation ≤ 40 ms au p99 et ≤ 60 ms au maximum par appel, pour des zones jusqu'à 260 coursiers et 90 commandes en attente sur 1 vCPU ; p99 de POST /assign ≤ 120 ms sur le rejeu à 1,6 fois le volume, périodes de latence injectée sur le routage comprises.
- Au rejeu de la soirée du 24/10 à volume réel, délai moyen de prise en charge ≤ 8,04 min, soit au moins 80 % du gain de 0,7 min obtenu par l'optimum ; écart à l'optimum publié par taille de zone, jusqu'à 260 coursiers.
- Retour arrière d'une ville du service Node vers le monolithe en moins de 5 min et bascule de région en ≤ 10 min, sans double affectation ni commande perdue, vérifiés en préproduction.
- Les 14 villes sont migrées avant le 16/11, au plus 2 par jour ouvré entre 15:00 et 17:00, pour une charge totale du plan compatible avec la capacité de 3 développeurs dont 1 d'astreinte.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T018 — Soldes négatifs dans un registre de cartes cadeaux Kotlin : invariants sous pauses GC et horloges dérivantes

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | problem solving sous contraintes |
| Type | preuve ou vérification d'invariants |
| Langage | Kotlin |
| Charge | production (10k req/s, 10 TB) |
| Architecture | monolithe modulaire |
| Incident | garbage collector en surcharge |
| Failure mode | horloge dérivante |
| Mode | conception d'un système résilient |

### Contexte

Oréade gère les cartes cadeaux et le porte-monnaie de fidélité de 2 300 enseignes partenaires : 41 M comptes, chacun avec un solde en centimes. En caisse, le terminal demande une autorisation, qui pose une réservation (« hold ») valable 7 min, puis capture le montant final, inférieur ou égal au montant réservé. Des enseignes de restauration capturent volontairement quelques secondes avant l'échéance `expires_at`, renvoyée dans la réponse d'autorisation, pour laisser le temps d'ajouter un pourboire.

En pointe, le registre traite ≈ 10 000 req/s : 3 400 autorisations, 3 100 captures, 2 900 lectures de solde et 600 recharges ou remboursements par seconde. 91 % des holds sont capturés, 3 % annulés et 6 % expirent. Le règlement aux enseignes se fait à J+1 sur la base des captures.

Chronologie :
- 27/08 : la v5.8 vérifie les plafonds de conversion de points à la capture, ce qui charge l'historique de 90 jours du compte ;
- depuis le 01/09 : pauses GC de plus d'une seconde sur tous les nœuds ;
- du 14/09 au 27/09 : le contrôle nocturne trouve 14 comptes à solde négatif, ce que les conditions générales interdisent, et l'audit mensuel 3 comptes dont la somme des écritures diffère du solde.

Trois propositions circulent : passer PostgreSQL en SERIALIZABLE, porter le bail à 10 min, migrer vers ZGC. La direction technique te confie le diagnostic, une conception dont les garanties sont démontrées, et son déploiement.

### Architecture existante

- **Monolithe modulaire** Kotlin 2.0 sur JDK 21 (G1, tas de 12 Go, régions de 4 Mo), Ktor, 10 nœuds derrière un répartiteur sans affinité. Modules `wallet` (comptes, holds, captures), `ledger` (écritures), `loyalty` (règles de points), `history` (lecture sur un réplica). Convention d'équipe : chaque module possède ses tables et ouvre ses propres transactions.
- **PostgreSQL 16** : un primaire et deux réplicas en réplication asynchrone, niveau READ COMMITTED, un pool HikariCP par module. Tables `account(id, balance_cents, held_cents)`, `hold(id, account_id, amount_cents, expires_at)` et `ledger_entry(id bigserial, account_id, kind, amount_cents, ref, created_at)`, partitionnée par mois ; 9,4 To au total.
- **Expiration** : `expires_at` est calculé par le nœud qui autorise (`clock.instant()` + 7 min). Toutes les 10 s, chaque nœud balaie les holds des comptes de sa tranche (`account_id mod 10`, node-10 prenant le reste 0) : il lit les candidats sur un réplica et écrit sur le primaire.
- **Horloges** : chrony sur chaque nœud, deux sources NTP internes, `makestep 0.5 -1`.
- **Audit** : le journal du balayeur est conservé 7 jours ; un hold supprimé ne laisse pas d'autre trace.
- **Latence de capture** : p50 11 ms, p99 38 ms hors pauses GC.

### Problème

Les symptômes mêlent trois facteurs présents en même temps (pauses GC, dérive d'horloge, réseau instable), et chaque équipe propose de traiter « son » facteur. Il faut d'abord énoncer formellement les invariants que le registre doit garantir. Il faut ensuite établir, traces à l'appui, quels entrelacements d'opérations les violent aujourd'hui et sous quelles hypothèses de temps et de pannes, en disant ce qui subsisterait si les pauses GC passaient sous 50 ms et si les horloges étaient parfaitement synchronisées.

Il faut enfin concevoir un registre dont les invariants tiennent sans supposer de borne sur les pauses, la dérive d'horloge ou les délais réseau. Il doit être déployé progressivement à côté de l'ancienne version, avec un retour arrière possible à chaque étape, et les 17 comptes touchés doivent être réconciliés.

### Preuves


Extraits de `wallet` (v5.8) et requêtes SQL associées :
```kotlin
// wallet/CaptureService.kt
fun capture(cmd: CaptureCommand): CaptureResult {
    val result = db.transaction {                         // pool « wallet », READ COMMITTED
        val hold = holds.find(cmd.holdId) ?: return@transaction CaptureResult.UnknownHold
        if (clock.instant() > hold.expiresAt) return@transaction CaptureResult.Expired
        if (cmd.amountCents > hold.amountCents) return@transaction CaptureResult.OverCapture
        val recent = history.recent(hold.accountId, Duration.ofDays(90)) // JSON de 2 à 9 Mo pour 0,4 % des comptes
        loyalty.checkCapture(hold, cmd.amountCents, recent)
        accounts.applyCapture(hold.accountId, capturedCents = cmd.amountCents, releasedCents = hold.amountCents)
        holds.delete(hold.id)
        CaptureResult.Captured(hold.accountId, cmd.amountCents)
    }
    if (result is CaptureResult.Captured) {
        retrying(attempts = 3, on = SQLException::class) {  // pool « ledger »
            ledger.append(Entry.debit(result.accountId, result.amountCents, ref = cmd.holdId))
        }
    }
    return result
}

// wallet/HoldSweeper.kt, planifié toutes les 10 s sur chaque nœud
fun sweep() {
    val now = clock.instant()
    val expired = replicaHolds.findExpired(slice = nodeSlice, before = now, limit = 500)
    for (h in expired) {
        db.transaction {
            accounts.release(h.accountId, h.amountCents)
            holds.delete(h.id)
        }
        audit.info("hold.expired", "hold" to h.id, "account" to h.accountId, "amount" to h.amountCents)
    }
}
```
```sql
-- accounts.reserve (autorisation)
UPDATE account SET held_cents = held_cents + :amount WHERE id = :id AND balance_cents - held_cents >= :amount;
-- accounts.applyCapture
UPDATE account SET balance_cents = balance_cents - :captured, held_cents = held_cents - :released WHERE id = :id;
-- accounts.release
UPDATE account SET held_cents = held_cents - :amount WHERE id = :id;
-- holds.delete
DELETE FROM hold WHERE id = :id;
```


Compte A-88104225, extrait sauvegardé le 18/09 (horodatages de l'horloge locale de chaque nœud, montants en centimes) :
```text
2026-09-17T14:03:11.482Z node-02 wallet  hold.created  hold=h-5f21c9 amount=6000 expires_at=14:10:11.482
2026-09-17T14:10:10.903Z node-02 wallet  capture.start hold=h-5f21c9 amount=5740 check=ok
2026-09-17T14:10:10.958Z node-02 gc      GC(48213) Pause Young (Concurrent Start) (G1 Humongous Allocation) 10854M->9012M(12288M) 1812.412ms
2026-09-17T14:10:12.109Z node-05 sweeper hold.expired  hold=h-5f21c9 account=A-88104225 amount=6000
2026-09-17T14:10:12.826Z node-02 wallet  capture.done  hold=h-5f21c9 result=Captured
2026-09-17T14:10:12.861Z node-02 ledger  append        ref=h-5f21c9 kind=DEBIT amount=5740
2026-09-17T14:21:40.227Z node-08 wallet  hold.created  hold=h-60aa13 amount=7500 expires_at=14:28:40.227
2026-09-17T14:21:52.310Z node-04 wallet  capture.done  hold=h-60aa13 result=Captured
```
État le 17/09 à 23:00 : `balance_cents = -5240`, `held_cents = -6000`, aucun hold actif. Écritures du compte : +8000 RECHARGE (02/09), -5740 DEBIT ref=h-5f21c9, -7500 DEBIT ref=h-60aa13.


Analyse du 28/09 sur les 14 comptes à solde négatif (15 holds en cause). Pour 13 comptes, `held_cents` moins la somme des holds actifs vaut l'opposé du montant d'un hold ; pour le dernier, l'opposé de la somme de deux holds.
```text
groupe  holds  nœuds de capture       délai vérification → écriture  pause GC dans ce délai  observations
G1      10     2,2,4,6,6,8,9,9,9,10   1,21 à 2,07 s                  1,10 à 1,98 s
G2       4     3,3,3,3                0,38 à 1,15 s                  aucune > 150 ms         19/09 entre 08:36 et 09:08 ; historique lu lentement
G3       1     7                      0,09 s                         aucune                  balayeur node-01 ; retard du réplica 2,3 s le 23/09 à 16:02:18

Pauses GC > 1 s sur 14 jours, node-01 à node-10 : 212, 388, 97, 240, 151, 301, 175, 226, 264, 198 (max 2,41 s)
```


Journal système de node-03 et alerte de la supervision ; sur la même période, les autres nœuds restent à moins de 3 ms de leurs sources NTP :
```text
Sep 19 06:12:40 node-03 chronyd[912]: Can't synchronise: no selectable sources
Sep 19 08:55:00 mon-01 prometheus: alerte ClockSkew instance=node-03 : node_time_seconds - time() = -0.586 s
Sep 19 09:10:03 node-03 chronyd[912]: Selected source 10.20.0.11 (ntp-b.internal)
Sep 19 09:10:03 node-03 chronyd[912]: System clock wrong by 0.640912 seconds
Sep 19 09:10:03 node-03 chronyd[912]: System clock was stepped by 0.640912 seconds
```


Module `ledger` et audit mensuel des écritures (montants en centimes) :
```text
2026-09-21T19:22:39.301Z node-06 wallet capture.done hold=h-81d0e2 account=A-33071152 result=Captured amount=2390
2026-09-21T19:22:41.312Z node-06 ledger append ref=h-81d0e2 attempt=1 failed: PSQLException: An I/O error occurred while sending to the backend. (SocketTimeoutException: Read timed out)
2026-09-21T19:22:41.704Z node-06 ledger append ref=h-81d0e2 attempt=2 ok
2026-09-24T11:05:12.880Z node-09 wallet capture.done hold=h-a7730f account=A-55209038 result=Captured amount=4100
2026-09-24T11:05:19.141Z node-09 ledger append ref=h-a7730f attempt=3 failed: PSQLException: The connection attempt failed. -> HTTP 500
2026-09-24T11:05:21.020Z node-04 wallet capture hold=h-a7730f result=UnknownHold -> HTTP 404

compte       solde − Σ écritures  observation
A-33071152   +2390                deux écritures DEBIT de 2390 avec ref=h-81d0e2
A-55209038   -4100                aucune écriture pour h-a7730f
A-10497763   -1215                aucune écriture pour h-c01b95 (même séquence de logs le 26/09)
```

- Essais en préproduction (rejeu du trafic du 17/09 à 10 000 req/s pendant 6 h, pauses de 0 à 3 s injectées dans `history.recent`), en nombre de holds à la fois libérés par le balayeur et capturés : v5.8 de référence 9 ; SERIALIZABLE sur les transactions `wallet` 1, avec 2,8 % d'échecs de sérialisation sur les captures et un p99 de capture passé de 38 à 212 ms ; bail de 10 min 0, les captures étant rejouées aux instants enregistrés ; ZGC générationnel 5, avec des pauses GC ≤ 3 ms, +14 % de CPU et un p99 de capture de 51 ms. Non disponibles : les lignes du balayeur antérieures au 21/09 (rétention de 7 jours, 6 des 14 comptes concernés), l'issue des ventes côté caisse pour les 3 comptes en écart (journaux détenus par les enseignes) et la distribution des instants de capture par rapport à `expires_at`, jamais mesurée.

### Contraintes

- rollback obligatoire — chaque étape, code comme schéma, doit pouvoir être annulée en moins de 15 min sans perte d'écriture ; la version N−1 du monolithe doit redémarrer et rester correcte sur le schéma migré
- réseau partiellement instable — 0,5 % de pertes de paquets entre nœuds applicatifs, primaire et réplicas ; blocages TCP de 1 à 2 s plusieurs fois par heure ; retard de réplication observé jusqu'à 2,3 s ; statement_timeout de 3 s
- déploiement progressif — canari sur 1 nœud sur 10 pendant 48 h, puis 3 nœuds pendant 24 h, puis les 10 ; pendant ces phases, anciennes et nouvelles versions agissent sur les mêmes comptes et les mêmes holds

### Objectifs

- Énoncer formellement les invariants du registre (par compte, par hold et entre solde et écritures) et, pour chaque groupe de holds (G1, G2, G3) et chacun des 3 comptes en écart, exhiber un entrelacement minimal qui en viole un, avec des horodatages corrigés des décalages d'horloge.
- Évaluer les trois propositions en circulation (SERIALIZABLE, bail de 10 min, ZGC) : ce que chacune garantit, ce qu'elle laisse passer, et ce que les essais de préproduction permettent ou non de conclure.
- Concevoir un registre dont les invariants tiennent quelles que soient la durée des pauses, la dérive des horloges et la perte ou le rejeu de messages, en comparant au moins trois conceptions en latence, débit, taux de conflits et complexité de migration.
- Mettre la conception retenue en production par étapes réversibles, en préservant les invariants pendant la cohabitation des versions, et réconcilier les 17 comptes touchés.

### Livrables

- Spécification des invariants (formules sur les tables et sur l'historique des opérations), traces d'entrelacement pour chaque cas observé, et esquisse de preuve que chaque opération de la nouvelle conception (autoriser, capturer, annuler, expirer, recharger, écrire au ledger) préserve chaque invariant sous tout entrelacement, hypothèses listées explicitement.
- Code Kotlin de l'autorisation, de la capture, de l'expiration et de l'écriture au ledger, SQL compris, avec la source de temps retenue pour décider de l'échéance et la justification de ce choix.
- Banc de tests par injection de fautes : pause arbitraire entre deux instructions, sauts d'horloge de ±2 s, perte de la réponse après un commit, retard de réplica ; plus un test de propriété sur un modèle (séquences aléatoires d'opérations concurrentes) qui vérifie les invariants après chaque pas.
- Plan de migration et de retour arrière : étapes de schéma, compatibilité entre les versions N et N−1 à chaque phase du canari, critères chiffrés de passage d'une phase à la suivante, procédure de retour arrière chronométrée.
- Plan de réduction des pauses GC (origine des allocations humongous, options comparées et mesurées) et procédure de réconciliation des 17 comptes, qui distingue ce qui est prouvable de ce qui doit être arbitré par le métier.

### Critères de réussite

- Banc à 10 000 req/s pendant 24 h avec pauses injectées de 0 à 5 s, sauts d'horloge de ±2 s, 0,5 % de pertes et blocages de 2 s : 0 violation d'invariant, vérifiée par une requête de contrôle globale chaque minute et en fin d'essai.
- Au trafic du 17/09, p99 de capture ≤ 60 ms hors pauses GC et au plus 0,05 % de captures refusées pour conflit.
- Chaque étape du plan est annulée en moins de 15 min lors d'un exercice, la version N−1 tournant ensuite 1 h sur le schéma migré, en charge mixte, sans violation d'invariant.
- En production, au plus 1 pause GC de plus de 200 ms par nœud et par jour sur 7 jours, contre 7 à 28 pauses de plus d'une seconde par jour aujourd'hui.
- Les 17 comptes sont réconciliés ou transmis au métier avec, pour chacun, la trace qui justifie le montant, et la requête de contrôle global des invariants spécifiés passe sur les 41 M comptes.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T019 — Bornes de recharge les plus proches : p99 multiplié par 47 pendant la cohabitation de deux index spatiaux Rust

| Axe | Valeur |
|---|---|
| Piste | Problem Solving |
| Domaine | problem solving algorithmique |
| Type | recherche de contre-exemple |
| Langage | Rust |
| Charge | prototype (10 req/s, 10 GB) |
| Architecture | serverless |
| Incident | latence p99 qui explose sans hausse du p50 |
| Failure mode | version mixte pendant migration |
| Mode | conception de tests de charge |

### Contexte

Ohmnibus, start-up de 9 personnes, édite une application qui indique aux conducteurs de véhicules électriques les bornes les plus proches et leur disponibilité en temps réel. Le prototype sert en moyenne 12 req/s, avec des pointes à 60 req/s le soir et lors des départs en vacances. Chaque requête demande les k = 10 bornes les plus proches d'une position, classées en tenant compte de leur disponibilité.

Le jeu de points est passé de 180 000 bornes françaises à 1,1 M points européens depuis l'intégration, en mars 2026, d'un agrégateur de données d'itinérance. Un point correspond à un point de charge (EVSE) ; une station d'autoroute en compte souvent de 12 à 64.

La v2 de l'index, un k-d tree maison construit en masse, remplace la v1, un R-tree de la crate `rstar`. La PR #198 affirmait : « v2 est toujours au moins aussi rapide que v1, la construction par médiane garantit O(log n) ». Depuis le 14/09, un alias pondéré envoie 50 % des invocations à chaque version. Le p50 est resté à 8 ms, mais le p99 est passé de 40 ms à 1,9 s, et le support a reçu 214 signalements de listes qui changent d'un rafraîchissement à l'autre.

Tu reprends le sujet avec l'équipe.

### Architecture existante

- **Fonctions serverless en Rust** (`lambda_runtime`, arm64, 1 024 Mo, concurrence maximale 200). À l'initialisation, la fonction télécharge son index depuis le stockage objet et le désérialise : `stations.kd2` (84 Mo) pour v2, `stations.rtree.bin` (71 Mo) pour v1.
- **Publication** : un job nocturne construit l'index depuis la base PostgreSQL des points (≈ 9 Go avec l'historique des statuts). Depuis la PR #212 (14/09), il ne produit plus que `stations.kd2`.
- **Requête v1** : `nearest_neighbor_iter` de `rstar`, 3k = 30 candidats. **Requête v2** : parcours du k-d tree ; parmi les points des feuilles visitées, tous ceux qui sont à moins de 1,5 fois la distance de la k-ième deviennent candidats.
- **Enrichissement** : pour chaque candidat, lecture du statut temps réel dans un cache Valkey régional alimenté par l'agrégateur, avec au plus 8 lectures en vol par invocation, puis classement : bornes disponibles d'abord, dans un rayon de 1,5 fois la distance de la k-ième.
- **Alias** : pondération 50/50 par invocation, sans affinité par utilisateur. Le tableau de bord de la plateforme n'affiche que des métriques par alias ; chaque invocation écrit une ligne de log structurée (version, démarrage à froid, candidats, durées).

### Problème

Il faut réfuter ou établir l'affirmation de la PR #198 sur des bases formelles : construire une famille d'entrées (points et requêtes) sur laquelle v2 est asymptotiquement plus lente que v1, relier cette famille aux données de production, puis séparer la part du p99 qui vient de l'index de celle qui vient de l'enrichissement, des démarrages à froid et de la cohabitation des versions.

Il faut ensuite corriger l'algorithme avec des garanties de pire cas qui tiennent à 2,5 M points. Il faut aussi concevoir des tests de charge capables de détecter ce type de régression avant tout futur changement de pondération, et rendre la migration réversible alors que le format publié a déjà changé.

### Preuves


Latences par version, reconstituées à partir des logs structurés (toutes invocations du 21 au 27/09) :
```text
version  invocations  démarrages à froid      p50   p99     p99,9   candidats par requête (p50 / max)
v1       3 640 000    0,42 % (init ≈ 0,9 s)   8 ms  41 ms   0,93 s  30 / 30
v2       3 660 000    0,61 % (init ≈ 1,4 s)   7 ms  2,2 s   2,7 s   22 / 4 829
alias    7 300 000    0,52 %                  8 ms  1,9 s   2,5 s   -

Du 01 au 13/09 (v1 seule) : p50 8 ms, p99 40 ms, démarrages à froid 0,31 %.
```


Échantillon de logs (coordonnées WGS84 de la requête) :
```text
{"ts":"2026-09-24T18:41:07.114Z","ver":2,"cold":false,"lat":45.4642,"lon":9.1900,"cands":4829,"status_reads":4829,"index_us":212,"status_ms":1851,"dur_ms":1874}
{"ts":"2026-09-24T18:41:07.380Z","ver":1,"cold":false,"lat":45.4640,"lon":9.1903,"cands":30,"status_reads":30,"index_us":38,"status_ms":6,"dur_ms":8}
{"ts":"2026-09-24T18:43:55.902Z","ver":2,"cold":true,"init_ms":1412,"lat":50.8467,"lon":4.3525,"cands":22,"status_reads":22,"index_us":9,"status_ms":5,"dur_ms":1426}
{"ts":"2026-09-26T19:12:31.447Z","ver":2,"cold":false,"lat":48.1372,"lon":11.5756,"cands":2433,"status_reads":2433,"index_us":131,"status_ms":1204,"dur_ms":1219}
{"ts":"2026-09-27T18:05:12.019Z","ver":2,"cold":false,"lat":45.4639,"lon":9.1897,"cands":4826,"status_reads":4826,"index_us":219,"status_ms":2493,"dur_ms":2512}
```


Construction de v2 et chemins de requête des deux versions :
```rust
// kd2/src/build.rs (v2.0.3)
const LEAF_CAP: usize = 32;

pub fn build(pts: &mut [Station], depth: u32, nodes: &mut Vec<Node>) -> u32 {
    if pts.len() <= LEAF_CAP {
        return push_leaf(nodes, pts);
    }
    let axis = (depth % 2) as usize; // 0 = x, 1 = y (ETRS89-LAEA, en mètres)
    let mid = pts.len() / 2;
    pts.select_nth_unstable_by(mid, |a, b| a.pos[axis].total_cmp(&b.pos[axis]));
    let pivot = pts[mid].pos[axis];
    let split = itertools::partition(pts.iter_mut(), |s| s.pos[axis] < pivot);
    if split == 0 || split == pts.len() {
        return push_leaf(nodes, pts); // évite une récursion sans fin
    }
    let (lo, hi) = pts.split_at_mut(split);
    let left = build(lo, depth + 1, nodes);
    let right = build(hi, depth + 1, nodes);
    push_inner(nodes, axis as u8, pivot, left, right)
}

// handler v2
let mut cands = Vec::with_capacity(64);
let dk = index.knn_leaves(q, K, &mut cands); // points des feuilles visitées, avec leur distance
cands.retain(|c| c.dist <= 1.5 * dk);
let statuses: Vec<Status> = stream::iter(cands.iter().map(|c| status.get(c.id)))
    .buffered(8)
    .try_collect()
    .await?;

// handler v1
let cands: Vec<&Station> = rtree.nearest_neighbor_iter(&q).take(3 * K).collect();
```


Mesures jointes à la PR #198 et statistiques du fichier publié :
```text
criterion, index seul, k = 10, 1,1 M points tirés uniformément dans l'emprise Europe, 100 000 requêtes uniformes
  v1 rstar : 11,8 µs/requête    v2 kd2 : 3,9 µs/requête    construction v2 : 2,1 s

stations.kd2 du 27/09 : 1 100 212 points, 64 988 feuilles, profondeur max 21
  taille des feuilles : p50 17, p99 29, max 4 812 ; 212 feuilles de plus de 32 points (58 311 points au total)
```

- Provenance des points (table `station_source`) : registre national français 214 000, opérateurs raccordés en direct 96 000, agrégateur d'itinérance 790 212. Pour l'agrégateur, la précision de géocodage déclarée est « adresse » pour 91 % des points, « commune » pour 6 % et « inconnue » pour 3 % ; elle n'est pas renseignée pour les autres sources. L'agrégateur n'a donné aucune date pour une amélioration du géocodage.
- Cohabitation : v1 lit le dernier `stations.rtree.bin` publié, celui du 13/09 (1 062 212 points), car la PR #212 a retiré le constructeur R-tree du job. Sur 10 000 requêtes rejouées le 25/09 sur les deux versions, 31 % des listes diffèrent : 12 % des requêtes par au moins un point absent de v1, 19 % uniquement par l'ordre de bornes équidistantes. La plateforme ne publie aucune métrique de démarrage à froid par version : les chiffres ci-dessus viennent des logs de la fonction. La répartition spatiale des requêtes du partenaire, dont la flotte est concentrée dans les aéroports et les gares, n'est pas connue.

### Contraintes

- rollback obligatoire — retour à 100 % sur v1 en moins de 10 min à tout moment de la migration, avec des données de moins de 24 h ; aujourd'hui, v1 sert un fichier figé au 13/09 auquel manquent 38 000 points
- équipe réduite — 2 développeurs, dont un à mi-temps, sans astreinte ; 3 semaines de travail avant l'ouverture de l'API à un partenaire, un loueur de véhicules
- forte croissance des données — 1,1 M points aujourd'hui contre 180 000 il y a un an ; ≈ 2,5 M attendus dans 12 mois, soit 3 000 à 5 000 points de plus par jour

### Objectifs

- Établir formellement si l'affirmation de la PR #198 est vraie : exhiber une famille paramétrée d'entrées où v2 est asymptotiquement plus lente que v1, pour l'index seul et de bout en bout, donner sa complexité et montrer que les données de production la réalisent.
- Décomposer le p99 observé entre index, enrichissement, démarrages à froid et cohabitation des versions, en distinguant faits mesurés, hypothèses et inconnues.
- Corriger l'index avec des garanties de pire cas démontrées (profondeur, taille des feuilles, nombre de statuts lus par requête) valables jusqu'à 2,5 M points, sans dégrader le p50.
- Concevoir les tests de charge et un plan de migration réversible qui permettent de reprendre le déploiement de v2 en 3 semaines avec 2 développeurs.

### Livrables

- Contre-exemple formel : famille d'entrées, coût de v1 et de v2 en fonction de ses paramètres, preuve que le rapport des coûts n'est pas borné, et instance minimale reproductible (fichier de points et requête) tirée ou dérivée de la production.
- Algorithme corrigé (construction et requête), énoncé et preuve de ses bornes, et analyse du temps de construction, de la taille du fichier et du temps d'initialisation à 1,1 M et à 2,5 M points, ainsi que tout amendement de la règle de classement qu'imposeraient ces bornes, avec son effet mesuré sur les listes renvoyées.
- Code Rust : construction, requête des k plus proches voisins avec un ordre total déterministe entre bornes équidistantes, tests de propriété (proptest) contre une recherche exhaustive sur des jeux aléatoires et sur la famille de contre-exemples, benchmarks criterion de l'index seul et de bout en bout.
- Plan de tests de charge : modèle de charge (répartition spatiale observée, scénario partenaire, rafales), maîtrise et mesure du taux de démarrages à froid, mesure par version, générateur en boucle ouverte qui évite l'omission coordonnée, seuils go/no-go chiffrés.
- Plan de migration et de rollback à double format : publication, lecture, bascule d'alias par paliers, cohérence des réponses pendant la cohabitation, durée de retour arrière mesurée, et répartition du travail entre les 2 développeurs sur 3 semaines.

### Critères de réussite

- 0 divergence entre la v2 corrigée et la recherche exhaustive sur 10⁶ requêtes (jeux aléatoires, famille de contre-exemples, jeu de production), ordre des égalités compris.
- Sur le jeu de production et sur une projection à 2,5 M points, le nombre de statuts lus par requête est borné par une constante justifiée, indépendante de n et de la densité locale, et l'index seul répond en moins de 50 µs au p99,9.
- Test de charge en boucle ouverte à 60 req/s pendant 2 h avec la répartition spatiale de production : pour chaque version, p50 ≤ 8 ms et p99 ≤ 50 ms sur les invocations chaudes ; à 2,5 M points, initialisation ≤ 1,4 s et démarrages à froid ≤ 0,5 %.
- Exercice de rollback : 100 % du trafic sur v1 en moins de 10 min avec un fichier v1 de moins de 24 h, puis retour à 50/50, sans aucune erreur 5xx.
- Pendant la cohabitation, au plus 1 % des requêtes rejouées sur les deux versions donnent des listes différentes, ordre compris, contre 31 % aujourd'hui.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```


---

## B002-T020 — Quasi-doublons d'images en flux : rappel perdu, évaluation contaminée et index C++ bloqué à 48 Go par nœud

| Axe | Valeur |
|---|---|
| Piste | Machine Learning |
| Domaine | computer vision |
| Type | clustering |
| Langage | C++ |
| Charge | extreme-scale (1M+ req/s, 1 PB+) |
| Architecture | stream processing |
| Incident | contamination du jeu d'évaluation |
| Failure mode | labels en retard ou partiellement manquants |
| Mode | optimisation de performance |

### Contexte

Brocalia, marketplace généraliste de 310 M annonces actives, détecte en flux les quasi-doublons d'images : ≈ 1,1 M événements image/s en pointe (uploads, vignettes, ré-encodages, flux catalogue des vendeurs professionnels) pour ≈ 4,2 Po d'images stockées. Chaque image reçoit une empreinte pHash DCT de 64 bits ; deux images sont des quasi-doublons si leurs empreintes sont à une distance de Hamming ≤ 6. Les quasi-doublons sont regroupés en clusters, qui servent à signaler les annonces dupliquées et à construire les splits train/éval du classifieur de catégories : un cluster entier va dans le même split.

Chronologie :
- 29/06 (v3.8) : la recherche ne sonde plus que 4 des 8 bandes de 8 bits ; le débit par cœur est multiplié par 2,3 et la mémoire par entrée baisse de 40 %, ce qui a permis de passer la fenêtre de 4 à 7 jours sans ajouter de RAM ;
- 08/07 : mise en production du modèle v12 (nouveau backbone distillé) ;
- T3 : exactitude du classifieur sur l'éval de 94,1 %, contre 90,7 % au T2, gain attribué à v12.

Un audit manuel de 2 000 items sans quasi-doublon en train donne pourtant 86,9 % ± 1,5, et les modérateurs corrigent toujours 8,1 % des catégories (8,3 % au T2). Tu dois expliquer l'écart, rendre l'évaluation fiable et remettre l'index en état sans dépasser le budget mémoire ni dégrader le SLA.

### Architecture existante

- **Opérateur `dedup`** (C++17, framework de flux interne) sur 28 nœuds de 64 Go, dont 48 Go réservés à l'index. Les événements sont partitionnés par catégorie de niveau 2 déclarée par le vendeur (≈ 3 400 catégories) ; chaque nœud tient un index par catégorie, sur une fenêtre glissante de 7 jours.
- **Index d'une catégorie** : un tableau de lignes (pHash de 8 octets et référence d'item de 8 octets) et une table par bande sondée. La table de la bande b associe chacune des 256 valeurs de l'octet b à un tableau contigu d'entrées de 8 octets (indice de ligne sur 32 bits et 32 bits de préfiltre). Surcoût mesuré de l'allocateur : ×1,12.
- **Flux** : toutes les empreintes (1,1 M/s en pointe) sont recherchées, seules les nouvelles (≈ 60 k/s en pointe) sont insérées. Chaque paire trouvée à distance ≤ 6 fusionne deux clusters (union-find persistant) ; le split d'un item est fixé à son insertion d'après l'identifiant de son cluster.
- **Étiquettes** : la catégorie validée (modération, retours d'acheteurs, flux pros) arrive de façon asynchrone. L'éval d'une semaine est figée à T+24 h et exclut les items sans catégorie validée à cette date ; le train est reconstruit chaque semaine avec toutes les étiquettes disponibles pour les items de plus de 14 jours.

### Problème

Depuis juin, plusieurs changements se superposent : la recherche de l'index, la durée de la fenêtre, le modèle, et des étiquettes qui arrivent tard ou jamais, alors que les splits sont dérivés des clusters. Il faut quantifier la contribution de chaque facteur à l'écart entre 94,1 % et 86,9 %, en séparant mesures, estimations et inconnues, puis produire une estimation de l'exactitude qui mérite confiance.

Côté système, il faut une recherche qui retrouve toutes les paires à distance ≤ 6 dans la fenêtre, tient 1,1 M recherches/s dans le SLA et reste sous 48 Go par nœud malgré la croissance de la fenêtre, sans toucher au format de l'empreinte. Revenir aux 8 bandes demanderait ≈ 75 Go par nœud.

### Preuves


Rappel mesuré sur 120 000 paires de quasi-doublons étiquetées à la main (signalements d'acheteurs et audit aléatoire), par distance de Hamming entre empreintes :
```text
distance  paires   v3.7 (8 bandes)  v3.8 (bandes 4, 5, 6, 7)
0 à 3     41 000   1,000            1,000
4         19 600   1,000            0,930
5         25 300   1,000            0,620
6         30 500   1,000            0,340
7 et +     3 600   0,000            0,000
total    120 000   0,970            0,711
```
Les bandes 4 à 7 ont été retenues en v3.8 pour la répartition de leurs buckets : entropie moyenne de 7,6 bits par octet, contre 5,9 bits pour les bandes 0 à 3.


Banc de v3.7 contre v3.8 sur le nœud le plus chargé (rejeu d'une heure de pointe) :
```text
                                      v3.7 (8 bandes, fenêtre 4 j)  v3.8 (4 bandes, fenêtre 7 j)
recherches/s par cœur                 3 900                         9 000
entrées parcourues par recherche      386 000 (médiane)             191 000 (médiane)
octets par entrée, surcoût compris    89,6                          53,8
uploads traités en < 2 s              99,91 %                       99,97 %
```
Buckets : 1 % des buckets contiennent 18 % des entrées ; le plus gros (bande 5, valeur 0x00) compte 4,1 M entrées, surtout des empreintes d'images génériques (fonds unis, « photo non disponible »). Taille des clusters : p50 1, p99 14, max 2,3 M items, de même origine.


Chemin de recherche et d'insertion (v3.8) :
```cpp
// dedup/band_index.cc
constexpr std::array<int, 4> kProbedBands = {4, 5, 6, 7};
constexpr int kRadius = 6;

struct Entry { uint32_t row; uint32_t pre; };

void BandIndex::Query(uint64_t h, std::vector<uint32_t>* out) const {
  for (int b : kProbedBands) {
    const uint8_t key = static_cast<uint8_t>(h >> (8 * b));
    const uint32_t pre = Prefilter(h, b);              // 32 bits de h pris hors de la bande b
    for (const Entry& e : tables_[b].bucket(key)) {
      if (__builtin_popcount(e.pre ^ pre) > kRadius) continue;
      if (__builtin_popcountll(rows_[e.row].phash ^ h) <= kRadius) out->push_back(e.row);
    }
  }
}

// dedup/operator.cc
void DedupOperator::OnFingerprint(const ImageEvent& ev, uint64_t h) {
  std::vector<uint32_t> hits;
  index_.Query(h, &hits);
  if (!ev.is_new) { EmitLinks(ev, hits); return; }
  const uint32_t row = index_.Insert(h, ev.item_ref);
  for (uint32_t r : hits) clusters_.Union(row, r);
  splits_.AssignOnce(ev.item_ref, SplitOf(clusters_.Find(row)));   // hash(cluster) % 100 < 10 : éval
}
```


Balayage exhaustif hors ligne de 20 000 items tirés de l'éval T3, comparés à tout le train (distance ≤ 6) :
```text
items d'éval ayant au moins un quasi-doublon en train : 23,4 %  (même mesure sur l'éval T2 : 14,1 %)
exactitude de v12 sur ces items : 99,2 %
quasi-doublon le plus récent en train, pour les items contaminés du T3 :
  uploadé moins de 7 jours avant l'item : 58 %    plus de 7 jours avant : 42 %
v12 évalué sur l'éval T2 : 91,6 % (v11 : 90,7 %)
```


Délai entre upload et catégorie validée (items de juillet et août) : ≤ 24 h pour 52 %, de 24 à 72 h pour 17 %, plus de 72 h pour 25 %, aucune catégorie au bout de 30 jours pour 6 % (annonces retirées, souvent pour fraude). Audit expert de 2 000 items de la semaine 37 sans quasi-doublon en train, stratifié selon ce délai, les strates lentes étant suréchantillonnées :
```text
délai                   items audités  bien classés par v12
≤ 24 h                  700            636
24 à 72 h               600            511
plus de 72 h ou jamais  700            568
estimation repondérée selon les parts ci-dessus : 86,9 % (IC à 95 % : ± 1,5)
```
Non disponibles : le taux d'accord entre étiquettes expertes et catégories validées en production n'a jamais été mesuré ; les catégories des annonces retirées ne seront jamais validées.


### Contraintes

- SLA élevé — 99,95 % des uploads traités de bout en bout (empreinte, recherche, rattachement au cluster) en moins de 2 s, mesuré heure par heure ; 99,97 % aujourd'hui, 99,91 % aux heures de pointe avec l'ancienne configuration
- legacy non remplaçable à court terme — empreinte pHash DCT de 64 bits, ordre des bits compris, consommée par 14 systèmes et inchangeable avant 2027 ; framework de flux interne en C++17 (opérateurs à état, checkpoints incrémentaux toutes les 10 min) imposé
- faible consommation mémoire — 48 Go de RAM réservés à l'index par nœud, dont 44,8 Go utilisés sur le nœud le plus chargé ; fenêtre en croissance de 3 % par mois ; aucune extension matérielle avant le T2 2027

### Objectifs

- Quantifier, avec intervalles de confiance, la part de l'écart entre 94,1 % et 86,9 % due à la contamination de l'éval, au délai d'étiquetage et aux autres facteurs, en séparant mesures, estimations et inconnues, et dire ce qu'il reste du gain attribué à v12.
- Modéliser le rappel de la recherche en fonction de la distance, du nombre de bandes, de leur taille et des bandes sondées, confronter le modèle aux mesures et expliquer les écarts.
- Concevoir et implémenter une recherche qui trouve toutes les paires à distance ≤ 6 dans la fenêtre, à au moins 9 000 recherches/s par cœur, sous 48 Go par nœud pendant au moins 6 mois de croissance, sans changer l'empreinte.
- Reconstruire des splits sans fuite et un protocole d'évaluation robuste aux étiquettes tardives ou absentes.

### Livrables

- Note d'analyse : décomposition chiffrée de l'écart d'exactitude (IC et hypothèses), réestimation de v11 et de v12 sur une base comparable, liste des mesures manquantes avec leur coût d'obtention.
- Modèle probabiliste de collision de la recherche par bandes (distance, nombre et taille des bandes, bandes sondées), écart aux mesures par distance et conséquences pour le choix des bandes.
- Conception de la nouvelle recherche : structures, preuve d'exhaustivité au rayon 6, modèle mémoire par entrée et par nœud (aujourd'hui et à 6 mois), coût d'une recherche (accès mémoire, entrées comparées), traitement des empreintes dégénérées et des buckets géants, compatibilité avec les checkpoints du framework.
- Code C++17 de l'index (insertion, recherche, expiration de la fenêtre) avec tests d'exhaustivité contre un balayage brut sur des jeux aléatoires et adverses, test de non-régression sur les 120 000 paires, benchmarks de débit, de latence et de mémoire sur le rejeu d'une heure de pointe.
- Procédure de décontamination et de migration : reconstruction des splits du train et de l'éval existants, règle de gel de l'éval compatible avec les étiquettes tardives ou absentes, bascule de l'opérateur sans rupture du SLA ni perte de l'état des clusters.

### Critères de réussite

- Rappel de 1,000 sur les 116 400 paires étiquetées à distance ≤ 6, 0 paire manquée par rapport à un balayage brut sur 10⁸ recherches (jeux aléatoires et adverses), et aucune paire à distance > 6 rattachée.
- Au rejeu d'une heure de pointe à 1,1 M événements/s : au moins 9 000 recherches/s par cœur et 99,95 % des uploads traités en moins de 2 s.
- Mémoire de l'index, surcoût de l'allocateur compris, ≤ 44,8 Go sur le nœud le plus chargé au volume actuel et ≤ 48 Go au volume projeté à 6 mois (+3 % par mois).
- Sur un nouvel échantillon d'éval de 20 000 items, au plus 0,5 % d'items ayant un quasi-doublon à distance ≤ 6 en train, vérifié par balayage exhaustif.
- L'exactitude annoncée par le nouveau protocole tombe dans l'IC à 95 % d'un nouvel audit expert de 2 000 items, et, pour une même cohorte, sa valeur calculée à T+24 h s'écarte de moins d'un point de celle calculée à T+30 j.

### Métadonnées

```json
{
  "difficulty": "extreme",
  "requires_code": true,
  "requires_architecture": true,
  "requires_tradeoffs": true,
  "requires_multistep_reasoning": true,
  "solution_included": false
}
```

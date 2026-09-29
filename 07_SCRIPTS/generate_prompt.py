#!/usr/bin/env python3
"""Génère des fiches de variation à partir des catalogues de 02_TAXONOMY.

Aucun appel réseau. Garanties :
- répartition exacte Problem Solving / Machine Learning (--ps-ratio, 0.6 par défaut) ;
- chaque axe est tiré parmi les valeurs les moins utilisées du lot (couverture maximale) ;
- règles de cohérence de 02_TAXONOMY/compatibility.json ;
- chaque fiche diffère d'au moins --min-diff axes de toutes les fiches précédentes.

Sorties : generated_prompts.md (à copier dans Claude) et generated_cards.jsonl (machine).
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from taxonomy import BASE, DIMENSIONS, TRACK_LABEL, Taxonomy, dimension_diff, utf8_stdout

MAX_ATTEMPTS = 2000
CONSTRAINTS_PER_TASK = 3


def least_used(rng, pool, usage):
    low = min(usage[x] for x in pool)
    return rng.choice([x for x in pool if usage[x] == low])


def draw_card(rng, tax, track, usage):
    domain = least_used(rng, tax.domains[track], usage["domain"])

    languages = [l for l in tax.languages if tax.language_ok(l, domain)]
    pref = tax.language_preference.get(track)
    if pref and pref["language"] in languages and rng.random() < pref["probability"]:
        language = pref["language"]
    else:
        language = least_used(rng, languages, usage["language"])

    incidents = [i for i in tax.incidents if tax.incident_ok(i, track, language)]
    pool = list(tax.constraints)
    constraints = []
    for _ in range(CONSTRAINTS_PER_TASK):
        c = least_used(rng, pool, usage["constraints"])
        constraints.append(c)
        pool.remove(c)

    return {
        "track": track,
        "domain": domain,
        "subtype": least_used(rng, tax.subtypes[track], usage["subtype"]),
        "language": language,
        "load_level": least_used(rng, list(tax.loads), usage["load_level"]),
        "architecture_style": least_used(rng, tax.architectures, usage["architecture_style"]),
        "incident_type": least_used(rng, incidents, usage["incident_type"]),
        "failure_mode": least_used(rng, tax.failures, usage["failure_mode"]),
        "task_mode": least_used(rng, tax.modes, usage["task_mode"]),
        "constraints": constraints,
    }


def render_card(card, tax):
    load = tax.loads[card["load_level"]]
    return [
        f"## {card['task_id']} — {TRACK_LABEL[card['track']]}",
        "",
        f"**Domaine:** {card['domain']}",
        f"**Type:** {card['subtype']}",
        f"**Langage:** {card['language']}",
        f"**Charge:** {card['load_level']} — {load['throughput']}, {load['data']}",
        f"**Architecture:** {card['architecture_style']}",
        f"**Incident:** {card['incident_type']}",
        f"**Failure mode:** {card['failure_mode']}",
        f"**Mode:** {card['task_mode']}",
        f"**Contraintes:** {', '.join(card['constraints'])}",
        "",
        "Génère maintenant un problème technique complet de niveau Distinguished Engineer,",
        "au format de 03_TEMPLATES/task_schema.json : contexte, architecture existante, problème,",
        "preuves, contraintes chiffrées, objectifs, livrables, critères de réussite et métadonnées.",
        "Laisse des inconnues identifiables. Ne donne pas la solution ni la cause racine.",
        "",
    ]


def main():
    utf8_stdout()
    p = argparse.ArgumentParser(description="Génère localement des fiches de variation.")
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--seed", type=int, default=20260928)
    p.add_argument("--ps-ratio", type=float, default=0.6, help="part de Problem Solving (0-1)")
    p.add_argument("--min-diff", type=int, default=4, help="axes différents minimum entre deux fiches")
    p.add_argument("--id-prefix", default="T", help="préfixe des task_id (ex. B001-T)")
    p.add_argument("--out-dir", default=str(BASE / "05_OUTPUTS"))
    args = p.parse_args()

    rng = random.Random(args.seed)
    tax = Taxonomy()
    errors = tax.self_check()
    if errors:
        sys.exit("\n".join(errors))

    n_ps = round(args.count * args.ps_ratio)
    tracks = ["problem_solving"] * n_ps + ["machine_learning"] * (args.count - n_ps)
    rng.shuffle(tracks)

    usage = {k: Counter() for k in ("subtype", *DIMENSIONS)}
    cards = []
    for i, track in enumerate(tracks, 1):
        for _ in range(MAX_ATTEMPTS):
            card = draw_card(rng, tax, track, usage)
            if all(dimension_diff(card, prev) >= args.min_diff for prev in cards):
                break
        else:
            sys.exit(f"Aucune fiche assez différente pour la tâche {i} : baisse --min-diff.")
        card = {"task_id": f"{args.id_prefix}{i:03d}", **card}
        for key in usage:
            usage[key].update(card[key] if key == "constraints" else [card[key]])
        cards.append(card)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    blocks = [
        "# Generated prompt pack",
        "",
        f"Seed: {args.seed}",
        f"Count: {args.count} ({n_ps} Problem Solving / {args.count - n_ps} Machine Learning)",
        "",
        "Copier chaque fiche dans Claude Desktop sous le MASTER SUPERPROMPT.",
        "",
    ]
    for card in cards:
        blocks += render_card(card, tax)

    md_path = out / "generated_prompts.md"
    md_path.write_text("\n".join(blocks), encoding="utf-8")
    jsonl_path = out / "generated_cards.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for card in cards:
            f.write(json.dumps(card, ensure_ascii=False) + "\n")
    print(f"Created: {md_path}")
    print(f"Created: {jsonl_path}")


if __name__ == "__main__":
    main()

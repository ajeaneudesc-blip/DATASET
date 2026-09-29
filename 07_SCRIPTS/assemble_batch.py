#!/usr/bin/env python3
"""Assemble les tâches d'un lot (un .json par tâche) en un .jsonl et un .md lisible.

  python 07_SCRIPTS/assemble_batch.py 05_OUTPUTS/batch_002
  python 07_SCRIPTS/assemble_batch.py --check 05_OUTPUTS/batch_002

Lit <lot>/tasks/*.json et écrit <lot>/tasks.jsonl et <lot>/tasks.md.
Le lot est d'abord validé (y compris contre les autres lots du dossier parent) ;
en cas d'erreur rien n'est écrit, sauf avec --force.
--check n'écrit rien et échoue si tasks.jsonl / tasks.md ne sont pas à jour.
"""
import argparse
import json
import sys
from pathlib import Path

from taxonomy import TRACK_LABEL, Taxonomy, dataset_items, load_items, utf8_stdout
from validate_tasks import validate

SECTIONS = (
    ("context", "Contexte"),
    ("existing_architecture", "Architecture existante"),
    ("problem", "Problème"),
    ("evidence", "Preuves"),
    ("constraints", "Contraintes"),
    ("objectives", "Objectifs"),
    ("deliverables", "Livrables"),
    ("success_criteria", "Critères de réussite"),
)


def render_value(value):
    if isinstance(value, list):
        # Une preuve peut contenir un bloc de code : on la sépare au lieu d'en faire une puce.
        parts = []
        for v in value:
            parts.append(f"\n{v}\n" if "\n" in v else f"- {v}")
        return "\n".join(parts)
    return value


def render_task(task, tax):
    load = tax.loads.get(task["load_level"], {})
    axes = [
        ("Piste", TRACK_LABEL.get(task["track"], task["track"])),
        ("Domaine", task["domain"]),
        ("Type", task["subtype"]),
        ("Langage", task["language"]),
        ("Charge", f"{task['load_level']} ({load.get('throughput', '?')}, {load.get('data', '?')})"),
        ("Architecture", task["architecture_style"]),
        ("Incident", task["incident_type"]),
        ("Failure mode", task["failure_mode"]),
        ("Mode", task["task_mode"]),
    ]
    lines = [f"## {task['task_id']} — {task['title']}", "", "| Axe | Valeur |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in axes]
    for key, title in SECTIONS:
        lines += ["", f"### {title}", "", render_value(task[key])]
    lines += ["", "### Métadonnées", "", "```json", json.dumps(task["metadata"], ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines)


def render_batch(name, tasks, tax):
    jsonl = "".join(json.dumps(task, ensure_ascii=False) + "\n" for task in tasks)
    n_ps = sum(t["track"] == "problem_solving" for t in tasks)
    header = [
        f"# {name}",
        "",
        f"{len(tasks)} tâches — {n_ps} Problem Solving / {len(tasks) - n_ps} Machine Learning.",
        "Énoncés uniquement : aucune solution n'est incluse.",
        "",
        "## Sommaire",
        "",
    ]
    header += [f"- {t['task_id']} — {t['title']} ({TRACK_LABEL[t['track']]})" for t in tasks]
    body = "\n\n---\n\n".join(render_task(t, tax) for t in tasks)
    return {"tasks.jsonl": jsonl, "tasks.md": "\n".join(header) + "\n\n---\n\n" + body}


def main():
    utf8_stdout()
    p = argparse.ArgumentParser(description="Assemble un lot de tâches.")
    p.add_argument("batch_dir")
    p.add_argument("--force", action="store_true", help="assemble même si la validation échoue")
    p.add_argument("--check", action="store_true", help="vérifie que les fichiers assemblés sont à jour")
    args = p.parse_args()

    batch = Path(args.batch_dir)
    items = load_items(batch / "tasks") if (batch / "tasks").is_dir() else []
    if not items:
        sys.exit(f"Aucune tâche dans {batch / 'tasks'}")
    tasks = [item for _, item in items]

    rep = validate(items, "task", dataset_items(batch.resolve().parent, exclude=batch))
    for line in rep.errors + rep.warnings:
        print(line)
    if rep.errors and not args.force:
        sys.exit(f"{len(rep.errors)} erreur(s) de validation : rien n'est écrit (--force pour passer outre).")

    outputs = render_batch(batch.name, tasks, Taxonomy())
    if args.check:
        stale = [name for name, text in outputs.items()
                 if not (batch / name).is_file() or (batch / name).read_text(encoding="utf-8") != text]
        if stale:
            sys.exit(f"Pas à jour : {', '.join(stale)} — relancer assemble_batch.py {batch}")
        print(f"À jour : {batch / 'tasks.jsonl'}, {batch / 'tasks.md'}")
        return
    for name, text in outputs.items():
        with open(batch / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"Created: {batch / name}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Assemble les tâches d'un lot (un .json par tâche) en un .jsonl et un .md lisible.

  python 07_SCRIPTS/assemble_batch.py 05_OUTPUTS/batch_001

Lit <lot>/tasks/*.json et écrit <lot>/tasks.jsonl et <lot>/tasks.md.
"""
import argparse
import json
import sys
from pathlib import Path

from taxonomy import TRACK_LABEL, Taxonomy, utf8_stdout

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


def main():
    utf8_stdout()
    p = argparse.ArgumentParser(description="Assemble un lot de tâches.")
    p.add_argument("batch_dir")
    args = p.parse_args()

    batch = Path(args.batch_dir)
    files = sorted((batch / "tasks").glob("*.json"))
    if not files:
        sys.exit(f"Aucune tâche dans {batch / 'tasks'}")
    tasks = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    tax = Taxonomy()

    with open(batch / "tasks.jsonl", "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task, ensure_ascii=False) + "\n")

    n_ps = sum(t["track"] == "problem_solving" for t in tasks)
    header = [
        f"# {batch.name}",
        "",
        f"{len(tasks)} tâches — {n_ps} Problem Solving / {len(tasks) - n_ps} Machine Learning.",
        "Énoncés uniquement : aucune solution n'est incluse.",
        "",
        "## Sommaire",
        "",
    ]
    header += [f"- {t['task_id']} — {t['title']} ({TRACK_LABEL[t['track']]})" for t in tasks]
    body = "\n\n---\n\n".join(render_task(t, tax) for t in tasks)
    (batch / "tasks.md").write_text("\n".join(header) + "\n\n---\n\n" + body, encoding="utf-8")
    print(f"Created: {batch / 'tasks.jsonl'}")
    print(f"Created: {batch / 'tasks.md'}")


if __name__ == "__main__":
    main()

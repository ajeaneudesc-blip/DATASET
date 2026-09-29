"""Construit 05_OUTPUTS/batch_002/tasks/*.json à partir des fiches générées et des sources YAML.

  python3 build.py                 # toutes les sources B002-T*.yaml
  python3 build.py B002-T007 ...   # seulement ces tâches

Les axes (piste, domaine, type, langage, charge, architecture, incident, failure mode, mode)
sont repris tels quels de generated_cards.jsonl ; la source YAML fournit le texte et le
détail chiffré de chaque contrainte (clé = label de la fiche).
"""
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
BATCH = Path("/home/user/DATASET/05_OUTPUTS/batch_002")
AXES = ("track", "title", "domain", "subtype", "language", "load_level", "architecture_style",
        "incident_type", "failure_mode", "task_mode")
BODY = ("context", "existing_architecture", "problem", "evidence", "objectives", "deliverables",
        "success_criteria")

cards = {c["task_id"]: c for c in map(json.loads, (BATCH / "generated_cards.jsonl").read_text(encoding="utf-8").splitlines())}
out_dir = BATCH / "tasks"
out_dir.mkdir(exist_ok=True)
errors = []
wanted = set(sys.argv[1:])
for src in sorted(HERE.glob("B002-T*.yaml")):
    task_id = src.stem
    if wanted and task_id not in wanted:
        continue
    card = cards[task_id]
    doc = yaml.safe_load(src.read_text(encoding="utf-8"))
    details = doc["constraints"]
    if list(details) != card["constraints"]:
        errors.append(f"{task_id}: contraintes {list(details)} ≠ fiche {card['constraints']}")
        continue
    task = {"task_id": task_id}
    for key in AXES:
        task[key] = doc["title"] if key == "title" else card[key]
    task["constraints"] = [f"{label} — {detail}" for label, detail in details.items()]
    for key in BODY:
        value = doc[key]
        task[key] = [v.strip() for v in value] if isinstance(value, list) else value.strip()
    task["metadata"] = {
        "difficulty": "extreme",
        "requires_code": bool(doc["metadata"]["requires_code"]),
        "requires_architecture": bool(doc["metadata"]["requires_architecture"]),
        "requires_tradeoffs": True,
        "requires_multistep_reasoning": True,
        "solution_included": False,
    }
    (out_dir / f"{task_id}.json").write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ok", task_id)
if errors:
    sys.exit("\n".join(errors))

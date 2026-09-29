#!/usr/bin/env python3
"""Valide des seeds, des fiches ou des tâches complètes contre les catalogues du projet.

Exemples :
  python 07_SCRIPTS/validate_tasks.py --kind seed 04_SEEDS/seed_tasks.jsonl
  python 07_SCRIPTS/validate_tasks.py --kind card 05_OUTPUTS/generated_cards.jsonl
  python 07_SCRIPTS/validate_tasks.py --kind task 05_OUTPUTS/batch_001/tasks
  python 07_SCRIPTS/validate_tasks.py --kind task --single 05_OUTPUTS/batch_001/tasks/B001-T001.json

Entrée : fichier .jsonl, fichier .json (objet ou liste) ou dossier de .json.
Code retour 1 s'il y a au moins une erreur.
"""
import argparse
import json
import re
import sys
import unicodedata
from itertools import combinations
from pathlib import Path

from taxonomy import (
    CONSTRAINT_SEP,
    DIMENSIONS,
    TRACKS,
    Taxonomy,
    constraint_label,
    dimension_diff,
    utf8_stdout,
)

AXIS_FIELDS = ("task_id", "track", "domain", "subtype", *DIMENSIONS[1:])
SEED_FIELDS = (*AXIS_FIELDS, "theme", "difficulty", "prompt_instruction")
CARD_FIELDS = AXIS_FIELDS
TASK_TEXT_MIN = {"title": 15, "context": 400, "existing_architecture": 200, "problem": 150}
TASK_LIST_MIN = {"evidence": 3, "objectives": 2, "deliverables": 3, "success_criteria": 3}
TASK_FIELDS = (*AXIS_FIELDS, *TASK_TEXT_MIN, *TASK_LIST_MIN, "metadata")
METADATA_BOOLS = (
    "requires_code",
    "requires_architecture",
    "requires_tradeoffs",
    "requires_multistep_reasoning",
    "solution_included",
)
MIN_CONSTRAINTS = 3

# Heuristiques de fuite : signalées en avertissement, à confirmer à la relecture.
LEAK_PATTERNS = [
    (r"cha[iî]ne de pens[ée]e|chain[- ]of[- ]thought|raisonnement interne", "demande de chaîne de pensée"),
    (r"la cause racine (est|était)|root cause (is|was)", "cause racine possiblement révélée"),
    (r"la (bonne )?solution (est|consiste)|the (fix|solution) is", "solution possiblement donnée"),
]


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, where, msg):
        self.errors.append(f"ERROR [{where}] {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"WARN  [{where}] {msg}")


def load_items(path):
    path = Path(path)
    if path.is_dir():
        files = sorted(path.glob("*.json"))
        return [(f.name, json.loads(f.read_text(encoding="utf-8"))) for f in files]
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [(f"{path.name}:{n}", json.loads(line)) for n, line in enumerate(text.splitlines(), 1) if line.strip()]
    data = json.loads(text)
    items = data if isinstance(data, list) else [data]
    return [(f"{path.name}[{n}]", item) for n, item in enumerate(items)]


def normalize(text):
    text = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip()


def all_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(all_text(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(all_text(v) for v in value.values())
    return ""


def check_axes(item, where, tax, rep):
    track = item.get("track")
    if track not in TRACKS:
        rep.error(where, f"track invalide : {track!r}")
        return
    domain = item.get("domain")
    real_track = tax.track_of(domain)
    if real_track is None:
        rep.error(where, f"domaine hors taxonomie : {domain!r}")
    elif real_track != track:
        rep.error(where, f"domaine « {domain} » appartient à {real_track}, pas à {track}")
    if item.get("subtype") not in tax.subtypes[track]:
        rep.error(where, f"subtype hors taxonomie {track} : {item.get('subtype')!r}")

    catalogs = {
        "language": tax.languages,
        "load_level": list(tax.loads),
        "architecture_style": tax.architectures,
        "incident_type": tax.incidents,
        "failure_mode": tax.failures,
        "task_mode": tax.modes,
    }
    for field, allowed in catalogs.items():
        if item.get(field) not in allowed:
            rep.error(where, f"{field} hors taxonomie : {item.get(field)!r}")

    if real_track and not tax.language_ok(item.get("language"), domain):
        rep.error(where, f"langage « {item.get('language')} » incohérent avec le domaine « {domain} »")
    if not tax.incident_ok(item.get("incident_type"), track, item.get("language")):
        rep.error(where, f"incident « {item.get('incident_type')} » incohérent avec {track} / {item.get('language')}")

    constraints = item.get("constraints")
    if not isinstance(constraints, list) or not all(isinstance(c, str) and c.strip() for c in constraints):
        rep.error(where, "constraints doit être une liste de chaînes non vides")
        return
    labels = [constraint_label(c) for c in constraints]
    for c, label in zip(constraints, labels):
        if label not in tax.constraints:
            rep.error(where, f"contrainte hors taxonomie (attendu « label{CONSTRAINT_SEP}détail ») : {c[:80]!r}")
    if len(set(labels)) < MIN_CONSTRAINTS:
        rep.error(where, f"au moins {MIN_CONSTRAINTS} contraintes distinctes attendues, trouvé {len(set(labels))}")


def check_task_body(item, where, rep):
    for field, minimum in TASK_TEXT_MIN.items():
        value = item.get(field)
        if not isinstance(value, str) or len(value.strip()) < minimum:
            rep.error(where, f"{field} absent ou trop court (< {minimum} caractères)")
    for field, minimum in TASK_LIST_MIN.items():
        value = item.get(field)
        if not isinstance(value, list) or len([v for v in value if isinstance(v, str) and v.strip()]) < minimum:
            rep.error(where, f"{field} doit contenir au moins {minimum} éléments texte non vides")

    meta = item.get("metadata")
    if not isinstance(meta, dict):
        rep.error(where, "metadata absent")
    else:
        if meta.get("difficulty") != "extreme":
            rep.error(where, f"metadata.difficulty doit valoir 'extreme', trouvé {meta.get('difficulty')!r}")
        for key in METADATA_BOOLS:
            if not isinstance(meta.get(key), bool):
                rep.error(where, f"metadata.{key} doit être un booléen")
        if meta.get("solution_included") is not False:
            rep.error(where, "metadata.solution_included doit valoir false")

    text = all_text({k: v for k, v in item.items() if k != "metadata"})
    for pattern, label in LEAK_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            rep.warn(where, f"{label} : « …{text[max(0, match.start() - 40):match.end() + 40]}… »")


def check_item(item, where, kind, tax, rep):
    if not isinstance(item, dict):
        rep.error(where, "l'entrée doit être un objet JSON")
        return
    expected = {"seed": SEED_FIELDS, "card": CARD_FIELDS, "task": TASK_FIELDS}[kind]
    missing = [f for f in expected if f not in item]
    if missing:
        rep.error(where, f"champs manquants : {', '.join(missing)}")
    unknown = [f for f in item if f not in expected]
    if unknown:
        rep.warn(where, f"champs non prévus par le schéma : {', '.join(unknown)}")
    check_axes(item, where, tax, rep)
    if kind == "seed":
        for field in ("theme", "prompt_instruction"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                rep.error(where, f"{field} vide")
        if item.get("difficulty") != "extreme":
            rep.error(where, "difficulty doit valoir 'extreme'")
    if kind == "task":
        check_task_body(item, where, rep)


def check_batch(items, kind, args, rep):
    ids = [item.get("task_id") for _, item in items]
    for task_id in {i for i in ids if ids.count(i) > 1}:
        rep.error("lot", f"task_id dupliqué : {task_id}")

    n = len(items)
    n_ps = sum(item.get("track") == "problem_solving" for _, item in items)
    if n:
        ratio = n_ps / n
        if abs(ratio - args.ps_ratio) > args.ratio_tolerance:
            rep.error("lot", f"répartition PS/ML {n_ps}/{n - n_ps} ({ratio:.0%} PS), cible {args.ps_ratio:.0%} ± {args.ratio_tolerance:.0%}")

    for (wa, a), (wb, b) in combinations(items, 2):
        diff = dimension_diff(a, b)
        if diff < args.min_diff:
            rep.error("lot", f"{a.get('task_id')} et {b.get('task_id')} ne diffèrent que sur {diff} axe(s) (min {args.min_diff})")

    text_key = {"seed": "theme", "task": "title"}.get(kind)
    if text_key:
        seen = {}
        for _, item in items:
            key = normalize(str(item.get(text_key, "")))
            if key and key in seen:
                rep.error("lot", f"{text_key} dupliqué : {item.get('task_id')} et {seen[key]}")
            seen.setdefault(key, item.get("task_id"))


def main():
    utf8_stdout()
    p = argparse.ArgumentParser(description="Valide seeds, fiches ou tâches.")
    p.add_argument("path")
    p.add_argument("--kind", choices=("seed", "card", "task"), required=True)
    p.add_argument("--single", action="store_true", help="ignore les contrôles de lot (ratio, diversité, doublons)")
    p.add_argument("--ps-ratio", type=float, default=0.6)
    p.add_argument("--ratio-tolerance", type=float, default=0.05)
    p.add_argument("--min-diff", type=int, default=4)
    args = p.parse_args()

    tax = Taxonomy()
    rep = Report()
    for msg in tax.self_check():
        rep.error("taxonomie", msg)

    try:
        items = load_items(args.path)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"Lecture impossible de {args.path} : {exc}")

    for where, item in items:
        label = item.get("task_id", where) if isinstance(item, dict) else where
        check_item(item, label, args.kind, tax, rep)
    if not args.single:
        check_batch([(w, i) for w, i in items if isinstance(i, dict)], args.kind, args, rep)

    for line in rep.errors + rep.warnings:
        print(line)
    n_ps = sum(isinstance(i, dict) and i.get("track") == "problem_solving" for _, i in items)
    print(
        f"\n{len(items)} élément(s) — {n_ps} Problem Solving / {len(items) - n_ps} Machine Learning — "
        f"{len(rep.errors)} erreur(s), {len(rep.warnings)} avertissement(s)"
    )
    sys.exit(1 if rep.errors else 0)


if __name__ == "__main__":
    main()

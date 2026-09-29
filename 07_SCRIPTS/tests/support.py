"""Aides partagées par les tests : chemins, tâches valides de test, lancement des scripts."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
BASE = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# Cinq combinaisons valides qui diffèrent deux à deux sur tous les axes (3 PS / 2 ML = 60 %).
AXES = [
    ("problem_solving", "optimisation combinatoire", "optimisation sous contraintes", "Python", "prototype",
     "monolithe modulaire", "régression après déploiement", "panne d'un nœud", "diagnostic d'incident",
     ["zero downtime", "rollback obligatoire", "budget mensuel plafonné"]),
    ("problem_solving", "raisonnement probabiliste", "raisonnement probabiliste", "Go", "small-production",
     "microservices", "latence p99 qui explose sans hausse du p50", "panne d'une zone", "architecture greenfield",
     ["compatibilité API stricte", "legacy non remplaçable à court terme", "p99 très faible"]),
    ("problem_solving", "planification et recherche", "planification multi-objectifs", "Rust", "production",
     "event-driven", "duplication sporadique d'opérations", "panne d'une région", "migration progressive",
     ["SLA élevé", "multi-région", "multi-tenant"]),
    ("machine_learning", "NLP et LLM", "fine-tuning", "Java", "high-scale",
     "serverless", "perte ou retard d'événements", "partition réseau", "refactorisation legacy",
     ["fenêtre de migration courte", "équipe réduite", "auditabilité complète"]),
    ("machine_learning", "recommender systems", "ranking", "TypeScript", "extreme-scale",
     "actor model", "deadlocks rares", "latence d'un fournisseur externe", "code review",
     ["faible consommation mémoire", "réseau partiellement instable", "déploiement progressif"]),
]
KEYS = ("track", "domain", "subtype", "language", "load_level", "architecture_style",
        "incident_type", "failure_mode", "task_mode", "constraints")


def words(tag, n):
    return " ".join(f"{tag}mot{i}" for i in range(n))


def make_task(index=0, task_id=None, **overrides):
    """Tâche complète et valide, avec un texte propre à son identifiant."""
    task_id = task_id or f"X-T{index + 1:03d}"
    tag = task_id.lower().replace("-", "")
    task = {"task_id": task_id, **dict(zip(KEYS, AXES[index]))}
    task["constraints"] = [f"{c} — détail chiffré {i}" for i, c in enumerate(task["constraints"])]
    task.update({
        "title": f"Titre de test numéro {task_id}",
        "context": words(tag + "ctx", 60),
        "existing_architecture": words(tag + "arch", 30),
        "problem": words(tag + "pb", 25),
        "evidence": [f"preuve {i} {tag}" for i in range(3)],
        "objectives": [f"objectif {i} {tag}" for i in range(2)],
        "deliverables": [f"livrable {i} {tag}" for i in range(3)],
        "success_criteria": [f"critère {i} {tag}" for i in range(3)],
        "metadata": {
            "difficulty": "extreme",
            "requires_code": True,
            "requires_architecture": True,
            "requires_tradeoffs": True,
            "requires_multistep_reasoning": True,
            "solution_included": False,
        },
    })
    task.update(overrides)
    return task


def write_batch(batch_dir, tasks):
    tasks_dir = Path(batch_dir) / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        (tasks_dir / f"{task['task_id']}.json").write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
    return tasks_dir


def run_script(name, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

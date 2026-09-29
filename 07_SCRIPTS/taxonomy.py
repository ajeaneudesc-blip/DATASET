"""Outils partagés : catalogues, piste (track), règles de cohérence, lecture des lots."""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TAX = BASE / "02_TAXONOMY"
CONFIG = BASE / "00_CONFIG" / "project.json"
OUTPUTS = BASE / "05_OUTPUTS"

TRACKS = ("problem_solving", "machine_learning")
TRACK_LABEL = {"problem_solving": "Problem Solving", "machine_learning": "Machine Learning"}

# Les 8 axes de variation du MASTER SUPERPROMPT.
DIMENSIONS = (
    "domain",
    "language",
    "load_level",
    "architecture_style",
    "incident_type",
    "failure_mode",
    "task_mode",
    "constraints",
)

# Une contrainte de tâche s'écrit « label » ou « label — détail chiffré ».
CONSTRAINT_SEP = " — "


def utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def load(name):
    with open(TAX / name, encoding="utf-8") as f:
        return json.load(f)


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def load_items(path):
    """Lit un fichier .jsonl, un fichier .json (objet ou liste) ou un dossier de .json."""
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


def dataset_items(root, exclude=None):
    """Tâches finalisées de tous les lots <root>/batch_*/tasks/, sauf le lot contenant `exclude`."""
    excluded = Path(exclude).resolve() if exclude else None
    items = []
    for batch in sorted(Path(root).glob("batch_*")):
        resolved = batch.resolve()
        if excluded and (resolved == excluded or resolved in excluded.parents):
            continue
        if (batch / "tasks").is_dir():
            items += [(f"{batch.name}/{where}", item) for where, item in load_items(batch / "tasks")]
    return items


class Taxonomy:
    def __init__(self):
        domains = load("domains.json")
        self.domains = {t: list(domains[t]) for t in TRACKS}
        self.subtypes = {
            "problem_solving": load("problem_solving_types.json"),
            "machine_learning": load("ml_types.json"),
        }
        self.languages = load("languages.json")
        self.loads = {l["name"]: l for l in load("load_levels.json")}
        self.constraints = load("constraints.json")
        self.incidents = load("incidents.json")
        self.architectures = load("architecture_styles.json")
        self.failures = load("failure_modes.json")
        self.modes = load("task_modes.json")

        compat = load("compatibility.json")
        self.incident_tracks = compat.get("incident_allowed_tracks", {})
        self.incident_excluded_languages = compat.get("incident_excluded_languages", {})
        self.language_domains = compat.get("language_allowed_domains", {})
        self.domain_languages = compat.get("domain_allowed_languages", {})
        self.language_preference = compat.get("track_language_preference", {})

    def track_of(self, domain):
        for track in TRACKS:
            if domain in self.domains[track]:
                return track
        return None

    def language_ok(self, language, domain):
        by_language = self.language_domains.get(language)
        by_domain = self.domain_languages.get(domain)
        return (by_language is None or domain in by_language) and (
            by_domain is None or language in by_domain
        )

    def incident_ok(self, incident, track, language=None):
        allowed = self.incident_tracks.get(incident)
        excluded = self.incident_excluded_languages.get(incident, [])
        return (allowed is None or track in allowed) and language not in excluded

    def self_check(self):
        """Vérifie que compatibility.json ne référence que des valeurs existantes."""
        errors = []
        all_domains = self.domains["problem_solving"] + self.domains["machine_learning"]
        for incident, tracks in self.incident_tracks.items():
            if incident not in self.incidents:
                errors.append(f"compatibility.json: incident inconnu « {incident} »")
            errors += [f"compatibility.json: piste inconnue « {t} »" for t in tracks if t not in TRACKS]
        for incident, languages in self.incident_excluded_languages.items():
            if incident not in self.incidents:
                errors.append(f"compatibility.json: incident inconnu « {incident} »")
            errors += [f"compatibility.json: langage inconnu « {l} »" for l in languages if l not in self.languages]
        for language, domains in self.language_domains.items():
            if language not in self.languages:
                errors.append(f"compatibility.json: langage inconnu « {language} »")
            errors += [f"compatibility.json: domaine inconnu « {d} »" for d in domains if d not in all_domains]
        for domain, languages in self.domain_languages.items():
            if domain not in all_domains:
                errors.append(f"compatibility.json: domaine inconnu « {domain} »")
            errors += [f"compatibility.json: langage inconnu « {l} »" for l in languages if l not in self.languages]
        for track, pref in self.language_preference.items():
            if track not in TRACKS or pref.get("language") not in self.languages:
                errors.append(f"compatibility.json: préférence de langage invalide pour « {track} »")
        axes = load_config().get("variation_axes", [])
        if sorted(axes) != sorted(DIMENSIONS):
            errors.append(f"project.json: variation_axes {axes} ≠ axes des scripts {list(DIMENSIONS)}")
        return errors


def constraint_label(constraint):
    return constraint.split(CONSTRAINT_SEP, 1)[0].strip()


def signature(item):
    """Valeurs des 8 axes ; les contraintes sont comparées comme un ensemble de labels."""
    values = []
    for dim in DIMENSIONS:
        if dim == "constraints":
            values.append(frozenset(constraint_label(c) for c in item.get("constraints", [])))
        else:
            values.append(item.get(dim))
    return tuple(values)


def dimension_diff(a, b):
    return sum(x != y for x, y in zip(signature(a), signature(b)))

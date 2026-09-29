import tempfile
import unittest

from support import BASE, make_task, run_script, write_batch

from validate_tasks import validate


def check(tasks, previous=(), **options):
    return validate([(t["task_id"], t) for t in tasks], "task", [(t["task_id"], t) for t in previous], **options)


class TacheTest(unittest.TestCase):
    def test_tache_valide(self):
        rep = check([make_task(0)], single=True)
        self.assertEqual((rep.errors, rep.warnings), ([], []))

    def test_domaine_hors_piste(self):
        rep = check([make_task(0, track="machine_learning")], single=True)
        self.assertTrue(any("appartient à problem_solving" in e for e in rep.errors), rep.errors)

    def test_solution_incluse(self):
        task = make_task(0)
        task["metadata"]["solution_included"] = True
        self.assertTrue(check([task], single=True).errors)

    def test_contrainte_hors_taxonomie(self):
        rep = check([make_task(0, constraints=["zero downtime", "SLA élevé", "très rapide — 1 ms"])], single=True)
        self.assertTrue(any("contrainte hors taxonomie" in e for e in rep.errors), rep.errors)

    def test_langage_incoherent(self):
        rep = check([make_task(3, domain="deep learning", language="Bash")], single=True)
        self.assertTrue(any("incohérent avec le domaine" in e for e in rep.errors), rep.errors)

    def test_failure_mode_reserve_au_ml(self):
        rep = check([make_task(0, failure_mode="checkpoint corrompu ou incomplet")], single=True)
        self.assertTrue(any("réservé à une autre piste" in e for e in rep.errors), rep.errors)
        rep = check([make_task(3, failure_mode="checkpoint corrompu ou incomplet")], single=True)
        self.assertEqual(rep.errors, [])

    def test_fuite_de_solution_signalee(self):
        task = make_task(0, problem=make_task(0)["problem"] + " La cause racine est le cache.")
        rep = check([task], single=True)
        self.assertEqual(rep.errors, [])
        self.assertTrue(any("cause racine" in w for w in rep.warnings), rep.warnings)

    def test_texte_trop_court(self):
        rep = check([make_task(0, context="trop court")], single=True)
        self.assertTrue(any("context absent ou trop court" in e for e in rep.errors), rep.errors)


class LotTest(unittest.TestCase):
    def setUp(self):
        self.batch = [make_task(i) for i in range(5)]

    def test_lot_valide(self):
        rep = check(self.batch)
        self.assertEqual((rep.errors, rep.warnings), ([], []))

    def test_repartition(self):
        rep = check(self.batch[:4])
        self.assertTrue(any("répartition PS/ML 3/1" in e for e in rep.errors), rep.errors)

    def test_combinaisons_trop_proches(self):
        self.batch[1] = make_task(0, task_id="X-T002", title="Un autre titre suffisamment long")
        rep = check(self.batch)
        self.assertTrue(any("ne diffèrent que sur 0 axe" in e for e in rep.errors), rep.errors)

    def test_titre_duplique(self):
        self.batch[1]["title"] = "  TITRE de test numéro X-T001 !"
        rep = check(self.batch)
        self.assertTrue(any("title dupliqué" in e for e in rep.errors), rep.errors)

    def test_reformulation_signalee(self):
        for key in ("context", "existing_architecture", "problem"):
            self.batch[1][key] = self.batch[0][key]
        rep = check(self.batch)
        self.assertEqual(rep.errors, [])
        self.assertTrue(any("textes très proches" in w for w in rep.warnings), rep.warnings)

    def test_comparaison_aux_autres_lots(self):
        previous = [make_task(0, task_id="X-T001"), make_task(1, task_id="OLD-T001")]
        rep = check(self.batch, previous)
        self.assertTrue(any("task_id X-T001 déjà utilisé" in e for e in rep.errors), rep.errors)
        self.assertTrue(any("X-T002 et OLD-T001 ne diffèrent que sur 0 axe" in e for e in rep.errors), rep.errors)


class CliTest(unittest.TestCase):
    def test_seeds_du_projet(self):
        result = run_script("validate_tasks.py", "--kind", "seed", BASE / "04_SEEDS" / "seed_tasks.jsonl")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 erreur(s), 0 avertissement(s)", result.stdout)

    def test_against_exclut_le_lot_valide(self):
        with tempfile.TemporaryDirectory() as root:
            write_batch(f"{root}/batch_001", [make_task(i, f"B001-T{i:03d}") for i in range(5)])
            current = write_batch(f"{root}/batch_002", [make_task(i, f"B002-T{i:03d}") for i in range(5)])
            result = run_script("validate_tasks.py", "--kind", "task", current, "--against", root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("comparé à 5 tâche(s)", result.stdout)
            self.assertIn("B002-T000 et B001-T000 ne diffèrent que sur 0 axe", result.stdout)


if __name__ == "__main__":
    unittest.main()

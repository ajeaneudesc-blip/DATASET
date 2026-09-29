import json
import tempfile
import unittest
from pathlib import Path

from support import make_task, run_script, write_batch


class AssembleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.batch = Path(self.tmp.name) / "batch_009"
        self.tasks = [make_task(i, f"B009-T{i + 1:03d}") for i in range(5)]
        write_batch(self.batch, self.tasks)

    def tearDown(self):
        self.tmp.cleanup()

    def test_assemble_puis_check(self):
        result = run_script("assemble_batch.py", self.batch)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = (self.batch / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(l)["task_id"] for l in lines], [t["task_id"] for t in self.tasks])
        md = (self.batch / "tasks.md").read_text(encoding="utf-8")
        self.assertIn("5 tâches — 3 Problem Solving / 2 Machine Learning.", md)
        self.assertIn("## B009-T005 — ", md)

        self.assertEqual(run_script("assemble_batch.py", "--check", self.batch).returncode, 0)
        write_batch(self.batch, [dict(self.tasks[0], title="Titre modifié après assemblage")])
        result = run_script("assemble_batch.py", "--check", self.batch)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Pas à jour", result.stderr)

    def test_refuse_un_lot_invalide(self):
        write_batch(self.batch, [dict(self.tasks[0], domain="domaine inventé")])
        result = run_script("assemble_batch.py", self.batch)
        self.assertEqual(result.returncode, 1)
        self.assertIn("domaine hors taxonomie", result.stdout)
        self.assertFalse((self.batch / "tasks.jsonl").exists())

        result = run_script("assemble_batch.py", "--force", self.batch)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.batch / "tasks.jsonl").exists())

    def test_compare_aux_lots_voisins(self):
        write_batch(Path(self.tmp.name) / "batch_001", [make_task(0, "B001-T001")])
        result = run_script("assemble_batch.py", self.batch)
        self.assertEqual(result.returncode, 1)
        self.assertIn("B009-T001 et B001-T001 ne diffèrent que sur 0 axe", result.stdout)


if __name__ == "__main__":
    unittest.main()

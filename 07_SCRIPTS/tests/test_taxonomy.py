import tempfile
import unittest

from support import make_task, write_batch

from taxonomy import Taxonomy, constraint_label, dataset_items, dimension_diff


class TaxonomyTest(unittest.TestCase):
    def setUp(self):
        self.tax = Taxonomy()

    def test_catalogues_coherents(self):
        self.assertEqual(self.tax.self_check(), [])

    def test_label_de_contrainte(self):
        self.assertEqual(constraint_label("zero downtime — 0 s d'indisponibilité"), "zero downtime")
        self.assertEqual(constraint_label("SLA élevé"), "SLA élevé")

    def test_ecart_ignore_detail_et_ordre_des_contraintes(self):
        a = make_task(0)
        b = dict(a, constraints=list(reversed([constraint_label(c) for c in a["constraints"]])))
        self.assertEqual(dimension_diff(a, b), 0)
        self.assertEqual(dimension_diff(make_task(0), make_task(1)), 8)

    def test_langage_et_domaine(self):
        self.assertTrue(self.tax.language_ok("Python", "deep learning"))
        self.assertFalse(self.tax.language_ok("Bash", "deep learning"))
        self.assertFalse(self.tax.language_ok("SQL", "computer vision"))

    def test_incident_et_piste(self):
        self.assertFalse(self.tax.incident_ok("dérive de modèle ML", "problem_solving"))
        self.assertTrue(self.tax.incident_ok("dérive de modèle ML", "machine_learning"))
        self.assertFalse(self.tax.incident_ok("garbage collector en surcharge", "problem_solving", "Rust"))
        self.assertFalse(self.tax.incident_ok("écart training/serving", "problem_solving"))
        self.assertFalse(self.tax.incident_ok("divergence ou instabilité d'entraînement", "machine_learning", "SQL"))

    def test_failure_mode_et_piste(self):
        self.assertTrue(self.tax.failure_ok("partition réseau", "problem_solving"))
        self.assertFalse(self.tax.failure_ok("checkpoint corrompu ou incomplet", "problem_solving"))
        self.assertTrue(self.tax.failure_ok("checkpoint corrompu ou incomplet", "machine_learning"))

    def test_lots_du_dataset_sans_le_lot_courant(self):
        with tempfile.TemporaryDirectory() as root:
            write_batch(f"{root}/batch_001", [make_task(0, "B001-T001")])
            current = write_batch(f"{root}/batch_002", [make_task(1, "B002-T001")])
            ids = [item["task_id"] for _, item in dataset_items(root, exclude=current)]
            self.assertEqual(ids, ["B001-T001"])
            self.assertEqual(len(dataset_items(root)), 2)


if __name__ == "__main__":
    unittest.main()

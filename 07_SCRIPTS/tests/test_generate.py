import json
import tempfile
import unittest
from itertools import combinations
from pathlib import Path

from support import run_script, write_batch

from taxonomy import dimension_diff
from validate_tasks import validate


def generate(out_dir, *args):
    result = run_script("generate_prompt.py", "--out-dir", out_dir, *args)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    lines = (Path(out_dir) / "generated_cards.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


class GenerateTest(unittest.TestCase):
    def test_lot_par_defaut(self):
        with tempfile.TemporaryDirectory() as out:
            cards = generate(out, "--count", 20)
            self.assertEqual(sum(c["track"] == "problem_solving" for c in cards), 12)
            rep = validate([(c["task_id"], c) for c in cards], "card")
            self.assertEqual((rep.errors, rep.warnings), ([], []))
            self.assertTrue((Path(out) / "generated_prompts.md").is_file())

    def test_reproductible(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.assertEqual(generate(a, "--seed", 7), generate(b, "--seed", 7))
            self.assertNotEqual(generate(a, "--seed", 7), generate(b, "--seed", 8))

    def test_grand_lot(self):
        with tempfile.TemporaryDirectory() as out:
            cards = generate(out, "--count", 60)
            self.assertTrue(all(dimension_diff(a, b) >= 4 for a, b in combinations(cards, 2)))

    def test_against_lots_existants(self):
        with tempfile.TemporaryDirectory() as root:
            first = generate(f"{root}/draft", "--count", 20, "--id-prefix", "B001-T")
            write_batch(f"{root}/batch_001", first)
            second = generate(f"{root}/batch_002", "--count", 20, "--id-prefix", "B002-T", "--against", root)
            self.assertTrue(all(dimension_diff(a, b) >= 4 for a in second for b in first))
            # Les domaines ML peu couverts par le premier lot sont servis en priorité.
            ml_domains = {c["domain"] for c in first + second if c["track"] == "machine_learning"}
            self.assertEqual(len(ml_domains), 15)


if __name__ == "__main__":
    unittest.main()

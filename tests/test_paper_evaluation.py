"""Original scorer behavior, including its duplicate oracle entries."""
import runpy
import unittest
from pathlib import Path
from scripts.evaluate_paper import score, external_name


class PaperScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer = runpy.run_path(str(Path(__file__).resolve().parents[1] /
            'validation/paper_2026_10_22/reference/compare_macro_benchmark_cg.py'))

    def test_external_and_extra_caller_edges_are_not_filtered(self):
        result=score({'app.go':['vendor.send'], 'other':['vendor.extra']},
                     {'app.go':['vendor.send', 'vendor.missing']}, self.scorer)
        self.assertEqual(result['precision'], .5)
        self.assertEqual(result['recall'], .5)
        self.assertEqual(result['fp'], 1)
        self.assertEqual(result['fn'], 1)

    def test_duplicate_truth_entries_preserve_original_denominator(self):
        result=score({'app.go':['vendor.send']},
                     {'app.go':['vendor.send','vendor.send','vendor.missing']}, self.scorer)
        self.assertEqual(result['precision'], 1)
        self.assertEqual(result['recall'], 2/3)
        self.assertEqual(result['ground_truth_items_including_duplicates'], 3)
        self.assertEqual(result['truth_pairs'], 2)

    def test_symbolic_names_do_not_use_suffix_matching(self):
        result=score({'app.go':['pkg.Class.send']}, {'app.go':['other.Class.send']}, self.scorer)
        self.assertEqual(result['tp'], 0)
        self.assertEqual(result['f1'], 0)
        self.assertEqual(external_name('builtins.len'), '<builtin>.len')
        self.assertEqual(external_name('str.strip'), '<**PyStr**>.strip')

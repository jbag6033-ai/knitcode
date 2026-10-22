"""A count improvement must not hide newly introduced false/missing pairs."""
import json
from pathlib import Path
import tempfile
import unittest
from scripts.compare_paper_runs import compare_runs


class ComparisonGuardTests(unittest.TestCase):
    def compare(self, old, new):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for label, values in [('before',old),('after',new)]:
                p=root/label/'sample';p.mkdir(parents=True)
                data=dict(source_sha256={'app.py':'hash'},ground_truth_sha256='truth',contract='same',full_calls=values)
                (p/'results.json').write_text(json.dumps(data))
            return compare_runs(root/'before',root/'after')

    def metric(self, tp, fp, fn):
        return dict(tp=len(tp),fp=len(fp),fn=len(fn),precision=.5,recall=.5,f1=.5,
                    true_positive=tp,false_positive=fp,false_negative=fn)

    def test_equal_counts_cannot_hide_replaced_false_positive(self):
        old=self.metric([['a','b']],[['a','old']],[])
        new=self.metric([['a','b']],[['a','new']],[])
        result=self.compare(old,new)
        self.assertFalse(result['passed'])
        self.assertEqual(result['records'][0]['added_false_positives'],[('a','new')])

    def test_more_hits_cannot_hide_loss_of_existing_true_positive(self):
        old=self.metric([['a','old']],[],[['a','new1'],['a','new2']])
        new=self.metric([['a','new1'],['a','new2']],[],[['a','old']])
        result=self.compare(old,new)
        self.assertFalse(result['passed'])
        self.assertEqual(result['records'][0]['lost_true_positives'],[('a','old')])

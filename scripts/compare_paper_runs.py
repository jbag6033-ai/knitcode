"""Fail if a full-oracle benchmark comparison adds FPs or loses existing TPs."""
import argparse
import json
from pathlib import Path


def compare_runs(before, after):
    records=[]
    projects=sorted(p.parent.name for p in before.glob('*/results.json'))
    if not projects:
        raise ValueError('No baseline projects')
    for name in projects:
        old=json.loads((before/name/'results.json').read_text())
        new=json.loads((after/name/'results.json').read_text())
        identity=all(old[k]==new[k] for k in ('source_sha256','ground_truth_sha256','contract'))
        a,b=old['full_calls'],new['full_calls']
        pairs=lambda data,key: set(map(tuple,data[key]))
        added_fp=sorted(pairs(b,'false_positive')-pairs(a,'false_positive'))
        lost_tp=sorted(pairs(a,'true_positive')-pairs(b,'true_positive'))
        records.append(dict(project=name, identical_inputs_and_contract=identity,
            before={k:a[k] for k in ('tp','fp','fn','precision','recall','f1')},
            after={k:b[k] for k in ('tp','fp','fn','precision','recall','f1')},
            added_false_positives=added_fp, lost_true_positives=lost_tp,
            gained_true_positives=sorted(pairs(b,'true_positive')-pairs(a,'true_positive')),
            removed_false_positives=sorted(pairs(a,'false_positive')-pairs(b,'false_positive')),
            passed=identity and b['fp']<=a['fp'] and b['fn']<=a['fn'] and not added_fp and not lost_tp))
    return dict(passed=all(r['passed'] for r in records), records=records)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before',type=Path)
    parser.add_argument('after',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=compare_runs(args.before,args.after)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    for row in result['records']:
        print(row['project'], 'PASS' if row['passed'] else 'FAIL', row['before'], '->', row['after'])
    raise SystemExit(0 if result['passed'] else 1)

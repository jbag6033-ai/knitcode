"""Compare unchanged Flask sources and review oracles before/after engine fixes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'validation/flask_2026_10_22'


def read(path):
    return json.loads(path.read_text())


def main():
    result = dict(scopes={})
    for scope in ['production', 'full']:
        before = read(BASE/scope/'metadata.json')
        after = read(BASE/'improved'/scope/'metadata.json')
        assert before['commit'] == after['commit']
        assert before['source_sha256'] == after['source_sha256']
        assert before['calls'] == after['calls']
        audit = read(BASE/'improved'/f'audit_{scope}'/'STATS.json')
        result['scopes'][scope] = dict(commit=after['commit'], same_source_hashes=True,
                                      calls=after['calls'], before=before['statuses'], after=after['statuses'],
                                      newly_resolved=audit['newly_resolved'], lost=audit['lost_resolutions'],
                                      changed_target_sites=audit['substantive_changes'],
                                      verified=after['verify_graph']==after['verify_statuses']==0)
    before, after = (read(BASE/path/'source_review.json') for path in [Path('.'), Path('improved')])
    oracle = lambda data: [(r['group'],r['file'],r['line'],r['callee'],r['expected'],r['scenario']) for r in data['rows']]
    assert oracle(before) == oracle(after)
    result['review'] = dict(unchanged_oracles=True, before={k:before[k] for k in ['exact','required']},
                           after={k:after[k] for k in ['exact','required']},
                           remaining=[dict(file=r['file'], line=r['line'], callee=r['callee'],
                                           expected=r['expected'],actual=r['actual']) for r in after['rows'] if not r['passed']],
                           note='Development probes, not an independent or population precision/recall estimate.')
    synthetic_before = read(ROOT/'validation/current_evaluation/probes.json')
    synthetic_after = read(BASE/'improved/synthetic_probes.json')
    assert [(r['name'],r['source_sha256'],r['expected']) for r in synthetic_before['records']] == [
        (r['name'],r['source_sha256'],r['expected']) for r in synthetic_after['records']]
    result['synthetic'] = {phase: {k:data[k] for k in ['cases','exact','tp','fp','fn']}
                           for phase,data in [('before',synthetic_before),('after',synthetic_after)]}
    (BASE/'improved/comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()

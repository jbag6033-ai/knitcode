"""Evaluate this engine against the unchanged PyAnalyzer Sublist3r snapshot."""
import contextlib
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from main import run

BASE = ROOT.parent/'knitcode_test/benchmark/PyAnalyzer/Data/RQ3/macro-benchmark C'
SOURCE = BASE/'projects/Sublist3r'
TRUTH = BASE/'ground-truth-cgs/Sublist3r.json'
OUT = ROOT/'validation/sublist3r_2026_10_22'


def compare(truth, predicted):
    tp, fp, fn = predicted & truth, predicted - truth, truth - predicted
    precision = len(tp)/len(predicted) if predicted else 0
    recall = len(tp)/len(truth) if truth else 0
    return dict(truth_pairs=len(truth), predicted_pairs=len(predicted),
                tp=len(tp), fp=len(fp), fn=len(fn), precision=precision, recall=recall,
                f1=2*precision*recall/(precision+recall) if precision+recall else 0,
                true_positive=sorted(tp), false_positive=sorted(fp), false_negative=sorted(fn))


def main(output=OUT, project="Sublist3r"):
    global SOURCE, TRUTH
    references = json.loads((ROOT.parent/"knitcode_test/reports/release-2026-10-16/summary.json").read_text())["results"]
    reference = next(r for r in references if r["project"] == project)
    SOURCE = ROOT.parent/"knitcode_test"/reference["scope"]
    TRUTH = BASE/"ground-truth-cgs"/(project+".json")
    OUT = output
    OUT.mkdir(parents=True, exist_ok=True)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    previous = json.loads((ROOT.parent/'knitcode_test/reports/release-2026-10-16/summary.json').read_text())['results']
    previous = next(r for r in previous if r['project']==project)
    hashes = {p.relative_to(SOURCE).as_posix():sha(p) for p in sorted(SOURCE.rglob('*.py'))}
    assert hashes == previous['source_sha256'], 'Source changed from reference evaluation'
    assert sha(TRUTH) == previous['ground_truth_sha256'], 'Ground truth changed'
    start = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp, (OUT/'analysis.log').open('w') as log, contextlib.redirect_stdout(log):
        analysis_source = SOURCE
        # These benchmark scopes are packages, with fully qualified oracle names.
        # Wrap only the hashed scope; do not include sibling tests or project files.
        if project in ('fabric', 'asciinema'):
            analysis_source = Path(tmp)
            for rel in hashes:
                dest = analysis_source/project/rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(SOURCE/rel, dest)
        facts, symbols, graph = run(analysis_source, OUT/'analysis')
    elapsed = time.perf_counter()-start
    modules = set(symbols['source_modules'])
    internal = lambda name: any(name==m or name.startswith(m+'.') for m in modules)
    oracle = json.loads(TRUTH.read_text())
    truth = {(caller, target) for caller, targets in oracle.items() for target in targets
             if internal(caller) and internal(target)}
    if project == "Sublist3r":
        assert len(truth)==115
    assert len(truth) == previous['tp'] + previous['fn'], 'Oracle scope differs from reference'
    nodes = {n['id']:n for n in graph['nodes']}
    # Benchmark lambdas use a source-order index within the enclosing scope;
    # the engine uses stable source coordinates. Normalize names, not edges.
    lambda_names = {}
    counters = {}
    for s in sorted((s for s in symbols['symbols'] if s['kind']=='LAMBDA'), key=lambda s:(s['file'],s['line'],s['column'])):
        scope = s['canonical_name'].rsplit('.',1)[0]
        counters[scope] = counters.get(scope,0)+1
        lambda_names[s['canonical_name']] = scope + f'.<lambda{counters[scope]}>'
    qualified = lambda name: lambda_names.get(name,name)
    predicted = set()
    function_calls = set()
    evidence = []
    for edge in graph['edges']:
        if edge['type'] not in ('CALLS','INSTANTIATES'):
            continue
        caller = qualified(nodes[edge['source']]['canonical_name'])
        target = qualified(nodes[edge['target']]['canonical_name'])
        if internal(caller) and internal(target):
            predicted.add((caller,target))
            if edge['type']=='CALLS' and nodes[edge['target']]['kind'] in ('FUNCTION','METHOD','LAMBDA'):
                function_calls.add((caller,target))
            evidence.append(dict(caller=caller, target=target, relation=edge['type'], **edge['evidence']))
    functions = {qualified(s['canonical_name']) for s in symbols['symbols'] if s['kind'] in ('FUNCTION','METHOD','LAMBDA')}
    project = lambda pairs: {(a,b) for a,b in pairs if a in functions | modules and b in functions}
    result = dict(source=str(SOURCE), ground_truth=str(TRUTH), python=sys.version,
                  source_sha256=hashes, ground_truth_sha256=sha(TRUTH),
                  engine_sha256={p.name:sha(p) for p in sorted(ROOT.glob('*.py'))},
                  files=facts['python_file_count'], parse_errors=facts['parse_errors'],
                  seconds_including_exports=elapsed, call_sites=graph['total_call_sites'],
                  statuses=graph['status_summary']['statuses'],
                  lambda_name_normalization=lambda_names,
                  contract='Unique exact caller-callee pairs; both endpoints in source-derived module namespaces. '
                           'Source-ordered lambda notation normalization only. No suffix matching, edge rewrites or constructor substitution.',
                  raw_including_class_targets=compare(truth,predicted),
                  function_calls_all_truth_pairs=compare(truth,function_calls),
                  declared_function_projection=compare(project(truth),project(predicted)),
                  excluded_class_or_nonfunction_predictions=sorted(predicted-project(predicted)),
                  reference_knitcode_test={k:previous[k] for k in ['tp','fp','fn','precision','recall','f1']},
                  note='Benchmark discrepancies are not automatically proven runtime errors; inspect pair differences.')
    if project == 'Sublist3r':
        result['function_calls_all_115_truth_pairs'] = result['function_calls_all_truth_pairs']
    (OUT/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUT/'predicted_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    for contract in ['function_calls_all_truth_pairs','raw_including_class_targets','declared_function_projection']:
        print(contract, json.dumps({k:v for k,v in result[contract].items() if not isinstance(v,list)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--project', choices=['Sublist3r', 'asciinema', 'autojump', 'fabric', 'face_classification'], default='Sublist3r')
    args = parser.parse_args()
    main(args.output, args.project)

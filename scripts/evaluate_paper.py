"""Evaluate full, unchanged PyCG ground truth using the original artifact scorer."""
import argparse
from collections import defaultdict
import contextlib
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from main import run
from external_calls import build_external_call_graph

BASE = ROOT.parent / 'knitcode_test/benchmark/PyAnalyzer/Data/RQ3/macro-benchmark C'
PROJECTS = ['autojump', 'fabric', 'asciinema', 'face_classification', 'Sublist3r']
SCOPES = {'autojump': 'bin', 'fabric': '.', 'asciinema': 'asciinema', 'face_classification': 'src', 'Sublist3r': '.'}
BUILTIN_TYPES = {'str': 'PyStr', 'bytes': 'PyBytes', 'list': 'PyList', 'dict': 'PyDict', 'set': 'PySet', 'tuple': 'PyTuple'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def adjacency(pairs):
    result = defaultdict(set)
    for a, b in pairs:
        result[a].add(b)
    return {a: sorted(bs) for a, bs in sorted(result.items())}


def score(actual, expected, scorer):
    precision = scorer['measure_precision'](actual, expected)
    recall = scorer['measure_recall'](actual, expected)
    pred = {(a, b) for a, bs in actual.items() for b in bs}
    truth = {(a, b) for a, bs in expected.items() for b in bs}
    expected_items = sum(len(bs) for bs in expected.values())
    recalled_items = sum(b in actual.get(a, []) for a, bs in expected.items() for b in bs)
    return dict(precision=precision, recall=recall,
                ground_truth_items_including_duplicates=expected_items, recalled_items_including_duplicates=recalled_items,
                f1=2*precision*recall/(precision+recall) if precision+recall else 0,
                predicted_pairs=len(pred), truth_pairs=len(truth), tp=len(pred & truth),
                fp=len(pred-truth), fn=len(truth-pred),
                true_positive=sorted(pred & truth), false_positive=sorted(pred-truth), false_negative=sorted(truth-pred))


def external_name(name):
    if name.startswith('builtins.'):
        return '<builtin>.' + name[len('builtins.'):]
    head, dot, rest = name.partition('.')
    if head in BUILTIN_TYPES and dot:
        return '<**' + BUILTIN_TYPES[head] + '**>.' + rest
    return name


def evaluate(project, out, scorer, artifact_root=None):
    source = BASE/'projects'/project
    scope = source/SCOPES[project]
    files = sorted(scope.rglob('*.py'))
    if project == 'fabric':
        # Exact file selection in generate_pycg_cgs.sh: grep -v tests | grep -v setup.py
        files = [p for p in files if 'tests' not in str(p.relative_to(source)) and 'setup.py' not in str(p.relative_to(source))]
    out.mkdir(parents=True, exist_ok=True)
    hashes = {p.relative_to(source).as_posix(): sha(p) for p in files}
    truth_path = BASE/'ground-truth-cgs'/(project+'.json')
    truth = json.loads(truth_path.read_text())
    artifact_check = None
    if artifact_root:
        original = artifact_root/'data/macro-benchmark'
        artifact_truth = original/'ground-truth-cgs'/(project+'.json')
        if artifact_truth.exists():
            assert json.loads(artifact_truth.read_text()) == truth, 'Artifact ground truth differs'
            artifact_scope = original/'projects'/project/SCOPES[project]
            original_files = sorted(artifact_scope.rglob('*.py'))
            if project == 'fabric':
                original_files = [p for p in original_files if 'tests' not in str(p.relative_to(original/'projects'/project)) and 'setup.py' not in str(p.relative_to(original/'projects'/project))]
            original_names = {p.relative_to(original/'projects'/project).as_posix() for p in original_files}
            assert original_names == set(hashes), 'Artifact input file selection differs'
            artifact_check = dict(ground_truth_equal=True, source_file_selection_equal=True,
                source_differences=[rel for rel, digest in hashes.items()
                                    if not (original/'projects'/project/rel).exists() or sha(original/'projects'/project/rel) != digest])
    start = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp, (out/'analysis.log').open('w') as log, contextlib.redirect_stdout(log):
        root = Path(tmp)
        for path in files:
            # These two projects retain their package prefix under --package.
            rel = path.relative_to(source if project in ('fabric', 'asciinema') else scope)
            dest = root/rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
        facts, symbols, graph = run(root, out/'analysis', source_roots=['.'])
    assert facts['python_file_count'] + len(facts['parse_errors']) == len(files), 'Scanner excluded selected inputs'
    elapsed = time.perf_counter()-start
    nodes = {n['id']: n for n in graph['nodes']}
    lambdas, counters = {}, defaultdict(int)
    for s in sorted((s for s in symbols['symbols'] if s['kind']=='LAMBDA'), key=lambda s:(s['file'], s['line'], s['column'])):
        scope_name = s['canonical_name'].rsplit('.', 1)[0]
        counters[scope_name] += 1
        lambdas[s['canonical_name']] = scope_name + f'.<lambda{counters[scope_name]}>'
    qualified = lambda name: lambdas.get(name, name)
    pairs, raw, evidence = set(), set(), []
    init_sites = {e['evidence'].get('call_id') for e in graph['edges']
                  if e['type']=='CALLS' and nodes[e['target']]['name']=='__init__'}
    for edge in graph['edges']:
        if edge['type'] not in ('CALLS', 'INSTANTIATES'):
            continue
        pair = (qualified(nodes[edge['source']]['canonical_name']), qualified(nodes[edge['target']]['canonical_name']))
        raw.add(pair)
        if edge['type']=='INSTANTIATES' and edge['evidence'].get('call_id') in init_sites:
            continue
        pairs.add(pair)
        evidence.append(dict(caller=pair[0], target=pair[1], **edge['evidence']))
    baseline = adjacency(pairs)
    external = build_external_call_graph(symbols, graph)
    external_nodes = {n['id']: n for n in external['nodes']}
    for edge in external['edges']:
        caller = qualified(nodes[edge['source']]['canonical_name'])
        target = external_name(external_nodes[edge['target']]['canonical_name'])
        pairs.add((caller, target))
        evidence.append(dict(caller=caller, target=target, **edge['evidence']))
    actual = adjacency(pairs)
    (out/'predicted.json').write_text(json.dumps(actual, indent=2)+'\n')
    (out/'baseline_internal_only.json').write_text(json.dumps(baseline, indent=2)+'\n')
    (out/'evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
    result = dict(project=project, source=str(source), source_sha256=hashes,
                  ground_truth_sha256=sha(truth_path), files=facts['python_file_count'], parse_errors=facts['parse_errors'],
                  engine_sha256={p.name:sha(p) for p in ROOT.glob('*.py')}, seconds_including_exports=elapsed,
                  artifact_check=artifact_check, lambda_names=lambdas,
                  contract='Original artifact precision/recall functions; ALL ground-truth edges, no namespace or caller filtering. '
                           'Unique predicted caller-callee pairs. Builtin/lambda notation normalization; '
                           'internal class target omitted when the same site has an initializer CALLS edge. '
                           'No truth-driven alias correction, suffix matching, misspelling fixes, or edge deletion.',
                  baseline_internal_only=score(baseline, truth, scorer), full_calls=score(actual, truth, scorer),
                  raw_internal_with_class_targets=score(adjacency(raw), truth, scorer), external_summary=external['summary'])
    (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    return {k:v for k,v in result.items() if k in ('project','files','seconds_including_exports','artifact_check')} | {
        mode: {k:v for k,v in result[mode].items() if not isinstance(v,list)} for mode in ('baseline_internal_only','full_calls')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-script', type=Path, default=ROOT/'validation/paper_2026_10_22/reference/compare_macro_benchmark_cg.py')
    parser.add_argument('--artifact-root', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'validation/paper_2026_10_22')
    parser.add_argument('--project', choices=PROJECTS, action='append')
    args = parser.parse_args()
    scorer = runpy.run_path(str(args.reference_script))
    args.output.mkdir(parents=True, exist_ok=True)
    results=[]
    for project in args.project or PROJECTS:
        row=evaluate(project, args.output/project, scorer, args.artifact_root)
        results.append(row)
        print(json.dumps(row), flush=True)
    (args.output/'summary.json').write_text(json.dumps(dict(reference_script_sha256=sha(args.reference_script), results=results), indent=2)+'\n')

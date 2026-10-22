"""Source-reviewed Flask probes. Curated diagnostics, not a random accuracy sample."""
import ast
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'validation/flask_2026_10_22'
REPO = ROOT / 'benchmarks/flask'
PIN = 'd086db856be187255b8ec61ef409357393020f32'

# Exact direct bindings: imports and locally defined module functions.
EXACT = [
    ('__main__.py', 3, 'main', 'FUNCTION:flask.cli.main'),
    ('app.py', 408, 'send_from_directory', 'FUNCTION:flask.helpers.send_from_directory'),
    ('app.py', 707, 'get_load_dotenv', 'FUNCTION:flask.helpers.get_load_dotenv'),
    ('app.py', 708, 'cli.load_dotenv', 'FUNCTION:flask.cli.load_dotenv'),
    ('cli.py', 348, 'prepare_import', 'FUNCTION:flask.cli.prepare_import'),
    ('cli.py', 349, 'locate_app', 'FUNCTION:flask.cli.locate_app'),
    ('helpers.py', 529, '_prepare_send_file_kwargs', 'FUNCTION:flask.helpers._prepare_send_file_kwargs'),
    ('helpers.py', 583, '_prepare_send_file_kwargs', 'FUNCTION:flask.helpers._prepare_send_file_kwargs'),
    ('templating.py', 148, '_render', 'FUNCTION:flask.templating._render'),
    ('templating.py', 160, '_render', 'FUNCTION:flask.templating._render'),
    ('json/tag.py', 323, 'dumps', 'FUNCTION:flask.json.dumps'),
    ('json/tag.py', 327, 'loads', 'FUNCTION:flask.json.loads'),
    ('json/__init__.py', 44, '_json.dumps', None),
    ('json/__init__.py', 105, '_json.loads', None),
]

# Required *possible* targets in an explicitly scoped concrete-class scenario.
# Additional candidates are not scored as FP: this is not a complete oracle
# over every possible extension/subclass/user application.
REQUIRED = [
    ('app.py', 987, 'self.make_default_options_response', 'METHOD:flask.app.Flask.make_default_options_response'),
    ('app.py', 1014, 'self.preprocess_request', 'METHOD:flask.app.Flask.preprocess_request'),
    ('app.py', 1016, 'self.dispatch_request', 'METHOD:flask.app.Flask.dispatch_request'),
    ('app.py', 1018, 'self.handle_user_exception', 'METHOD:flask.app.Flask.handle_user_exception'),
    ('app.py', 1019, 'self.finalize_request', 'METHOD:flask.app.Flask.finalize_request'),
    ('app.py', 1039, 'self.make_response', 'METHOD:flask.app.Flask.make_response'),
    ('app.py', 1041, 'self.process_response', 'METHOD:flask.app.Flask.process_response'),
    ('app.py', 1075, 'self.async_to_sync', 'METHOD:flask.app.Flask.async_to_sync'),
    ('app.py', 1597, 'self.full_dispatch_request', 'METHOD:flask.app.Flask.full_dispatch_request'),
    ('templating.py', 125, 'app.update_template_context', 'METHOD:flask.app.Flask.update_template_context'),
    ('json/__init__.py', 41, 'current_app.json.dumps', 'METHOD:flask.json.provider.DefaultJSONProvider.dumps'),
    ('json/__init__.py', 103, 'current_app.json.loads', 'METHOD:flask.json.provider.DefaultJSONProvider.loads'),
    ('config.py', 124, 'self.from_pyfile', 'METHOD:flask.config.Config.from_pyfile'),
    ('config.py', 215, 'self.from_object', 'METHOD:flask.config.Config.from_object'),
    ('config.py', 302, 'self.from_mapping', 'METHOD:flask.config.Config.from_mapping'),
    ('json/tag.py', 323, 'self.tag', 'METHOD:flask.json.tag.TaggedJSONSerializer.tag'),
]


def load(file):
    return json.loads(file.read_text())


def source_check(scope, analysis_root=OUT):
    folder = analysis_root / scope
    metadata = load(folder / 'metadata.json')
    assert metadata['commit'] == PIN
    symbols = load(folder / 'symbol_result.json')
    facts = load(folder / 'ast_result.json')
    graph = load(folder / 'graph_result.json')
    repo = REPO / 'src' if scope == 'production' else REPO
    definitions, old_definitions, calls = set(), set(), set()
    for f in facts['files']:
        file = f['file']
        source = (repo / file.split('/', 1)[1]).read_text(encoding='utf-8-sig')
        assert hashlib.sha256(source.encode()).hexdigest() == metadata['source_sha256'][file]
        for node in ast.walk(ast.parse(source)):
            loc = (file, getattr(node, 'lineno', None), getattr(node, 'col_offset', None))
            if isinstance(node, ast.Call):
                calls.add(loc)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                old_definitions.add(loc)
                definitions.add(loc)
            elif isinstance(node, ast.Lambda):
                definitions.add(loc)
    missing_symbols = [s['id'] for s in symbols['symbols']
                       if (s['file'], s['line'], s['column']) not in definitions]
    missing_calls = [s['id'] for s in symbols['calls']
                     if (s['file'], s['line'], s['column']) not in calls]
    legacy_missing = [s for s in symbols['symbols']
                      if (s['file'], s['line'], s['column']) not in old_definitions]
    assert not missing_symbols and not missing_calls
    assert all(s['kind'] == 'LAMBDA' for s in legacy_missing)
    return dict(symbols=len(symbols['symbols']), calls=len(symbols['calls']),
                missing_symbols=missing_symbols, missing_calls=missing_calls,
                legacy_checker_missing_lambda_count=len(legacy_missing),
                structural_16_checks_pass='PASS=16 FAIL=0' in (folder/'verify_graph.log').read_text(),
                status_10_checks_pass='Call status: PASS=10 FAIL=0' in (folder/'verify_statuses.log').read_text(),
                note=('Current verification and independent lambda-aware source check pass.'
                      if metadata['verify_graph'] == metadata['verify_statuses'] == 0 else
                      'Legacy verify_v23 source-location check omits ast.Lambda. '
                      'Its nonzero exit is preserved in metadata/logs. Independent lambda-aware source check passes.'))


def main(analysis_root=OUT):
    graph = load(analysis_root / 'production/graph_result.json')
    symbols = load(analysis_root / 'production/symbol_result.json')
    defs = {s['id']: s for s in symbols['symbols']}
    rows = []
    for group, specs in [('exact_binding', EXACT), ('required_base_scenario', REQUIRED)]:
        for file, line, callee, target in specs:
            stored = 'src/flask/' + file
            matched = [r for r in graph['call_statuses']
                       if r['file'] == stored and r['line'] == line and r['callee_text'] == callee]
            assert len(matched) == 1, (file, line, callee)
            row = matched[0]
            actual = set(row['target_ids'])
            expected = {target} if target else set()
            if target:
                assert target in defs
            ok = (actual == expected if group == 'exact_binding' else expected <= actual)
            if not target:
                ok &= row['status'] == 'KNOWN_NON_INTERNAL'
            caller = defs.get(row['caller_id'])
            lines = (REPO / stored).read_text().splitlines()
            scenario = ('Default namespaces, import binding unchanged.' if group == 'exact_binding'
                        else 'Concrete base Flask/Config/TaggedJSONSerializer; no user overrides or subclass '
                             'creation; active default app/JSON provider where applicable. Required possible target only.')
            rows.append(dict(group=group, file=stored, line=line, callee=callee,
                             caller=row['caller_id'], expected=sorted(expected), actual=sorted(actual),
                             status=row['status'], certainty=row['certainty'], passed=ok, scenario=scenario,
                             source_excerpt='\n'.join(f'{i+1}: {lines[i]}' for i in range(max(0,line-3),min(len(lines),line+2))),
                             expected_definitions=[dict(id=t, file=defs[t]['file'], line=defs[t]['line']) for t in expected],
                             caller_location=dict(file=caller['file'], line=caller['line']) if caller else None))
    exact = [r for r in rows if r['group']=='exact_binding']
    required = [r for r in rows if r['group']=='required_base_scenario']
    result = dict(commit=PIN, review_method='Source-reviewed by the same assistant; no independent human review. '
                  'Curated cases include observed failures. No whole-project precision/recall inference.',
                  exact=dict(cases=len(exact), passed=sum(r['passed'] for r in exact),
                             tp=sum(len(set(r['expected']) & set(r['actual'])) for r in exact),
                             fp=sum(len(set(r['actual']) - set(r['expected'])) for r in exact),
                             fn=sum(len(set(r['expected']) - set(r['actual'])) for r in exact)),
                  required=dict(cases=len(required), found=sum(r['passed'] for r in required),
                                missing=sum(not r['passed'] for r in required),
                                note='Only required targets are scored; additional candidates are not labeled FP.'),
                  source_checks={scope:source_check(scope, analysis_root) for scope in ['production','full']}, rows=rows)
    (analysis_root/'source_review.json').write_text(json.dumps(result, indent=2)+'\n')
    with (analysis_root/'source_review.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['group','file','line','callee','caller','expected','actual','status','certainty','passed','scenario','source_excerpt'])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row[k]) if isinstance(row[k],list) else row[k] for k in writer.fieldnames})
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis-root', type=Path, default=OUT)
    main(parser.parse_args().analysis_root)

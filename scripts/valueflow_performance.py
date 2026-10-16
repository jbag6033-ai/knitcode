"""Repeat a selected analysis with fresh resolvers and hash complete call records."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analyzer.resolver import CallResolver
from scripts.pyanalyzer_baseline import BASE, SCOPES


def call_digest(calls):
    rows = sorted(json.dumps(row, sort_keys=True, ensure_ascii=True) for row in calls)
    return hashlib.sha256('\n'.join(rows).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projects', nargs='+', choices=sorted(SCOPES), default=['autojump'])
    parser.add_argument('--repeat', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error('--repeat must be positive')
    reports = []
    for name in args.projects:
        project = BASE / 'projects' / name / SCOPES[name][0]
        samples = []
        for iteration in range(args.repeat + 1):
            started = perf_counter()
            resolver = CallResolver(project)
            resolver.analyze_project()
            calls = resolver.resolve_calls()
            elapsed = perf_counter() - started
            sample = {'seconds': elapsed, 'calls_sha256': call_digest(calls),
                      'records': len(calls), 'value_flow': resolver.value_flow_status,
                      'cache': getattr(resolver, 'value_flow_cache', None)}
            if iteration:
                samples.append(sample)
        assert len({row['calls_sha256'] for row in samples}) == 1
        reports.append({'project': name, 'warmup_runs': 1, 'samples': samples,
                        'median_seconds': median(row['seconds'] for row in samples),
                        'source_sha256': {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in sorted(project.rglob('*.py'))}})
    output = {'python': platform.python_version(), 'repeat': args.repeat, 'results': reports,
              'analyzer_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted((ROOT/'analyzer').glob('*.py'))},
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'measurement': 'Fresh resolver for every run; one unmeasured warmup; parse + resolve wall time, hashing excluded; no profiler.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2)+'\n')
    for report in reports:
        print(json.dumps({'project': report['project'], 'median_seconds': report['median_seconds'],
                          'calls_sha256': report['samples'][0]['calls_sha256']}))


if __name__ == '__main__':
    main()

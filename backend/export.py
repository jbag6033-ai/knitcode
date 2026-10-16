"""JSON bridge for the VS Code extension; never imports analyzed source."""
import argparse
import json
import os
from pathlib import Path

from analyzer.graph import CodeGraph
from analyzer.parser import parse_file
from analyzer.resolver import CallResolver
from git_analyzer.history import read_history

EXCLUDED = {'.git', '.venv', 'venv', 'Knitcode', '__pycache__', 'node_modules', 'benchmark', '.tox', 'lib', 'vendor'}


def export_project(root, days=90, limit=300, *, entrypoints=None):
    root = Path(root).resolve()
    paths, warnings = [], []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not Path(directory, d).is_symlink())
        # Also exclude virtual environments with arbitrary names.
        if Path(directory, 'pyvenv.cfg').exists():
            dirs[:] = []
            continue
        for name in sorted(files):
            path = Path(directory, name)
            if path.suffix != '.py' or path.is_symlink():
                continue
            try:
                parse_file(path)
                paths.append(path)
            except (SyntaxError, UnicodeError, OSError) as exc:
                warnings.append(f'{path.relative_to(root)}: {exc}')
    resolver = CallResolver(root, entrypoints=entrypoints)
    resolver.analyze_project(paths)
    calls = resolver.resolve_calls()
    graph = CodeGraph().build_from_resolved_calls(calls)
    # Include definitions even if no resolved call reaches them.
    for definitions in (resolver.function_definitions, resolver.class_definitions):
        for group in definitions.values():
            for definition in group:
                name = definition['name']
                if definition.get('class'):
                    name = f"{definition['class']}.{name}"
                graph.add_node(f"{definition['file']}::{name}", name=name,
                               file=definition['file'], lineno=definition['lineno'], type=definition['type'])
    for path in paths:
        file = path.relative_to(root).as_posix()
        graph.add_node('file:' + file, name=path.name, file=file, lineno=1, type='file')
    for node in list(graph.nodes.values()):
        if node['type'] != 'file':
            graph.add_edge('file:' + node['file'], node['id'], type='contains')
    history = read_history(root, {p.relative_to(root).as_posix() for p in paths}, days, limit)
    for pair in history['pairs']:
        graph.add_edge('file:' + pair['source'], 'file:' + pair['target'],
                       type='cochange', commits=pair['commits'], count=len(pair['commits']))
    incoming = {}
    for edge in graph.edges:
        if edge['type'] in ('calls', 'instantiates'):
            incoming.setdefault(edge['target'], set()).add(edge['source'])
    for node in graph.nodes.values():
        node['callers'] = len(incoming.get(node['id'], set()))
        node['changes'] = history['changes'].get(node['file'], 0)
    unresolved = sum(c['target'] is None for c in calls)
    result = {**graph.to_dict(), 'history': history, 'warnings': warnings,
            'summary': {'files': len(paths), 'resolved': len(calls) - unresolved,
                        'unresolved': unresolved}, 'flow': resolver.value_flow_status}
    if entrypoints is not None:
        result['entrypoints'] = entrypoints
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('--days', type=int, default=90)
    parser.add_argument('--limit', type=int, default=300)
    parser.add_argument('--entrypoints', type=Path, help='Explicit public API input types (JSON version 1)')
    args = parser.parse_args()
    config = json.loads(args.entrypoints.read_text()) if args.entrypoints else None
    print(json.dumps(export_project(args.root, args.days, args.limit, entrypoints=config), ensure_ascii=True))


if __name__ == '__main__':
    main()

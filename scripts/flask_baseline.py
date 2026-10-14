"""Record the current analyzer's Flask baseline without changing its behavior."""

import argparse
import ast
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyzer.graph import CodeGraph
from analyzer.resolver import CallResolver
from analyzer.visualize import build_visualization


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fingerprint(paths, root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    project = ROOT / "benchmark/Flask/src/flask"
    if not project.is_dir():
        parser.error(f"Flask source directory does not exist: {project}")

    started = perf_counter()
    resolver = CallResolver(project)
    resolver.analyze_project()
    parsed = perf_counter()
    results = resolver.resolve_calls()
    resolved = perf_counter()
    graph = CodeGraph().build_from_resolved_calls(results).to_dict()
    built = perf_counter()
    unresolved = [result for result in results if result["target"] is None]
    source_paths = list(project.rglob("*.py"))
    per_file = []
    for path in sorted(source_paths):
        name = str(path.relative_to(project))
        source = path.read_text(encoding="utf-8")
        visitor = resolver.file_results[name]
        file_results = [result for result in results if result["caller_file"] == name]
        per_file.append({
            "file": name,
            "lines": len(source.splitlines()),
            "ast_call_expressions": sum(isinstance(node, ast.Call) for node in ast.walk(ast.parse(source))),
            "function_and_method_definitions": len(visitor.functions),
            "class_definitions": len(visitor.classes),
            "call_records": len(file_results),
            "resolved_records": sum(result["target"] is not None for result in file_results),
            "unresolved_records": sum(result["target"] is None for result in file_results),
        })

    summary = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "python_version": platform.python_version(),
        "flask_commit": subprocess.check_output(
            ["git", "-C", str(project), "rev-parse", "HEAD"], text=True,
        ).strip(),
        "knitcode_head": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True,
        ).strip(),
        "scope": "benchmark/Flask/src/flask (tests, examples and external dependencies excluded)",
        "source_sha256": fingerprint(source_paths, project),
        "analyzer_sha256": fingerprint((ROOT / "analyzer").glob("*.py"), ROOT),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "files": len(per_file),
        "source_lines": sum(item["lines"] for item in per_file),
        "ast_call_expressions": sum(item["ast_call_expressions"] for item in per_file),
        "function_and_method_definitions": sum(item["function_and_method_definitions"] for item in per_file),
        "class_definitions": sum(item["class_definitions"] for item in per_file),
        "call_records": len(results),
        "resolved_records": len(results) - len(unresolved),
        "unresolved_records": len(unresolved),
        "resolution_rate": (len(results) - len(unresolved)) / len(results) if results else 0,
        "graph_nodes": len(graph["nodes"]),
        "graph_edge_records": len(graph["edges"]),
        "unique_caller_callee_edges": len({(edge["source"], edge["target"]) for edge in graph["edges"]}),
        "timing_seconds": {
            "parse_and_visit": parsed - started,
            "resolve": resolved - parsed,
            "graph": built - resolved,
            "total_analysis": built - started,
        },
        "top_unresolved_callees": Counter(result["callee"] for result in unresolved).most_common(20),
        "per_file": per_file,
        "limitations": [
            "No ground truth: resolution rate is not precision, recall or accuracy.",
            "Unresolved calls include builtins and external APIs as well as missed internal calls.",
            "Call records include synthetic enclosing-function-to-lambda relationships.",
            "Resolved targets can be incorrect; no complete manual correctness audit was performed.",
            "Analyzer hashes identify the working-tree implementation, including uncommitted changes.",
        ],
    }
    write_json(output / "summary.json", summary)
    write_json(output / "calls.json", results)
    write_json(output / "graph.json", graph)
    with (output / "unresolved.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["caller_file", "caller", "callee", "lineno"])
        writer.writeheader()
        writer.writerows({key: result[key] for key in writer.fieldnames} for result in unresolved)

    # Keep PyVis's local assets beside the HTML, outside the repository root.
    original_directory = Path.cwd()
    try:
        os.chdir(output)
        build_visualization(project, output / "graph.html")
    finally:
        os.chdir(original_directory)
    print(json.dumps({key: summary[key] for key in (
        "files", "source_lines", "ast_call_expressions", "call_records",
        "resolved_records", "unresolved_records", "resolution_rate",
        "graph_nodes", "graph_edge_records", "unique_caller_callee_edges",
        "timing_seconds", "top_unresolved_callees",
    )}, indent=2))


if __name__ == "__main__":
    main()

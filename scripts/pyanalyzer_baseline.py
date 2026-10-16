"""Evaluate larger PyAnalyzer projects against project-internal ground truth."""

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyzer.evaluate import make_qualified_name
from analyzer.resolver import CallResolver
from analyzer.comparison import compare_pairs, declared_symbols, project_declared_functions

BASE = ROOT / "benchmark/PyAnalyzer/Data/RQ3/macro-benchmark C"
# Package modules keep their package prefix. Script roots use their filenames.
SCOPES = {
    "Sublist3r": (".", ""),
    "asciinema": ("asciinema", "asciinema"),
    "autojump": ("bin", ""),
    "fabric": ("fabric", "fabric"),
    "face_classification": ("src", ""),
}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def module_name(file_name, prefix):
    path = Path(prefix) / file_name if prefix else Path(file_name)
    name = make_qualified_name(path, "<module>")
    return name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--entrypoints", type=Path, help="Explicit public API input contract; one project only")
    parser.add_argument("--projects", nargs="+", choices=sorted(SCOPES))
    parser.add_argument("--include-smaller", action="store_true",
                        help="Include small projects as explicitly labeled holdout evaluations")
    args = parser.parse_args()
    if args.entrypoints and (not args.projects or len(args.projects) != 1):
        parser.error('--entrypoints requires exactly one --projects selection')
    entrypoints = json.loads(args.entrypoints.read_text()) if args.entrypoints else None
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    inventory = []
    for name, (directory, prefix) in SCOPES.items():
        project = BASE / "projects" / name / directory
        paths = sorted(project.rglob("*.py"))
        inventory.append({
            "project": name, "scope": str(project.relative_to(ROOT)),
            "module_prefix": prefix, "files": len(paths),
            "lines": sum(len(path.read_text(encoding="utf-8").splitlines()) for path in paths),
        })
    threshold = inventory[0]["lines"]
    reports = []
    for item in inventory:
        name = item["project"]
        if args.projects and name not in args.projects:
            continue
        if not args.include_smaller and name != "Sublist3r" and item["lines"] <= threshold:
            continue
        project = ROOT / item["scope"]
        prefix = item["module_prefix"]
        gt_path = BASE / "ground-truth-cgs" / f"{name}.json"
        report = dict(item)
        report["source_sha256"] = {
            str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(project.rglob("*.py"))
        }
        report["ground_truth_sha256"] = hashlib.sha256(gt_path.read_bytes()).hexdigest()
        modules = sorted({module_name(str(path.relative_to(project)), prefix)
                          for path in project.rglob("*.py")} - {""})
        report["internal_modules"] = modules

        def internal(symbol):
            return any(symbol == module or symbol.startswith(module + ".") for module in modules)

        gt_graph = json.loads(gt_path.read_text(encoding="utf-8"))
        truth = {(caller, callee) for caller, callees in gt_graph.items()
                 for callee in callees if internal(caller) and internal(callee)}
        report["ground_truth_edges"] = len(truth)
        started = perf_counter()
        try:
            resolver = CallResolver(project, entrypoints=entrypoints)
            resolver.analyze_project()
            calls = resolver.resolve_calls()
            predicted = set()
            for call in calls:
                target = call["target"]
                if target is None:
                    continue
                target_name = target["name"]
                if target.get("class") is not None:
                    target_name = f"{target['class']}.{target_name}"
                caller_path = str(Path(prefix) / call["caller_file"]) if prefix else call["caller_file"]
                target_path = str(Path(prefix) / target["file"]) if prefix else target["file"]
                caller = make_qualified_name(caller_path, call["caller"])
                callee = make_qualified_name(target_path, target_name)
                if internal(caller) and internal(callee):
                    predicted.add((caller, callee))
            tp, fp, fn = predicted & truth, predicted - truth, truth - predicted
            precision = len(tp) / len(predicted) if predicted else 0
            recall = len(tp) / len(truth) if truth else 0
            report.update({
                "status": "ok", "call_records": len(calls),
                "value_flow": getattr(resolver, "value_flow_status", None),
                "resolved_records": sum(call["target"] is not None for call in calls),
                "predicted_edges": len(predicted), "tp": len(tp), "fp": len(fp), "fn": len(fn),
                "precision": precision, "recall": recall,
                "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
                "top_unresolved": Counter(call["callee"] for call in calls if call["target"] is None).most_common(15),
            })
            write_json(output / f"{name}-edges.json", {
                "true_positive": sorted(tp), "false_positive": sorted(fp), "false_negative": sorted(fn),
            })
            write_json(output / f"{name}-calls.json", calls)
            symbols = declared_symbols(resolver, prefix)
            projected_truth, excluded_truth = project_declared_functions(truth, symbols)
            projected_predicted, excluded_predicted = project_declared_functions(predicted, symbols)
            projected_metrics, projected_diff = compare_pairs(projected_truth, projected_predicted)
            report['function_projection'] = {
                'contract': 'source-declared-functions-v1', **projected_metrics,
                'excluded_truth_edges': len(excluded_truth),
                'excluded_predicted_edges': len(excluded_predicted),
            }
            write_json(output / f"{name}-function-projection.json", {
                'metrics': report['function_projection'], 'edges': projected_diff,
                'excluded_truth': excluded_truth, 'excluded_predicted': excluded_predicted,
                'symbols': {key: sorted(values) for key, values in symbols.items()},
            })
        except Exception:
            report.update({"status": "error", "traceback": traceback.format_exc()})
        report["analysis_seconds"] = perf_counter() - started
        reports.append(report)
        print(json.dumps({key: value for key, value in report.items()
                          if key not in {"source_sha256", "internal_modules", "top_unresolved"}}, ensure_ascii=False))
    write_json(output / "summary.json", {
        "generated_at": datetime.now().astimezone().isoformat(), "python": platform.python_version(),
        "selection": ("Explicit inclusion of smaller projects; comments, docstrings and blanks included" if args.include_smaller
                      else "Core-source Python lines > Sublist3r; comments, docstrings and blanks included"),
        "requested_projects": args.projects,
        "entrypoints": entrypoints,
        "entrypoints_sha256": hashlib.sha256(args.entrypoints.read_bytes()).hexdigest() if args.entrypoints else None,
        "threshold_lines": threshold, "inventory": inventory, "results": reports,
        "analyzer_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in sorted((ROOT / "analyzer").glob("*.py"))},
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "evaluation": "Unique caller-callee pairs; both endpoints within source-derived module namespaces. Naming normalization only, no edge rewriting.",
    })


if __name__ == "__main__":
    main()

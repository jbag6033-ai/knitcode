"""Evaluate KnitCode against a PyCG-style ground-truth call graph."""

import json
from pathlib import Path

from analyzer.resolver import CallResolver


PROJECT = Path(
    "benchmark/PyAnalyzer/Data/RQ3/macro-benchmark C/projects/Sublist3r"
)

GROUND_TRUTH = Path(
    "benchmark/PyAnalyzer/Data/RQ3/macro-benchmark C/"
    "ground-truth-cgs/Sublist3r.json"
)


def file_to_module(file_path):
    """
    Convert KnitCode file paths to Python module names.

    Examples:
        sublist3r.py
            -> sublist3r

        subbrute/subbrute.py
            -> subbrute.subbrute
    """

    path = Path(file_path)

    if path.name == "__init__.py":
        parts = path.parent.parts
    else:
        parts = path.with_suffix("").parts

    return ".".join(parts)


def make_qualified_name(file_path, name):
    """
    Convert KnitCode names to the naming scheme used by ground truth.

    Example:
        sublist3r.py + BaiduEnum.findsubs
            -> sublist3r.BaiduEnum.findsubs
    """

    module = file_to_module(file_path)

    if name == "<module>":
        return module

    return f"{module}.{name}"


def load_knitcode_edges():
    """
    Run KnitCode and return resolved project-internal call edges.
    """

    resolver = CallResolver(PROJECT)
    resolver.analyze_project()

    results = resolver.resolve_calls()

    edges = set()

    for result in results:
        target = result["target"]

        # Current KnitCode only places successfully resolved
        # project-internal calls in its graph.
        if target is None:
            continue

        caller = make_qualified_name(
            result["caller_file"],
            result["caller"],
        )

        if (
            target.get("type") == "method"
            and target.get("class")
        ):
            target_name = (
                f"{target['class']}.{target['name']}"
            )
        else:
            target_name = target["name"]

        callee = make_qualified_name(
            target["file"],
            target_name,
        )

        edges.add((caller, callee))

    return edges, results


def is_internal(name):
    """
    Keep only calls belonging to the Sublist3r project.
    """

    return (
        name == "sublist3r"
        or name.startswith("sublist3r.")
        or name == "subbrute"
        or name.startswith("subbrute.")
    )


def load_ground_truth_edges():
    """
    Load ground truth and keep only project-internal edges.
    """

    with GROUND_TRUTH.open(
        "r",
        encoding="utf-8",
    ) as f:
        graph = json.load(f)

    edges = set()

    for caller, callees in graph.items():
        if not is_internal(caller):
            continue

        for callee in callees:
            if is_internal(callee):
                edges.add((caller, callee))

    return edges


def main():
    knitcode_edges, raw_results = load_knitcode_edges()
    ground_truth_edges = load_ground_truth_edges()

    true_positive = knitcode_edges & ground_truth_edges
    false_positive = knitcode_edges - ground_truth_edges
    false_negative = ground_truth_edges - knitcode_edges

    tp = len(true_positive)
    fp = len(false_positive)
    fn = len(false_negative)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    resolved_count = sum(
        result["target"] is not None
        for result in raw_results
    )

    print("=== KnitCode Sublist3r Evaluation ===")
    print()

    print(f"Detected call expressions : {len(raw_results)}")
    print(f"Resolved calls            : {resolved_count}")
    print()

    print(f"KnitCode internal edges   : {len(knitcode_edges)}")
    print(f"Ground-truth internal     : {len(ground_truth_edges)}")
    print()

    print(f"TP                        : {tp}")
    print(f"FP                        : {fp}")
    print(f"FN                        : {fn}")
    print()

    print(f"Precision                 : {precision:.4f}")
    print(f"Recall                    : {recall:.4f}")
    print(f"F1                        : {f1:.4f}")

    print()
    print("=== False Positives ===")

    for caller, callee in sorted(false_positive):
        print(f"{caller} -> {callee}")

    print()
    print("=== False Negatives ===")

    for caller, callee in sorted(false_negative):
        print(f"{caller} -> {callee}")


if __name__ == "__main__":
    main()
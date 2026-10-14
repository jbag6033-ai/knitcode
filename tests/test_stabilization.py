import ast
from collections import Counter

import pytest

from analyzer.graph import CodeGraph
from analyzer.resolver import CallResolver
from analyzer.visitor import CodeVisitor


def analyze(tmp_path, files):
    for name, source in files.items():
        (tmp_path / name).write_text(source, encoding="utf-8")
    resolver = CallResolver(tmp_path)
    resolver.analyze_project()
    return resolver.resolve_calls()


def test_nested_lambda_body_is_visited_once():
    visitor = CodeVisitor()
    visitor.visit(ast.parse(
        "def outer():\n"
        "    callback = lambda: (lambda: helper())\n"
        "    after()\n"
    ))
    relationships = Counter(
        (item["caller"], item["callee"])
        for item in visitor.call_relationships
    )
    assert relationships == Counter({
        ("outer", "outer.<lambda1>"): 1,
        ("outer.<lambda1>", "outer.<lambda1>.<lambda1>"): 1,
        ("outer.<lambda1>.<lambda1>", "helper"): 1,
        ("outer", "after"): 1,
    })
    assert [item["name"] for item in visitor.functions] == [
        "outer", "outer.<lambda1>", "outer.<lambda1>.<lambda1>",
    ]


@pytest.mark.parametrize("reverse", [False, True])
def test_method_metadata_does_not_depend_on_call_order(tmp_path, reverse):
    results = analyze(tmp_path, {"service.py": (
        "class Service:\n"
        "    def run(self):\n"
        "        print('running')\n"
        "    def unused(self):\n"
        "        print('unused')\n"
        "def main():\n"
        "    service = Service()\n"
        "    service.run()\n"
    )})
    graph = CodeGraph().build_from_resolved_calls(
        list(reversed(results)) if reverse else results
    )
    for name, lineno in [("run", 2), ("unused", 4)]:
        assert graph.nodes[f"service.py::Service.{name}"] == {
            "id": f"service.py::Service.{name}",
            "name": name,
            "file": "service.py",
            "type": "method",
            "class_name": "Service",
            "lineno": lineno,
        }


@pytest.mark.parametrize("reverse", [False, True])
def test_graph_preserves_target_metadata_without_caller_definition(tmp_path, reverse):
    results = analyze(tmp_path, {"service.py": (
        "class Service:\n"
        "    def run(self):\n"
        "        print('running')\n"
        "def main():\n"
        "    service = Service()\n"
        "    service.run()\n"
    )})
    for result in results:
        result.pop("caller_definition")
    ordered = list(reversed(results)) if reverse else results
    graph = CodeGraph().build_from_resolved_calls(iter(ordered))
    node = graph.nodes["service.py::Service.run"]
    assert (node["type"], node["name"], node["class_name"], node["lineno"]) == (
        "method", "run", "Service", 2,
    )


@pytest.mark.parametrize("class_name, target_name, target_type", [
    ("Own", "__init__", "method"),
    ("Inherited", "__init__", "method"),
    ("Empty", "Empty", "class"),
])
def test_local_and_imported_constructors_agree(
    tmp_path, class_name, target_name, target_type,
):
    results = analyze(tmp_path, {
        "classes.py": (
            "class Own:\n"
            "    def __init__(self):\n"
            "        pass\n"
            "class Inherited(Own):\n"
            "    pass\n"
            "class Empty:\n"
            "    pass\n"
            f"def local():\n    {class_name}()\n"
        ),
        "main.py": (
            f"from classes import {class_name} as Imported\n"
            "def main():\n    Imported()\n"
        ),
    })
    constructor_calls = [
        result for result in results
        if result["caller"] in {"local", "main"}
    ]
    assert len(constructor_calls) == 2
    local, imported = constructor_calls
    assert local["target"] == imported["target"]
    assert local["target"]["name"] == target_name
    assert local["target"]["type"] == target_type
    if target_type == "method":
        assert local["target"]["class"] == "Own"
    graph = CodeGraph().build_from_resolved_calls(results)
    assert {edge["type"] for edge in graph.edges} == {
        "calls" if target_type == "method" else "instantiates"
    }

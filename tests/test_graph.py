from analyzer.graph import CodeGraph
from analyzer.resolver import CallResolver


def test_build_call_graph():
    resolver = CallResolver("tests/fixtures/toy_project")
    resolver.analyze_project()

    graph = CodeGraph()
    graph.build_from_resolved_calls(resolver.resolve_calls())

    data = graph.to_dict()

    node_ids = {node["id"] for node in data["nodes"]}

    edges = {
        (edge["source"], edge["target"])
        for edge in data["edges"]
    }

    assert "main.py::main" in node_ids
    assert "service.py::create_order" in node_ids
    assert "payment.py::calculate_price" in node_ids
    assert "database.py::save_order" in node_ids

    assert (
        "main.py::main",
        "service.py::create_order",
    ) in edges

    assert (
        "service.py::create_order",
        "payment.py::calculate_price",
    ) in edges

    assert (
        "service.py::create_order",
        "database.py::save_order",
    ) in edges

from analyzer.resolver import CallResolver


def test_resolve_project_calls():
    resolver = CallResolver("tests/fixtures/toy_project")

    resolver.analyze_project()
    results = resolver.resolve_calls()

    resolved_edges = {
        (
            result["caller_file"],
            result["caller"],
            result["target"]["file"],
            result["target"]["name"],
        )
        for result in results
        if result["target"] is not None
    }

    assert (
        "main.py",
        "main",
        "service.py",
        "create_order",
    ) in resolved_edges

    assert (
        "service.py",
        "create_order",
        "payment.py",
        "calculate_price",
    ) in resolved_edges

    assert (
        "service.py",
        "create_order",
        "database.py",
        "save_order",
    ) in resolved_edges

from analyzer.parser import parse_file
from analyzer.visitor import CodeVisitor


def test_extract_functions_and_calls():
    tree = parse_file("tests/fixtures/toy_project/main.py")

    visitor = CodeVisitor()
    visitor.visit(tree)

    function_names = [function["name"] for function in visitor.functions]
    call_names = [call["name"] for call in visitor.calls]

    assert "main" in function_names
    assert "create_order" in call_names
    assert "main" in call_names


def test_extract_imports():
    tree = parse_file("tests/fixtures/toy_project/main.py")

    visitor = CodeVisitor()
    visitor.visit(tree)

    assert any(
        imported["module"] == "service"
        and imported["name"] == "create_order"
        for imported in visitor.imports
    )

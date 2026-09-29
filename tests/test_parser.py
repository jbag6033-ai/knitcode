import ast

from analyzer.parser import parse_file


def test_parse_main_file():
    tree = parse_file("tests/fixtures/toy_project/main.py")

    assert isinstance(tree, ast.Module)

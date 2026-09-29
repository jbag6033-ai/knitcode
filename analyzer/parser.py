"""Parse Python source files using the ast module."""


import ast
from pathlib import Path


def parse_file(file_path: str | Path) -> ast.AST:
    """
    Python 파일을 읽고 AST(Abstract Syntax Tree)로 변환한다.

    Args:
        file_path: 분석할 Python 파일의 경로

    Returns:
        파싱된 AST 객체
    """

    file_path = Path(file_path)

    # Python 파일인지 확인
    if file_path.suffix != ".py":
        raise ValueError(f"Python 파일이 아닙니다: {file_path}")

    # 파일 존재 여부 확인
    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    # 소스 코드 읽기
    source_code = file_path.read_text(encoding="utf-8")

    # Python 코드 → AST
    tree = ast.parse(
        source_code,
        filename=str(file_path),
    )

    return tree
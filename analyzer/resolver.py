"""Resolve discovered calls to their likely definitions."""

from pathlib import Path

from analyzer.parser import parse_file
from analyzer.visitor import CodeVisitor


class CallResolver:
    def __init__(self, project_root):
        self.project_root = Path(project_root)

        # 함수 이름 -> 함수 정의 정보
        self.function_definitions = {}

        # 파일별 visitor 분석 결과
        self.file_results = {}

    def analyze_project(self):
        """Analyze every Python file in the project."""

        for file_path in sorted(self.project_root.rglob("*.py")):
            tree = parse_file(file_path)

            visitor = CodeVisitor()
            visitor.visit(tree)

            relative_path = file_path.relative_to(self.project_root)

            self.file_results[str(relative_path)] = visitor

            for function in visitor.functions:
                name = function["name"]

                definition = {
                    "name": name,
                    "file": str(relative_path),
                    "lineno": function["lineno"],
                    "class": function["class"],
                }

                self.function_definitions.setdefault(name, []).append(
                    definition
                )

    def resolve_calls(self):
        """Resolve discovered calls to likely function definitions."""

        resolved = []

        for file_name, visitor in self.file_results.items():
            for relationship in visitor.call_relationships:
                caller = relationship["caller"]
                callee = relationship["callee"]

                target = self._resolve_callee(
                    file_name,
                    caller,
                    callee,
                    visitor,
                )

                resolved.append({
                    "caller_file": file_name,
                    "caller": caller,
                    "callee": callee,
                    "target": target,
                    "lineno": relationship["lineno"],
                })

        return resolved

    def _resolve_callee(self, current_file, caller, callee, visitor):
        """Resolve one callee using imports, instances, and definitions."""

        # ---------------------------------------------------------
        # 0. self.method()
        # ---------------------------------------------------------

        if callee.startswith("self."):
            method_name = callee.split(".", 1)[1]

            if "." in caller:
                class_name = caller.split(".", 1)[0]

                for definition in self.function_definitions.get(
                    method_name, []
                ):
                    if (
                        definition["file"] == current_file
                        and definition["class"] == class_name
                    ):
                        return definition

        # ---------------------------------------------------------
        # 1. instance.method()
        # ---------------------------------------------------------
        #
        # Example:
        #
        # service = OrderService()
        # service.create_order()
        #
        # visitor.instances:
        #
        # {
        #     "service": "OrderService"
        # }
        #

        if "." in callee:
            prefix, method_name = callee.split(".", 1)

            if prefix in visitor.instances:
                class_name = visitor.instances[prefix]

                for definition in self.function_definitions.get(
                    method_name, []
                ):
                    if definition["class"] == class_name:
                        return definition

        # ---------------------------------------------------------
        # 2. module.function()
        # ---------------------------------------------------------
        #
        # import payment
        # payment.calculate_price()
        #
        # import database as db
        # db.save_order()
        #

        if "." in callee:
            prefix, function_name = callee.split(".", 1)

            for imported in visitor.imports:
                if imported["type"] != "import":
                    continue

                visible_name = imported["alias"] or imported["module"]

                if visible_name != prefix:
                    continue

                module = imported["module"]
                expected_file = module.replace(".", "/") + ".py"

                for definition in self.function_definitions.get(
                    function_name, []
                ):
                    if definition["file"] == expected_file:
                        return definition

        # ---------------------------------------------------------
        # 3. from module import function
        # ---------------------------------------------------------

        for imported in visitor.imports:
            if imported["type"] != "from":
                continue

            visible_name = imported["alias"] or imported["name"]

            if visible_name != callee:
                continue

            module = imported["module"]
            function_name = imported["name"]

            expected_file = module.replace(".", "/") + ".py"

            for definition in self.function_definitions.get(
                function_name, []
            ):
                if definition["file"] == expected_file:
                    return definition

        # ---------------------------------------------------------
        # 4. Function defined in the same file
        # ---------------------------------------------------------

        for definition in self.function_definitions.get(callee, []):
            if (
                definition["file"] == current_file
                and definition["class"] is None
            ):
                return definition

        # ---------------------------------------------------------
        # 5. Unique function name in project
        # ---------------------------------------------------------

        candidates = self.function_definitions.get(callee, [])

        if len(candidates) == 1:
            return candidates[0]

        return None
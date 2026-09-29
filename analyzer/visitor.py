"""AST visitors for extracting functions, classes, imports, calls, and instances."""

import ast


class CodeVisitor(ast.NodeVisitor):
    def __init__(self):
        self.functions = []
        self.classes = []
        self.imports = []
        self.calls = []
        self.call_relationships = []

        # variable name -> class name
        #
        # Example:
        #   service = OrderService()
        #
        # becomes:
        #   {"service": "OrderService"}
        self.instances = {}

        # 현재 탐색 중인 함수/클래스를 추적
        self.current_function = None
        self.current_class = None

    def visit_FunctionDef(self, node):
        function_info = {
            "name": node.name,
            "class": self.current_class,
            "lineno": node.lineno,
        }
        self.functions.append(function_info)

        previous_function = self.current_function
        self.current_function = node.name

        self.generic_visit(node)

        self.current_function = previous_function

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node):
        class_info = {
            "name": node.name,
            "lineno": node.lineno,
        }
        self.classes.append(class_info)

        previous_class = self.current_class
        self.current_class = node.name

        self.generic_visit(node)

        self.current_class = previous_class

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append({
                "type": "import",
                "module": alias.name,
                "name": None,
                "alias": alias.asname,
                "lineno": node.lineno,
            })

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.imports.append({
                "type": "from",
                "module": node.module,
                "name": alias.name,
                "alias": alias.asname,
                "lineno": node.lineno,
            })

    def visit_Assign(self, node):
        """
        Track simple class instance assignments.

        Example:

            service = OrderService()

        becomes:

            service -> OrderService
        """

        if isinstance(node.value, ast.Call):
            class_name = self._get_call_name(node.value.func)

            if class_name:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.instances[target.id] = class_name

        self.generic_visit(node)

    def visit_Call(self, node):
        called_name = self._get_call_name(node.func)

        if called_name:
            self.calls.append({
                "name": called_name,
                "lineno": node.lineno,
            })

            caller = self.current_function or "<module>"

            if self.current_class and self.current_function:
                caller = f"{self.current_class}.{self.current_function}"

            self.call_relationships.append({
                "caller": caller,
                "callee": called_name,
                "lineno": node.lineno,
            })

        self.generic_visit(node)

    def _get_call_name(self, node):
        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            prefix = self._get_call_name(node.value)

            if prefix:
                return f"{prefix}.{node.attr}"

            return node.attr

        return None
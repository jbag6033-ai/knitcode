"""Resolve discovered calls to their likely definitions."""

from pathlib import Path

from analyzer.parser import parse_file
from analyzer.visitor import CodeVisitor


class CallResolver:
    def __init__(self, project_root):
        self.project_root = Path(project_root)

        self.function_definitions = {}
        self.class_definitions = {}
        self.file_results = {}
        self.class_bases = {}

    def analyze_project(self):
        """Analyze every Python file in the project."""

        for file_path in sorted(self.project_root.rglob("*.py")):
            tree = parse_file(file_path)

            visitor = CodeVisitor()
            visitor.visit(tree)

            relative_path = file_path.relative_to(self.project_root)
            relative_path_str = str(relative_path)

            self.file_results[relative_path_str] = visitor

            # Functions and methods
            for function in visitor.functions:
                name = function["name"]

                definition = {
                    "type": (
                        "method"
                        if function["class"] is not None
                        else "function"
                    ),
                    "name": name,
                    "file": relative_path_str,
                    "lineno": function["lineno"],
                    "class": function["class"],
                }

                self.function_definitions.setdefault(
                    name, []
                ).append(definition)

            # Classes
            for class_info in visitor.classes:
                name = class_info["name"]

                definition = {
                    "type": "class",
                    "name": name,
                    "file": relative_path_str,
                    "lineno": class_info["lineno"],
                    "class": None,
                }

                self.class_definitions.setdefault(
                    name, []
                ).append(definition)
                
                self.class_bases[
                    (relative_path_str, name)
                ] = class_info.get("bases", [])

    def resolve_calls(self):
        """Resolve discovered calls to likely definitions."""

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
    
    def _resolve_method_in_hierarchy(
        self,
        current_file,
        class_name,
        method_name,
        visited=None,
    ):
        """
        Resolve a method by searching the current class and
        then recursively searching its base classes.
        """

        if visited is None:
            visited = set()

        key = (current_file, class_name)

        if key in visited:
            return None

        visited.add(key)

        # 1. Search the current class first.
        for definition in self.function_definitions.get(
            method_name, []
        ):
            if (
                definition["file"] == current_file
                and definition["class"] == class_name
            ):
                return definition

        # 2. Search base classes.
        for base_name in self.class_bases.get(key, []):
            # Ignore the module prefix when the base is written
            # as something like package.Parent.
            simple_base_name = base_name.split(".")[-1]

            # Only follow base classes that belong to this project/file.
            if (
                current_file,
                simple_base_name,
            ) not in self.class_bases:
                continue

            definition = self._resolve_method_in_hierarchy(
                current_file,
                simple_base_name,
                method_name,
                visited,
            )

            if definition is not None:
                return definition

        return None

    def _resolve_callee(self, current_file, caller, callee, visitor):
        """Resolve one callee."""
        
        # ---------------------------------------------------------
        # -1. super().method()
        # ---------------------------------------------------------

        if callee.startswith("super."):
            method_name = callee.split(".", 1)[1]

            if "." in caller:
                class_name = caller.split(".", 1)[0]

                key = (current_file, class_name)

                for base_name in self.class_bases.get(key, []):
                    simple_base_name = base_name.split(".")[-1]

                    definition = self._resolve_method_in_hierarchy(
                        current_file,
                        simple_base_name,
                        method_name,
                    )

                    if definition is not None:
                        return definition

        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # -0.5. ClassName.method()
        # ---------------------------------------------------------

        if "." in callee:
            class_name, method_name = callee.split(".", 1)

            if (
                current_file,
                class_name,
            ) in self.class_bases:
                definition = self._resolve_method_in_hierarchy(
                    current_file,
                    class_name,
                    method_name,
                )

                if definition is not None:
                    return definition
        
        
        # 0. self.method()
        # ---------------------------------------------------------

        if callee.startswith("self."):
            method_name = callee.split(".", 1)[1]

            if "." in caller:
                class_name = caller.split(".", 1)[0]

                definition = self._resolve_method_in_hierarchy(
                    current_file,
                    class_name,
                    method_name,
                )

                if definition is not None:
                    return definition

        # ---------------------------------------------------------
        # 1. instance.method()
        # ---------------------------------------------------------

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
        # ---------------------------------------------------------
        # 2. module.function()
        # ---------------------------------------------------------

        if "." in callee:
            prefix, function_name = callee.split(".", 1)

            for imported in visitor.imports:
                # -------------------------------------------------
                # import module
                #
                # Example:
                #     import payment
                #     payment.calculate()
                # -------------------------------------------------

                if imported["type"] == "import":
                    visible_name = (
                        imported["alias"] or imported["module"]
                    )

                    if visible_name != prefix:
                        continue

                    expected_file = (
                        imported["module"].replace(".", "/") + ".py"
                    )

                    for definition in self.function_definitions.get(
                        function_name, []
                    ):
                        if definition["file"] == expected_file:
                            return definition

                # -------------------------------------------------
                # from package import module
                #
                # Example:
                #     from subbrute import subbrute
                #     subbrute.print_target()
                #
                # resolves to:
                #     subbrute/subbrute.py
                # -------------------------------------------------

                elif imported["type"] == "from":
                    visible_name = (
                        imported["alias"] or imported["name"]
                    )

                    if visible_name != prefix:
                        continue

                    module = imported["module"]
                    imported_name = imported["name"]

                    expected_file = (
                        f"{module}.{imported_name}"
                        .replace(".", "/")
                        + ".py"
                    )

                    for definition in self.function_definitions.get(
                        function_name, []
                    ):
                        if definition["file"] == expected_file:
                            return definition

        # ---------------------------------------------------------
        # 3. Class constructor
        #
        # from service import OrderService
        # service = OrderService()
        # ---------------------------------------------------------

        for imported in visitor.imports:
            if imported["type"] != "from":
                continue

            visible_name = imported["alias"] or imported["name"]

            if visible_name != callee:
                continue

            module = imported["module"]
            imported_name = imported["name"]

            expected_file = module.replace(".", "/") + ".py"

            for definition in self.class_definitions.get(
                imported_name, []
            ):
                if definition["file"] == expected_file:
                    return definition

        # ---------------------------------------------------------
        # 4. from module import function
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
        # ---------------------------------------------------------
        # 4.5. Class defined in the same file
        # ---------------------------------------------------------

        for class_definition in self.class_definitions.get(callee, []):
            if class_definition["file"] != current_file:
                continue

            # A call to ClassName() executes ClassName.__init__().
            for method_definition in self.function_definitions.get(
                "__init__", []
            ):
                if (
                    method_definition["file"] == current_file
                    and method_definition["class"] == callee
                ):
                    return method_definition

            # The class exists, but it does not define __init__ itself.
            # Search its inheritance hierarchy.
            definition = self._resolve_method_in_hierarchy(
                current_file,
                callee,
                "__init__",
            )

            if definition is not None:
                return definition
        # 5. Function defined in same file
        # ---------------------------------------------------------

        for definition in self.function_definitions.get(callee, []):
            if (
                definition["file"] == current_file
                and definition["class"] is None
            ):
                return definition

        # ---------------------------------------------------------
        # 6. Unique function
        # ---------------------------------------------------------

        candidates = self.function_definitions.get(callee, [])

        if len(candidates) == 1:
            return candidates[0]

        return None
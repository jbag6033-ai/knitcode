"""Resolve discovered calls to their likely definitions."""

import ast
from pathlib import Path

from analyzer.parser import parse_file
from analyzer.visitor import CodeVisitor


class CallResolver:
    def __init__(self, project_root, *, entrypoints=None):
        self.project_root = Path(project_root)
        self.entrypoints = entrypoints

        self.function_definitions = {}
        self.class_definitions = {}
        self.file_results = {}
        self.class_bases = {}

    def analyze_project(self, file_paths=None):
        """Analyze every Python file in the project."""

        for file_path in sorted(self.project_root.rglob("*.py") if file_paths is None else file_paths):
            tree = parse_file(file_path)

            visitor = CodeVisitor()
            visitor.visit(tree)

            relative_path = file_path.relative_to(self.project_root)
            relative_path_str = str(relative_path)

            # Convert relative imports to module paths within the analysis root.
            for imported in visitor.imports:
                if imported.get("level", 0):
                    parent = list(relative_path.parent.parts)
                    ascend = imported["level"] - 1
                    if ascend > len(parent):
                        imported["module"] = "<outside-root>"
                    else:
                        parent = parent[:len(parent) - ascend]
                        imported["module"] = ".".join(
                            parent + (imported["module"] or "").split(".")
                        ).strip(".")

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
                    "caller_definition": self._find_caller_definition(
                        file_name, caller, visitor,
                    ),
                    "callee": callee,
                    "target": target,
                    "lineno": relationship["lineno"],
                })

        from analyzer.value_flow import ValueFlow

        flow = ValueFlow(self)
        flow_targets = flow.analyze()
        self.value_flow_status = {"iterations": flow.iterations, "converged": flow.converged}
        self.value_flow_cache = flow.cache_info()
        for (file_name, caller, lineno), targets in flow_targets.items():
            existing = {
                (result["target"]["file"], result["target"].get("class"), result["target"]["name"])
                for result in resolved if result["caller_file"] == file_name
                and result["caller"] == caller and result["lineno"] == lineno
                and result["target"] is not None
            }
            for identity, target in targets.items():
                if identity not in existing:
                    resolved.append({
                        "caller_file": file_name, "caller": caller,
                        "caller_definition": self._find_caller_definition(file_name, caller, self.file_results[file_name]),
                        "callee": target["name"], "target": target, "lineno": lineno,
                        "resolution": "value_flow",
                    })

        return resolved

    def _find_caller_definition(self, file_name, caller, visitor):
        """Return definition metadata without inferring types from dotted names."""
        for function in visitor.functions:
            class_name = function["class"]
            qualified_name = function["name"]
            if class_name is not None:
                qualified_name = f"{class_name}.{qualified_name}"
            if qualified_name == caller:
                return {
                    "type": "method" if class_name is not None else "function",
                    "name": function["name"],
                    "file": file_name,
                    "lineno": function["lineno"],
                    "class": class_name,
                }
        return None

    def _resolve_constructor(self, class_definition):
        """Prefer a project-defined initializer, otherwise keep the class target."""
        initializer = self._resolve_method_in_hierarchy(
            class_definition["file"], class_definition["name"], "__init__",
        )
        return initializer if initializer is not None else class_definition

    def _module_files(self, module):
        module = module or ""
        prefix = self.project_root.name + "."
        if (self.project_root / "__init__.py").exists():
            if module == self.project_root.name:
                module = ""
            elif module.startswith(prefix):
                module = module[len(prefix):]
        path = module.replace(".", "/")
        return [path + ".py", path + "/__init__.py"] if path else ["__init__.py"]

    def _imported_definition(self, module, name, kind, visited=None):
        visited = set() if visited is None else visited
        key = (module, name, kind)
        if key in visited:
            return None
        visited.add(key)
        files = self._module_files(module)
        definitions = self.class_definitions if kind == "class" else self.function_definitions
        for definition in definitions.get(name, []):
            if definition["file"] in files:
                return definition
        for file in files:
            visitor = self.file_results.get(file)
            if visitor is None:
                continue
            for imported in visitor.imports:
                if imported["type"] == "from" and (imported["alias"] or imported["name"]) == name:
                    definition = self._imported_definition(
                        imported["module"], imported["name"], kind, visited,
                    )
                    if definition is not None:
                        return definition
        return None

    def _class_reference(self, file, name):
        for definition in self.class_definitions.get(name, []):
            if definition["file"] == file:
                return definition
        visitor = self.file_results[file]
        for imported in visitor.imports:
            visible = imported["alias"] or imported["name"] or imported["module"]
            if imported["type"] == "from" and visible == name:
                return self._imported_definition(imported["module"], imported["name"], "class")
            if imported["type"] == "from" and name.startswith(visible + "."):
                suffix = name[len(visible) + 1:]
                outer = self._imported_definition(imported["module"], imported["name"], "class")
                if outer:
                    for nested in self.class_definitions.get(outer['name'] + '.' + suffix, []):
                        if nested['file'] == outer['file']:
                            return nested
                module = '.'.join(filter(None, [imported['module'], imported['name']]))
                definition = self._imported_definition(module, suffix, 'class')
                if definition:
                    return definition
            if imported["type"] == "import" and name.startswith(visible + "."):
                return self._imported_definition(imported["module"], name[len(visible) + 1:], "class")
        return None
    
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
            base = self._class_reference(current_file, base_name)
            if base is None:
                continue

            definition = self._resolve_method_in_hierarchy(
                base["file"],
                base["name"],
                method_name,
                visited,
            )

            if definition is not None:
                return definition

        return None

    def _resolve_callee(self, current_file, caller, callee, visitor):
        """Resolve one callee."""
        caller_definition = self._find_caller_definition(current_file, caller, visitor)
        caller_class = caller_definition["class"] if caller_definition else None
        # Inline callbacks carry a synthetic function name, not an attribute
        # access. Match the AST lambda in its exact enclosing method/class.
        if caller_class and callee.rpartition('.')[0] == caller_definition['name']:
            qualified = f'{caller_class}.{callee}'
            if isinstance(visitor.function_nodes.get(qualified), ast.Lambda):
                for definition in self.function_definitions.get(callee, []):
                    if definition['file'] == current_file and definition['class'] == caller_class:
                        return definition
        # Resolve local functions from the innermost enclosing function out.
        # Never bind a bare name to a nested function in an unrelated scope.
        if "." not in callee:
            scope = caller_definition["name"] if caller_definition else ""
            while scope:
                name = f"{scope}.{callee}"
                for definition in self.function_definitions.get(name, []):
                    if definition["file"] == current_file and definition["class"] == caller_class:
                        return definition
                scope = scope.rpartition(".")[0]
        
        # ---------------------------------------------------------
        # -1. super().method()
        # ---------------------------------------------------------

        if callee.startswith("super."):
            method_name = callee.split(".", 1)[1]

            if caller_class is not None:
                class_name = caller_class

                key = (current_file, class_name)

                for base_name in self.class_bases.get(key, []):
                    base = self._class_reference(current_file, base_name)
                    if base is None:
                        continue

                    definition = self._resolve_method_in_hierarchy(
                        base["file"],
                        base["name"],
                        method_name,
                    )

                    if definition is not None:
                        return definition

        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # -0.5. ClassName.method()
        # ---------------------------------------------------------

        if "." in callee:
            class_name, method_name = callee.rsplit(".", 1)

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

            if caller_class is not None:
                class_name = caller_class
                nested_class = f"{class_name}.{method_name}"
                for definition in self.class_definitions.get(nested_class, []):
                    if definition["file"] == current_file:
                        return self._resolve_constructor(definition)

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

                    if not callee.startswith(visible_name + "."):
                        continue

                    # Preserve the complete module path, including aliased
                    # dotted imports and calls through imported subpackages.
                    suffix = callee[len(visible_name) + 1:]
                    submodule, _, name = suffix.rpartition('.')
                    module = '.'.join(filter(None, [imported['module'], submodule]))
                    definition = self._imported_definition(module, name, 'function')
                    if definition is not None and definition['class'] is None:
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

                    expected_files = self._module_files(".".join(filter(None, [module, imported_name])))

                    for definition in self.function_definitions.get(
                        function_name, []
                    ):
                        if definition["file"] in expected_files:
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

            definition = self._imported_definition(module, imported_name, "class")
            if definition is not None:
                return self._resolve_constructor(definition)

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

            definition = self._imported_definition(module, function_name, "function")
            if definition is not None:
                return definition

        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # 4.5. Class defined in the same file
        # ---------------------------------------------------------

        for class_definition in self.class_definitions.get(callee, []):
            if class_definition["file"] != current_file:
                continue

            return self._resolve_constructor(class_definition)
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

        if len(candidates) == 1 and candidates[0]["class"] is None:
            return candidates[0]

        return None

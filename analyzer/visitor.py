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
        
        # collection variable -> possible class/function names
        self.collections = {}

        # loop variable -> possible class/function names
        self.loop_bindings = {}
        
        # function name -> number of lambdas encountered
        self.lambda_count = {}

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
        """
        Record a class definition and its base classes.

        Example:

            class GoogleEnum(enumratorBaseThreaded):

        becomes:

            {
                "name": "GoogleEnum",
                "bases": ["enumratorBaseThreaded"],
                "lineno": ...
            }
        """

        bases = []

        for base in node.bases:
            base_name = self._get_call_name(base)

            if base_name:
                bases.append(base_name)

        class_info = {
            "name": node.name,
            "bases": bases,
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
        
        # Track lists of callable names.
        #
        # Example:
        #     chosenEnums = [GoogleEnum, YahooEnum]
        #
        # becomes:
        #     chosenEnums -> ["GoogleEnum", "YahooEnum"]

        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
            names = []

            for element in node.value.elts:
                name = self._get_call_name(element)

                if name:
                    names.append(name)

            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.collections[target.id] = names
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
        # Resolve indirect calls through loop variables.
        #
        # Example:
        #     chosenEnums = [GoogleEnum, YahooEnum]
        #     [enum(...) for enum in chosenEnums]
        #
        # produces calls to:
        #     GoogleEnum
        #     YahooEnum

        if called_name in self.loop_bindings:
            caller = self.current_function or "<module>"

            if self.current_class and self.current_function:
                caller = f"{self.current_class}.{self.current_function}"

            for possible_callee in self.loop_bindings[called_name]:
                self.calls.append({
                    "name": possible_callee,
                    "lineno": node.lineno,
                })

                self.call_relationships.append({
                    "caller": caller,
                    "callee": possible_callee,
                    "lineno": node.lineno,
                })

            # Do not also record the unresolved loop variable itself.
            self.generic_visit(node)
            return

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

        # Handle calls used as part of another call expression.
        #
        # Example:
        #     super(GoogleEnum, self).__init__()
        #
        # The inner:
        #     super(GoogleEnum, self)
        #
        # is represented as ast.Call.
        if isinstance(node, ast.Call):
            return self._get_call_name(node.func)

        return None
    
    def visit_For(self, node):
        """
        Track loop variables iterating over known collections.

        Example:

            for enum in chosenEnums:
                enum()

        enum can refer to every callable stored in chosenEnums.
        """

        if (
            isinstance(node.target, ast.Name)
            and isinstance(node.iter, ast.Name)
            and node.iter.id in self.collections
        ):
            variable_name = node.target.id

            previous = self.loop_bindings.get(variable_name)

            self.loop_bindings[variable_name] = list(
                self.collections[node.iter.id]
            )

            self.generic_visit(node)

            if previous is None:
                self.loop_bindings.pop(variable_name, None)
            else:
                self.loop_bindings[variable_name] = previous

            return

        self.generic_visit(node)
        
    def visit_ListComp(self, node):
        """
        Track loop variables inside list comprehensions.

        Example:

            [enum(...) for enum in chosenEnums]
        """

        saved_bindings = {}

        for generator in node.generators:
            if (
                isinstance(generator.target, ast.Name)
                and isinstance(generator.iter, ast.Name)
                and generator.iter.id in self.collections
            ):
                variable_name = generator.target.id

                saved_bindings[variable_name] = (
                    self.loop_bindings.get(variable_name)
                )

                self.loop_bindings[variable_name] = list(
                    self.collections[generator.iter.id]
                )

        self.generic_visit(node)

        for variable_name, previous in saved_bindings.items():
            if previous is None:
                self.loop_bindings.pop(variable_name, None)
            else:
                self.loop_bindings[variable_name] = previous
                
                
    def visit_Lambda(self, node):
        """
        Record a lambda expression as a nested anonymous function.

        Example:

            def extract_subdomains():
                sorted(items, key=lambda x: x)

        becomes:

            extract_subdomains
                -> extract_subdomains.<lambda1>
        """

        parent_function = self.current_function or "<module>"

        count = self.lambda_count.get(parent_function, 0) + 1
        self.lambda_count[parent_function] = count

        lambda_name = f"<lambda{count}>"

        # Lambda is nested inside its enclosing function.
        if parent_function != "<module>":
            qualified_lambda_name = (
                f"{parent_function}.{lambda_name}"
            )
        else:
            qualified_lambda_name = lambda_name

        # Register the lambda as a function.
        self.functions.append({
            "name": qualified_lambda_name,
            "class": self.current_class,
            "lineno": node.lineno,
        })

        # Register enclosing function -> lambda.
        caller = parent_function

        if self.current_class and self.current_function:
            caller = f"{self.current_class}.{self.current_function}"

        self.call_relationships.append({
            "caller": caller,
            "callee": qualified_lambda_name,
            "lineno": node.lineno,
        })

        self.calls.append({
            "name": qualified_lambda_name,
            "lineno": node.lineno,
        })

        # Calls inside the lambda belong to the lambda itself.
        previous_function = self.current_function
        self.current_function = qualified_lambda_name

        self.generic_visit(node)

        self.current_function = previous_function

            # Register the enclosing function -> lambda relationship.
        caller = parent_function

        if self.current_class and self.current_function:
            caller = f"{self.current_class}.{self.current_function}"

        self.call_relationships.append({
            "caller": caller,
            "callee": lambda_name,
            "lineno": node.lineno,
        })

        self.calls.append({
            "name": lambda_name,
            "lineno": node.lineno,
        })

        # Analyze calls inside the lambda body as belonging to the lambda.
        previous_function = self.current_function
        self.current_function = lambda_name

        self.generic_visit(node)

        self.current_function = previous_function
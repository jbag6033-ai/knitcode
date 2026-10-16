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
        self.callable_aliases = {}
        self.function_nodes = {}
        self.assignments = []
        self.return_expressions = {}
        self.call_nodes = []
        self.attribute_nodes = []
        self.with_items = []
        self.iterations = []
        self.inline_callbacks = set()
        self.conditional_values = set()
        self.conditional_calls = set()
        self.branch_guards = []
        self.call_guards = {}
        self.conditional_depth = 0
        self.attribute_guards = set()
        self.guarded_getattrs = set()

        # 현재 탐색 중인 함수/클래스를 추적
        self.current_function = None
        self.current_class = None

    def visit_FunctionDef(self, node):
        qualified_name = node.name
        if self.current_function is not None:
            qualified_name = f"{self.current_function}.{node.name}"
        function_info = {
            "name": qualified_name,
            "class": self.current_class,
            "lineno": node.lineno,
        }
        self.functions.append(function_info)

        previous_function = self.current_function
        previous_aliases = self.callable_aliases
        self.callable_aliases = dict(previous_aliases)
        for argument in (
            node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        ):
            self.callable_aliases.pop(argument.arg, None)
        for argument in (node.args.vararg, node.args.kwarg):
            if argument is not None:
                self.callable_aliases.pop(argument.arg, None)
        self.current_function = qualified_name
        self.function_nodes[self._caller_name()] = node

        self.generic_visit(node)

        self.current_function = previous_function
        self.callable_aliases = previous_aliases

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

        qualified_class = node.name
        if self.current_class is not None:
            qualified_class = f"{self.current_class}.{node.name}"
        class_info = {
            "name": qualified_class,
            "bases": bases,
            "lineno": node.lineno,
        }

        self.classes.append(class_info)

        previous_class = self.current_class
        previous_function = self.current_function
        self.current_class = qualified_class
        self.current_function = None

        self.generic_visit(node)

        self.current_class = previous_class
        self.current_function = previous_function

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
                "level": node.level,
                "name": alias.name,
                "alias": alias.asname,
                "lineno": node.lineno,
            })

    def visit_Assign(self, node):
        self.assignments.append((self._caller_name(), node.targets, node.value, node.lineno))
        if self.conditional_depth:
            self.conditional_values.add(id(node.value))
        alias = None
        if isinstance(node.value, (ast.Name, ast.Attribute)):
            alias = self._get_call_name(node.value)
            if alias:
                alias = self.callable_aliases.get(alias, alias)
        elif isinstance(node.value, ast.Call) and self._get_call_name(node.value.func) == "super":
            alias = "super"
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.callable_aliases.pop(target.id, None)
                if alias is not None:
                    self.callable_aliases[target.id] = alias
        
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

    def visit_With(self, node):
        for item in node.items:
            self.with_items.append((self._caller_name(), item.context_expr))
            if item.optional_vars is not None:
                entered = ast.Call(func=ast.Attribute(value=item.context_expr, attr='__enter__', ctx=ast.Load()),
                                   args=[], keywords=[])
                ast.copy_location(entered, item.context_expr)
                ast.fix_missing_locations(entered)
                self.assignments.append((self._caller_name(), [item.optional_vars], entered,
                                         item.context_expr.lineno))
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Load):
            self.attribute_nodes.append((self._caller_name(), node))
        self.generic_visit(node)

    def visit_Call(self, node):
        self.call_nodes.append((self._caller_name(), node))
        self.call_guards[id(node)] = tuple(self.branch_guards)
        if self.conditional_depth:
            self.conditional_calls.add(id(node))
        called_name = self._get_call_name(node.func)
        if called_name in {"sorted", "min", "max", "map", "filter"}:
            for argument in node.args + [keyword.value for keyword in node.keywords]:
                if isinstance(argument, ast.Lambda):
                    self.inline_callbacks.add(id(argument))
        if called_name:
            prefix, separator, suffix = called_name.partition(".")
            if prefix in self.callable_aliases:
                called_name = self.callable_aliases[prefix] + (separator + suffix if separator else "")
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
        self.iterations.append((self._caller_name(), node.target, node.iter))
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
            self.iterations.append((self._caller_name(), generator.target, generator.iter))

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
                
                
    visit_SetComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

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

        # Defining a lambda does not call it. Inline callbacks to known
        # builtins retain a possible invocation edge; aliases are resolved
        # at their actual call sites by value flow.
        if id(node) in self.inline_callbacks:
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
        self.function_nodes[self._caller_name()] = node
        self.return_expressions[self._caller_name()] = [node.body]

        self.generic_visit(node)

        self.current_function = previous_function

    def _caller_name(self):
        name = self.current_function or "<module>"
        return f"{self.current_class}.{name}" if self.current_class and self.current_function else name

    def visit_Return(self, node):
        if node.value is not None:
            self.return_expressions.setdefault(self._caller_name(), []).append(node.value)
        self.generic_visit(node)

    def visit_If(self, node):
        self.visit(node.test)
        self.conditional_depth += 1
        for statements, expected in ((node.body, True), (node.orelse, False)):
            self.branch_guards.append((node.test, expected))
            for statement in statements:
                self.visit(statement)
            self.branch_guards.pop()
        self.conditional_depth -= 1

    def visit_Try(self, node):
        handles_attribute_error = any(
            isinstance(handler.type, ast.Name) and handler.type.id == "AttributeError"
            for handler in node.handlers
        )
        if handles_attribute_error:
            for statement in node.body:
                if isinstance(statement, (ast.Assign, ast.Return, ast.Expr)) and statement.value is not None:
                    for expression in ast.walk(statement.value):
                        if (isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name)
                                and expression.func.id == 'getattr'):
                            self.guarded_getattrs.add(id(expression))
                if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Attribute):
                    attribute = statement.value
                    if isinstance(attribute.value, ast.Name):
                        self.attribute_guards.add((self._caller_name(), attribute.value.id, attribute.attr))
        self.generic_visit(node)

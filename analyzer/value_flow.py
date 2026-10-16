"""Bounded inference of project-local return values, attributes and call arguments.

Values represent local functions/classes/instances; external and scalar values
remain unknown. This supplements name resolution without executing project code.
"""

import ast
import hashlib
from functools import lru_cache
from collections import defaultdict


class ValueFlow:
    def __init__(self, resolver, *, cache_static=True):
        self.resolver = resolver
        self.inputs = defaultdict(lambda: defaultdict(set))
        self.containers = defaultdict(set)
        self.entries = defaultdict(lambda: defaultdict(set))
        self.contexts = {}
        self.unknown_containers = set()
        self.attributes = defaultdict(set)
        self.implicit_targets = defaultdict(dict)
        self.parser_parents = {}
        self.parser_commands = defaultdict(set)
        self.allocation_context = ()
        self.parser_defaults = defaultdict(lambda: defaultdict(set))
        self.parser_default_positions = {}
        self.parser_default_events = defaultdict(dict)
        self.parser_namespace_sites = {}
        self.parser_namespaces = defaultdict(set)
        self.argparse_constructors = {}
        for file, visitor in resolver.file_results.items():
            names = set()
            for imported in visitor.imports:
                if imported['module'] == 'argparse':
                    if imported['type'] == 'import':
                        names.add((imported['alias'] or 'argparse') + '.ArgumentParser')
                    elif imported['name'] == 'ArgumentParser':
                        names.add(imported['alias'] or 'ArgumentParser')
            self.argparse_constructors[file] = names
        self.iterations = 0
        self.converged = False
        self.definitions = {}
        for definitions in resolver.function_definitions.values():
            for definition in definitions:
                name = definition["name"]
                if definition["class"]:
                    name = f"{definition['class']}.{name}"
                self.definitions[(definition["file"], name)] = definition
        self.lambdas = {}
        from analyzer.entrypoints import seed_entrypoints
        seed_entrypoints(resolver, self.definitions, self.inputs)
        for file, visitor in resolver.file_results.items():
            for name, node in visitor.function_nodes.items():
                if isinstance(node, ast.Lambda):
                    self.lambdas[(file, id(node))] = name
        # The AST and declaration tables are immutable during value inference.
        # Index once instead of rescanning every assignment on every read.
        self.local_assignments = defaultdict(list)
        self.attribute_assignments = defaultdict(list)
        self.mutations = defaultdict(list)
        self.iteration_bindings = defaultdict(list)
        for file, visitor in resolver.file_results.items():
            for context, targets, expression, line in visitor.assignments:
                for target in targets:
                    for name, path in self.target_names(target):
                        self.local_assignments[(file, context, name)].append((expression, line, path))
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                        owner = self.owner(file, context)
                        self.attribute_assignments[(file, owner, target.attr)].append((context, expression))
                    elif isinstance(target, (ast.Attribute, ast.Subscript)):
                        self.mutations[(file, context)].append((target, expression))
            for context, target, iterable in visitor.iterations:
                for name, path in self.target_names(target):
                    self.iteration_bindings[(file, context, name)].append((iterable, path))

        self.decorator_names = {}
        self.parameter_data = {}
        for file, visitor in resolver.file_results.items():
            for name, node in visitor.function_nodes.items():
                self.decorator_names[(file, name)] = frozenset(
                    item.id for item in getattr(node, 'decorator_list', ()) if isinstance(item, ast.Name))
                positional = node.args.posonlyargs + node.args.args
                defaults = dict(zip([arg.arg for arg in positional[-len(node.args.defaults):]], node.args.defaults)) if node.args.defaults else {}
                defaults.update({arg.arg: default for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults) if default is not None})
                names = {arg.arg for arg in positional + node.args.kwonlyargs}
                if node.args.kwarg:
                    names.add(node.args.kwarg.arg)
                self.parameter_data[(file, name)] = (frozenset(names), defaults)
        # Per-analysis caches cannot leak metadata between projects. Their keys
        # never include mutable flow state, and expression/invoke/bind are NOT
        # memoized. The resolver tables and these AST indexes are fixed here.
        self._static_caches = {}
        if cache_static:
            for name in ('class_reference', 'resolve_method', 'lineage', 'named', 'receiver',
                         'assignments_before', 'shadowed_builtin', 'configured_method_pattern', '_accepts_keywords'):
                cached = lru_cache(maxsize=None)(getattr(self, name))
                setattr(self, name, cached)
                self._static_caches[name] = cached

    def cache_info(self):
        return {name: dict(cached.cache_info()._asdict()) for name, cached in self._static_caches.items()}

    def assignments_before(self, file, scope, node):
        assignments = tuple(
            (value, line, path) for value, line, path in self.local_assignments[(file, scope, node.id)]
            if (getattr(value, 'end_lineno', None) or line,
                getattr(value, 'end_col_offset', None) or 0) < (node.lineno, node.col_offset))
        latest = max(assignments, key=lambda item: (
            getattr(item[0], 'end_lineno', None) or item[1],
            getattr(item[0], 'end_col_offset', None) or 0), default=None)
        return assignments, latest

    def value(self, definition):
        name = definition["name"]
        if definition.get("class"):
            name = f"{definition['class']}.{name}"
        return ("class" if definition["type"] == "class" else "function", definition["file"], name)

    def owner(self, file, caller):
        definition = self.definitions.get((file, caller))
        return definition.get("class") if definition else None

    def class_reference(self, file, name):
        return self.resolver._class_reference(file, name)

    def resolve_method(self, file, name, attribute):
        return self.resolver._resolve_method_in_hierarchy(file, name, attribute)

    def lineage(self, file, name):
        return tuple(self._walk_lineage(file, name))

    def _walk_lineage(self, file, name, seen=None):
        seen = set() if seen is None else seen
        if (file, name) in seen:
            return
        seen = seen | {(file, name)}
        yield file, name
        for base in self.resolver.class_bases.get((file, name), []):
            definition = self.class_reference(file, base)
            if definition:
                yield from self._walk_lineage(definition['file'], definition['name'], seen)

    def decorated(self, definition, decorator):
        value = self.value(definition)
        return decorator in self.decorator_names.get((value[1], value[2]), ())

    def named(self, file, caller, name):
        definition = self.class_reference(file, name)
        if definition is None:
            definition = self.resolver._resolve_callee(file, caller, name, self.resolver.file_results[file])
        return frozenset((self.value(definition),)) if definition else frozenset()

    def receiver(self, file, caller, identifier):
        """Find a real method receiver, respecting nested parameter shadowing."""
        scope = caller
        visitor = self.resolver.file_results[file]
        while scope:
            node = visitor.function_nodes.get(scope)
            if node is not None:
                args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                if any(arg.arg == identifier for arg in args):
                    definition = self.definitions.get((file, scope))
                    if (definition and definition.get('class') and '.' not in definition['name']
                            and args and args[0].arg == identifier
                            and not self.decorated(definition, 'staticmethod')):
                        kind = 'class' if self.decorated(definition, 'classmethod') else 'instance'
                        return frozenset(((kind, file, definition['class']),))
                    return frozenset()
            scope = scope.rpartition('.')[0]
        return frozenset()

    def invoke(self, value, file, caller, call, seen):
        """Evaluate functions and __call__ with identical argument/return rules."""
        _, target_file, name = value
        context = self.bind(value, file, caller, call, seen)
        key = (target_file, name)
        previous = self.contexts.get(key)
        previous_allocation = self.allocation_context
        site = (file, caller, call.lineno, call.col_offset)
        if site not in self.allocation_context:
            self.allocation_context = (self.allocation_context + (site,))[-3:]
        self.contexts[key] = context
        try:
            self.assign_subscripts(target_file, name, seen)
            for scope, operation in self.resolver.file_results[target_file].call_nodes:
                if (scope == name and isinstance(operation.func, ast.Attribute)
                        and operation.func.attr in {'set_defaults', 'add_parser', 'add_subparsers'}):
                    self.expression(target_file, name, operation, seen)
            values = set()
            for returned in self.resolver.file_results[target_file].return_expressions.get(name, []):
                values |= self.expression(target_file, name, returned, seen)
            return values
        finally:
            self.allocation_context = previous_allocation
            if previous is None:
                self.contexts.pop(key, None)
            else:
                self.contexts[key] = previous

    def configured_method_pattern(self, file, caller, expression, receiver_file, receiver_class):
        """Bound externally configurable string dispatch to a local method family.

        A constructor parameter is an open library input, even if calls inside
        this source tree only use its default. Fixed literal attributes do not
        receive this expansion. The caller also requires an AttributeError guard.
        """
        visited = set()
        while isinstance(expression, ast.Name):
            if expression.id in visited:
                return None
            visited.add(expression.id)
            assignments = [item for item in self.local_assignments[(file, caller, expression.id)]
                           if item[1] < expression.lineno]
            if not assignments:
                return None
            expression = max(assignments, key=lambda item: item[1])[0]
        if not (isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Mod)
                and isinstance(expression.left, ast.Constant) and isinstance(expression.left.value, str)
                and expression.left.value.count('%') == 1 and '%s' in expression.left.value
                and isinstance(expression.right, ast.Attribute)):
            return None
        field = expression.right
        pattern = tuple(expression.left.value.split('%s'))
        if not any(pattern):
            return None
        if not isinstance(field.value, ast.Name):
            return None
        if ('instance', receiver_file, receiver_class) not in self.receiver(file, caller, field.value.id):
            return None
        for owner_file, owner_name in self.lineage(receiver_file, receiver_class):
            for scope, value in self.attribute_assignments[(owner_file, owner_name, field.attr)]:
                definition = self.definitions.get((owner_file, scope))
                if not definition or definition['name'] != '__init__' or not isinstance(value, ast.Name):
                    continue
                function = self.resolver.file_results[owner_file].function_nodes[scope]
                parameters = function.args.posonlyargs + function.args.args + function.args.kwonlyargs
                if any(parameter.arg == value.id for parameter in parameters[1:]):
                    if any(line < value.lineno for _, line, _ in self.local_assignments[(owner_file, scope, value.id)]):
                        continue
                    return pattern
        return None

    def shadowed_builtin(self, file, caller, name):
        if self.named(file, caller, name):
            return True
        visitor = self.resolver.file_results[file]
        scope = caller
        while True:
            if self.local_assignments[(file, scope, name)]:
                return True
            function = visitor.function_nodes.get(scope)
            if function:
                parameters = function.args.posonlyargs + function.args.args + function.args.kwonlyargs
                parameters += [arg for arg in (function.args.vararg, function.args.kwarg) if arg]
                if any(parameter.arg == name for parameter in parameters):
                    return True
            if scope == '<module>':
                break
            scope = scope.rpartition('.')[0] or '<module>'
        return any((item['alias'] or item['name'] or item['module']) == name
                   and not (item['module'] == 'builtins' and item['name'] == name)
                   for item in visitor.imports)

    def expression(self, file, caller, node, seen=None):
        if node is None:
            return set()
        seen = set() if seen is None else seen
        key = (file, caller, id(node))
        if key in seen:
            return set()
        seen = seen | {key}
        visitor = self.resolver.file_results[file]
        if isinstance(node, ast.Name):
            receiver = self.receiver(file, caller, node.id)
            if receiver:
                scope = caller
                while scope:
                    context = self.contexts.get((file, scope), {})
                    if node.id in context:
                        return set(context[node.id])
                    scope = scope.rpartition('.')[0]
                return receiver
            scope = caller
            while True:
                assignments, latest = self.assignments_before(file, scope, node)
                if latest is not None:
                    value, _, path = latest
                    if id(value) in visitor.conditional_values:
                        values = set()
                        for expression, _, indices in reversed(assignments):
                            values |= self.project(self.expression(file, scope, expression, seen), indices)
                            if id(expression) not in visitor.conditional_values:
                                break
                        return values
                    return self.project(self.expression(file, scope, value, seen), path)
                bindings = self.iteration_bindings[(file, scope, node.id)]
                if bindings:
                    return set().union(*(
                        self.project(self.iterate(self.expression(file, scope, iterable, seen)), path)
                        for iterable, path in bindings
                    ))
                function = visitor.function_nodes.get(scope)
                if function is not None:
                    names, defaults = self.parameter_data[(file, scope)]
                    if node.id in names:
                        context = self.contexts.get((file, scope), {})
                        if node.id in context:
                            return set(context[node.id])
                        values = set(self.inputs[(file, scope)][node.id])
                        if node.id in defaults:
                            values |= self.expression(file, scope, defaults[node.id], seen)
                        if function.args.kwarg and node.id == function.args.kwarg.arg and not context:
                            container = ("container", file, f"{scope}:unknown-keywords")
                            self.unknown_containers.add(container)
                            values.add(container)
                        return values
                parent = scope.rpartition(".")[0]
                if not parent:
                    if scope == "<module>":
                        break
                    scope = "<module>"
                else:
                    scope = parent
            return self.named(file, caller, node.id)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, int, bool)) or node.value is None:
                return {("literal", "", repr(node.value))}
            return set()
        if isinstance(node, ast.Lambda):
            return {("function", file, self.lambdas[(file, id(node))])}
        if isinstance(node, ast.Attribute):
            values = set()
            receivers = self.expression(file, caller, node.value, seen)
            for kind, parser_file, parser_name in receivers:
                if kind == 'argparse_namespace':
                    namespace = (kind, parser_file, parser_name)
                    for parser in self.parser_namespaces[(kind, parser_file, parser_name)]:
                        values |= self.parser_default_at(parser, node.attr, self.parser_namespace_sites[namespace])
            if not receivers and isinstance(node.value, ast.Name) and (caller, node.value.id, node.attr) in visitor.attribute_guards:
                receivers = {("instance", definition["file"], definition["class"])
                             for definition in self.resolver.function_definitions.get(node.attr, [])
                             if definition["class"] is not None}
            for kind, value_file, name in receivers:
                if kind not in {"class", "instance"}:
                    continue
                method = self.resolve_method(value_file, name, node.attr)
                if method:
                    if kind == "instance" and self.decorated(method, "property"):
                        identity = (method['file'], method.get('class'), method['name'])
                        self.implicit_targets[(file, caller, node.lineno)][identity] = method
                        _, method_file, method_name = self.value(method)
                        for returned in self.resolver.file_results[method_file].return_expressions.get(method_name, []):
                            values |= self.expression(method_file, method_name, returned, seen)
                    else:
                        values.add(self.value(method))
                nested = self.class_reference(value_file, f"{name}.{node.attr}")
                if nested:
                    values.add(self.value(nested))
                for owner_file, owner_name in self.lineage(value_file, name):
                    values |= self.attributes[(owner_file, owner_name, node.attr)]
                    for context, value in self.attribute_assignments[(owner_file, owner_name, node.attr)]:
                        values |= self.expression(owner_file, context, value, seen)
            if not values:
                dotted = visitor._get_call_name(node)
                if dotted:
                    values = self.named(file, caller, dotted)
            return values
        if isinstance(node, ast.Call):
            if ((isinstance(node.func, ast.Attribute) and node.func.attr in {'add_subparsers', 'add_parser', 'set_defaults', 'parse_args'})
                    or visitor._get_call_name(node.func) in self.argparse_constructors[file]):
                parser_value = self.argparse_call(file, caller, node, seen)
                if parser_value is not None:
                    return parser_value
            if isinstance(node.func, ast.Name) and node.func.id in {"zip", "enumerate"} and not self.named(file, caller, node.func.id):
                container = ("container", file, f"{caller}:iteration:{node.lineno}:{node.col_offset}")
                row = ("container", file, container[2] + ":row")
                values = [self.iterate(self.expression(file, caller, arg, seen)) for arg in node.args]
                if node.func.id == "enumerate":
                    values = [set(), values[0] if values else set()]
                for index, items in enumerate(values):
                    self.entries[row][repr(index)] |= items
                    self.containers[row] |= items
                self.containers[container].add(row)
                return {container}
            if isinstance(node.func, ast.Name) and node.func.id == "type" and len(node.args) == 1:
                return {("class", value_file, name)
                        for kind, value_file, name in self.expression(file, caller, node.args[0], seen)
                        if kind == "instance"}
            if isinstance(node.func, ast.Name) and node.func.id == "dict" and not self.named(file, caller, "dict"):
                sources = [self.expression(file, caller, argument, seen) for argument in node.args]
                signature = self.mapping_signature(set().union(*sources))
                container = ("container", file, f"{caller}:dict:{node.lineno}:{node.col_offset}:{signature}")
                for argument in node.args:
                    self.copy_mapping(container, self.expression(file, caller, argument, seen))
                for keyword in node.keywords:
                    values = self.expression(file, caller, keyword.value, seen)
                    if keyword.arg:
                        self.entries[container][repr(keyword.arg)] |= values
                        self.containers[container] |= values
                    else:
                        self.copy_mapping(container, values)
                return {container}
            if (isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2
                    and not self.shadowed_builtin(file, caller, 'getattr')):
                values = set()
                for kind, value_file, name in self.expression(file, caller, node.args[0], seen):
                    if kind not in {"instance", "class"}:
                        continue
                    for attribute in self.expression(file, caller, node.args[1], seen):
                        if attribute[0] == "literal":
                            attribute_name = ast.literal_eval(attribute[2])
                            if isinstance(attribute_name, str):
                                method = self.resolve_method(value_file, name, attribute_name)
                                if method:
                                    values.add(self.value(method))
                    if kind == 'instance' and id(node) in visitor.guarded_getattrs:
                        pattern = self.configured_method_pattern(file, caller, node.args[1], value_file, name)
                        if pattern:
                            prefix, suffix = pattern
                            owners = set(self.lineage(value_file, name))
                            candidates = {definition['name']
                                          for definitions in self.resolver.function_definitions.values()
                                          for definition in definitions
                                          if (definition['file'], definition.get('class')) in owners
                                          and '.' not in definition['name']
                                          and definition['name'].startswith(prefix)
                                          and definition['name'].endswith(suffix)}
                            for candidate in candidates:
                                method = self.resolve_method(value_file, name, candidate)
                                if method:
                                    values.add(self.value(method))
                return values
            if isinstance(node.func, ast.Attribute):
                receivers = self.expression(file, caller, node.func.value, seen)
                containers = {value for value in receivers if value[0] == "container"}
                if containers:
                    if node.func.attr in {"append", "extend"} and node.args:
                        added = self.expression(file, caller, node.args[0], seen)
                        if node.func.attr == "extend":
                            added = self.elements(added)
                        for container in containers:
                            self.containers[container] |= added
                        return set()
                    if node.func.attr == "setdefault":
                        default_values = self.expression(file, caller, node.args[1], seen) if len(node.args) > 1 else {("literal", "", "None")}
                        if not any(value[0] == "container" for value in default_values):
                            keys = self.expression(file, caller, node.args[0], seen) if node.args else set()
                            existing = self.lookup(containers, keys)
                            for container in containers:
                                for key in keys:
                                    if key[0] == "literal":
                                        self.entries[container][key[2]] |= default_values
                                        self.containers[container] |= default_values
                            return existing | default_values
                        children = set()
                        keys = self.expression(file, caller, node.args[0], seen) if node.args else set()
                        literal_keys = {value[2] for value in keys if value[0] == "literal"} or {"?"}
                        for container in containers:
                            for mapping_key in literal_keys:
                                child = ("container", container[1], container[2] + ":mapping:" + mapping_key)
                                self.containers[container].add(child)
                                self.entries[container][mapping_key].add(child)
                                children.add(child)
                        return children
                    if node.func.attr in {"values", "items"}:
                        sequence = ("container", file, f"{caller}:{node.func.attr}:{node.lineno}:{node.col_offset}")
                        for container in containers:
                            if node.func.attr == "values":
                                self.containers[sequence] |= self.containers[container]
                            else:
                                for key, items in list(self.entries[container].items()):
                                    row = ("container", container[1], f"{container[2]}:item:{key}")
                                    if key != "?":
                                        self.entries[row]['0'].add(('literal', '', key))
                                    self.entries[row]['1'] |= items
                                    self.containers[row] |= self.entries[row]['0'] | items
                                    self.containers[sequence].add(row)
                        return {sequence}
                if node.func.attr in {"get", "pop"} and node.args:
                    keys = self.expression(file, caller, node.args[0], seen)
                    values = self.lookup(containers, keys)
                    if containers & self.unknown_containers:
                        values.add(("unknown", "", "keyword-value"))
                    known_keys = {value[2] for value in keys if value[0] == "literal"}
                    certain = containers and known_keys and all(
                        container not in self.unknown_containers and all(key in self.entries[container] for key in known_keys)
                        for container in containers
                    )
                    default = self.expression(file, caller, node.args[1], seen) if len(node.args) > 1 else {('literal', '', 'None')}
                    return values if certain else values | default
            values = set()
            for value in self.expression(file, caller, node.func, seen):
                kind, value_file, name = value
                if kind == "class":
                    initializer = self.resolve_method(value_file, name, "__init__")
                    if initializer and not self.accepts_keywords(initializer, file, caller, node):
                        continue
                    values.add(("instance", value_file, name))
                    if initializer:
                        self.bind(self.value(initializer), file, caller, node, seen)
                elif kind == "function":
                    values |= self.invoke(value, file, caller, node, seen)
                elif kind == "instance":
                    method = self.resolve_method(value_file, name, "__call__")
                    if method:
                        values |= self.invoke(self.value(method), file, caller, node, seen)
            return values
        if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            container = ("container", file, f"{caller}:{node.lineno}:{node.col_offset}")
            items = node.values if isinstance(node, ast.Dict) else node.elts
            self.containers[container] |= set().union(*(self.expression(file, caller, item, seen) for item in items))
            if isinstance(node, ast.Dict):
                for key_node, item in zip(node.keys, node.values):
                    for key in self.expression(file, caller, key_node, seen):
                        if key[0] == "literal":
                            self.entries[container][key[2]] |= self.expression(file, caller, item, seen)
            elif isinstance(node, (ast.Tuple, ast.List)):
                for index, item in enumerate(node.elts):
                    self.entries[container][repr(index)] |= self.expression(file, caller, item, seen)
            return {container}
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            container = ("container", file, f"{caller}:comprehension:{node.lineno}:{node.col_offset}")
            self.containers[container] |= self.expression(file, caller, node.elt, seen)
            return {container}
        if isinstance(node, ast.Subscript):
            values = self.expression(file, caller, node.value, seen)
            if isinstance(node.slice, ast.Slice):
                # Unknown bounds conservatively retain all possible elements.
                return values
            return self.lookup(values, self.expression(file, caller, node.slice, seen))
        if isinstance(node, ast.IfExp):
            return self.expression(file, caller, node.body, seen) | self.expression(file, caller, node.orelse, seen)
        if isinstance(node, ast.BoolOp):
            return set().union(*(self.expression(file, caller, value, seen) for value in node.values))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            values = set()
            for left in self.expression(file, caller, node.left, seen):
                for right in self.expression(file, caller, node.right, seen):
                    if left[0] == right[0] == "literal":
                        try:
                            value = ast.literal_eval(left[2]) % ast.literal_eval(right[2])
                            if isinstance(value, str):
                                values.add(("literal", "", repr(value)))
                        except (TypeError, ValueError, ZeroDivisionError):
                            pass
            return values
        return set()

    def target_names(self, target, path=()):
        if isinstance(target, ast.Name):
            yield target.id, path
        elif isinstance(target, (ast.Tuple, ast.List)):
            for index, item in enumerate(target.elts):
                yield from self.target_names(item, path + (index,))

    def accepts_keywords(self, definition, file, caller, call):
        return self._accepts_keywords(self.value(definition), file, caller, call)

    def _accepts_keywords(self, value, file, caller, call):
        node = self.resolver.file_results[value[1]].function_nodes.get(value[2])
        if node is None or node.args.kwarg is not None:
            return True
        accepted = {argument.arg for argument in node.args.args + node.args.kwonlyargs}
        supplied = {keyword.arg for keyword in call.keywords if keyword.arg}
        for keyword in call.keywords:
            if keyword.arg is not None:
                continue
            if isinstance(keyword.value, ast.Dict):
                supplied |= {key.value for key in keyword.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
            elif isinstance(keyword.value, ast.Name):
                # A preceding unconditional setdefault guarantees this key is
                # supplied by **mapping, even when other keys are unknown.
                visitor = self.resolver.file_results[file]
                function = visitor.function_nodes.get(caller)
                body = getattr(function, "body", [])
                direct_calls = {id(statement.value) for statement in body if isinstance(statement, ast.Expr)} if isinstance(body, list) else set()
                for context, prior in visitor.call_nodes:
                    if context != caller or prior.lineno >= call.lineno:
                        continue
                    func = prior.func
                    if isinstance(func, ast.Attribute) and func.attr == "setdefault" and isinstance(func.value, ast.Name) and func.value.id == keyword.value.id:
                        if prior.args and isinstance(prior.args[0], ast.Constant) and isinstance(prior.args[0].value, str):
                            reassigned = any(
                                context == caller and prior.lineno < line < call.lineno
                                and any(name == keyword.value.id for target in targets for name, _ in self.target_names(target))
                                for context, targets, _, line in visitor.assignments
                            )
                            if id(prior) in direct_calls and not reassigned:
                                supplied.add(prior.args[0].value)
        return supplied <= accepted

    def project(self, values, indices):
        for index in indices:
            values = self.lookup(values, {("literal", "", repr(index))})
        return values

    def lookup(self, containers, keys):
        literal_keys = {value[2] for value in keys if value[0] == "literal"}
        if any(value[0] == "unknown" for value in keys):
            literal_keys = set()
        values = set()
        for container in containers:
            if container[0] != "container":
                continue
            if literal_keys and self.entries[container]:
                for key in literal_keys:
                    values |= self.entries[container].get(key, set())
                values |= self.entries[container].get("?", set())
            else:
                values |= self.containers[container]
        return values

    def copy_mapping(self, destination, sources):
        for source in sources:
            if source[0] != "container":
                continue
            for key, values in list(self.entries[source].items()):
                self.entries[destination][key] |= values
                self.containers[destination] |= values
            if source in self.unknown_containers:
                self.unknown_containers.add(destination)

    def mapping_signature(self, values):
        summary = []
        for value in sorted(values):
            if value[0] == "container":
                entries = tuple((key, tuple(sorted(item if item[0] != "container" else ("container", "", "nested") for item in items)))
                                for key, items in sorted(self.entries[value].items()))
                summary.append(("mapping", value in self.unknown_containers, entries))
            else:
                summary.append(value)
        # Equivalent mapping shapes from recursive forwarding share a context.
        # Otherwise repeated **kwargs wrappers create new identities forever.
        normalized = sorted({repr(item) for item in summary})
        return hashlib.sha256(repr(normalized).encode()).hexdigest()[:16]

    def assign_subscripts(self, file, caller, seen=None):
        for target, expression in self.mutations[(file, caller)]:
            if isinstance(target, ast.Attribute):
                receivers = self.expression(file, caller, target.value, seen)
                values = self.expression(file, caller, expression, seen)
                for kind, value_file, name in receivers:
                    if kind in {"instance", "class"}:
                        self.attributes[(value_file, name, target.attr)] |= values
            if isinstance(target, ast.Subscript):
                containers = self.expression(file, caller, target.value, seen)
                values = self.expression(file, caller, expression, seen)
                keys = self.expression(file, caller, target.slice, seen)
                literal_keys = {value[2] for value in keys if value[0] == "literal"} or {"?"}
                for container in containers:
                    if container[0] == "container":
                        self.containers[container] |= values
                        for key in literal_keys:
                            self.entries[container][key] |= values

    def elements(self, values, seen=None):
        seen = set() if seen is None else seen
        result = set()
        for value in values:
            if value[0] != "container":
                result.add(value)
            elif value not in seen:
                result |= self.elements(self.containers[value], seen | {value})
        return result

    def iterate(self, values):
        """Iteration unwraps one sequence level; tuple positions stay intact."""
        result = set()
        for value in values:
            if value[0] == "container":
                result |= self.containers[value]
        return result

    def state(self):
        return (
            sum(len(values) for parameters in self.inputs.values() for values in parameters.values()),
            sum(len(values) for values in self.containers.values()),
            sum(len(values) for entries in self.entries.values() for values in entries.values()),
            len(self.unknown_containers),
            sum(len(values) for values in self.attributes.values()),
            len(self.parser_parents),
            sum(len(values) for fields in self.parser_defaults.values() for values in fields.values()),
            sum(len(values) for values in self.parser_namespaces.values()),
            sum(len(values) for events in self.parser_default_events.values() for fields, _ in events.values() for values in fields.values()),
        )

    def argparse_call(self, file, caller, call, seen):
        """Limited stdlib parser registration/Namespace model, scoped per parser."""
        visitor = self.resolver.file_results[file]
        for test, expected in visitor.call_guards.get(id(call), ()):
            values = self.expression(file, caller, test, seen)
            if values and all(v[0] == 'literal' for v in values):
                truths = {bool(ast.literal_eval(v[2])) for v in values}
                if truths == {not expected}:
                    return set()
        dotted = visitor._get_call_name(call.func)
        constructor = False
        for imported in visitor.imports:
            if imported['module'] != 'argparse':
                continue
            if imported['type'] == 'import':
                visible = imported['alias'] or 'argparse'
                expected = visible + '.ArgumentParser'
            elif imported['name'] == 'ArgumentParser':
                visible = imported['alias'] or 'ArgumentParser'
                expected = visible
            else:
                continue
            if dotted != expected:
                continue
            scope = caller
            shadowed = False
            while scope:
                if visible in self.parameter_data.get((file, scope), ((), {}))[0]:
                    shadowed = True
                if any(line < call.lineno for _, line, _ in self.local_assignments[(file, scope, visible)]):
                    shadowed = True
                scope = scope.rpartition('.')[0] or ('<module>' if scope != '<module>' else '')
            if not shadowed and not self.named(file, caller, visible):
                constructor = True
        context_key = hashlib.sha256(repr(self.allocation_context).encode()).hexdigest()[:16]
        identity = f'{caller}:{call.lineno}:{call.col_offset}:{context_key}'
        if constructor:
            return {('argparse_parser', file, identity)}
        if not isinstance(call.func, ast.Attribute):
            return None
        receivers = self.expression(file, caller, call.func.value, seen)
        parsers = {v for v in receivers if v[0] in {'argparse_parser', 'argparse_subparsers'}}
        if not parsers:
            return None
        method = call.func.attr
        if method == 'add_subparsers':
            return {('argparse_subparsers', v[1], v[2]) for v in parsers if v[0] == 'argparse_parser'}
        if method == 'add_parser':
            children = set()
            for parent in parsers:
                if parent[0] == 'argparse_subparsers':
                    parent_key = hashlib.sha256(repr(parent).encode()).hexdigest()[:16]
                    child = ('argparse_parser', file, identity + ':' + parent_key)
                    self.parser_parents[child] = ('argparse_parser', parent[1], parent[2])
                    if call.args:
                        self.parser_commands[child] |= {v[2] for v in self.expression(file, caller, call.args[0], seen) if v[0] == 'literal'}
                    for keyword in call.keywords:
                        if keyword.arg == 'aliases':
                            self.parser_commands[child] |= {v[2] for v in self.iterate(self.expression(file, caller, keyword.value, seen)) if v[0] == 'literal'}
                    children.add(child)
            return children
        if method == 'set_defaults':
            for parser in parsers:
                position = (file, caller, call.lineno, call.col_offset)
                fields = {k.arg: self.expression(file, caller, k.value, seen) for k in call.keywords if k.arg}
                self.parser_default_events[parser][position] = (fields, id(call) in visitor.conditional_calls)
                for keyword in call.keywords:
                    if keyword.arg:
                        key = (parser, keyword.arg)
                        position = (file, caller, call.lineno, call.col_offset)
                        previous = self.parser_default_positions.get(key)
                        if previous and previous[:2] == position[:2] and previous[2:] > position[2:]:
                            continue
                        conditional = id(call) in visitor.conditional_calls
                        if not conditional and previous and previous[:2] == position[:2] and previous[2:] < position[2:]:
                            self.parser_defaults[parser][keyword.arg].clear()
                        if not conditional:
                            self.parser_default_positions[key] = position
                        self.parser_defaults[parser][keyword.arg] |= self.expression(file, caller, keyword.value, seen)
            return set()
        if method == 'parse_args':
            if len(call.args) > 1 or any(keyword.arg == 'namespace' for keyword in call.keywords):
                return set()
            argv_node = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == 'args'), None)
            argv = self.argparse_argv(file, caller, argv_node, seen) if argv_node is not None else None
            namespace = ('argparse_namespace', file, identity)
            self.parser_namespace_sites[namespace] = (file, caller, call.lineno, call.col_offset)
            if argv is not None:
                if any(word.startswith('-') for word in argv):
                    return set()  # Option arities are not modeled yet.
                selected = set(parsers)
                for word in argv:
                    next_parsers = set()
                    for parser in selected:
                        children = {c for c, p in self.parser_parents.items() if p == parser}
                        if children:
                            next_parsers |= {c for c in children if repr(word) in self.parser_commands[c]}
                        else:
                            next_parsers.add(parser)  # Remaining positional operand.
                    selected = next_parsers
                self.parser_namespaces[namespace] |= selected
                return {namespace}
            # Unknown CLI inputs may select any registered subparser, but never
            # a command registered on a different root parser.
            for candidate in set(self.parser_defaults) | parsers:
                ancestor = candidate
                visited = set()
                while ancestor not in visited:
                    if ancestor in parsers:
                        self.parser_namespaces[namespace].add(candidate)
                        break
                    visited.add(ancestor)
                    ancestor = self.parser_parents.get(ancestor)
                    if ancestor is None:
                        break
            return {namespace}
        return None

    def parser_default_at(self, parser, attribute, site, visited=None):
        """Replay registrations before this parse, keeping unknown branches."""
        visited = set() if visited is None else visited
        if parser in visited:
            return set()
        parent = self.parser_parents.get(parser)
        inherited = self.parser_default_at(parent, attribute, site, visited | {parser}) if parent else set()
        groups = defaultdict(list)
        for position, (fields, conditional) in self.parser_default_events[parser].items():
            if attribute not in fields:
                continue
            if position[:2] == site[:2] and position[2:] >= site[2:]:
                continue
            groups[position[:2]].append((position[2:], fields[attribute], conditional))
        if not groups:
            return inherited
        result = set()
        for events in groups.values():
            current = set(inherited)
            for _, values, conditional in sorted(events, key=lambda event: event[0]):
                current = current | values if conditional else set(values)
            result |= current
        return result

    def argparse_argv(self, file, caller, node, seen):
        """A known literal sequence, or None for runtime/unknown argv."""
        values = self.expression(file, caller, node, seen)
        if len(values) != 1:
            return None
        value = next(iter(values))
        if value[0] != 'container':
            return None
        result = []
        for i in range(len(self.entries[value])):
            items = self.entries[value].get(repr(i), set())
            if len(items) != 1:
                return None
            item = next(iter(items))
            if item[0] != 'literal':
                return None
            literal = ast.literal_eval(item[2])
            if not isinstance(literal, str):
                return None
            result.append(literal)
        return result

    def bind(self, value, file, caller, call, seen):
        _, target_file, name = value
        node = self.resolver.file_results[target_file].function_nodes.get(name)
        if node is None:
            return {}
        context = {}
        args = node.args.posonlyargs + node.args.args
        definition = self.definitions.get((target_file, name))
        implicit = bool(args and definition and definition.get('class')
                        and '.' not in definition['name'] and not self.decorated(definition, 'staticmethod'))
        # Class.method(instance, argument) supplies its receiver explicitly.
        # Class construction and super().method(...) still bind it implicitly.
        if implicit and isinstance(call.func, ast.Attribute) and call.func.attr == node.name:
            receiver_name = self.resolver.file_results[file]._get_call_name(call.func.value)
            if (isinstance(call.func.value, (ast.Name, ast.Attribute))
                    and receiver_name and self.class_reference(file, receiver_name)
                    and not self.decorated(definition, 'classmethod')):
                implicit = False
        if implicit:
            if isinstance(call.func, ast.Attribute) and node.name == '__enter__':
                receivers = self.expression(file, caller, call.func.value, seen)
                actual = set()
                for kind, receiver_file, receiver_name in receivers:
                    if kind not in {'instance', 'class'}:
                        continue
                    method = self.resolve_method(receiver_file, receiver_name, node.name)
                    if method and self.value(method) == value:
                        actual.add((kind, receiver_file, receiver_name))
                if actual:
                    context[args[0].arg] = actual
            args = args[1:]
        positional = []
        for expression in call.args:
            if isinstance(expression, ast.Starred):
                containers = self.expression(file, caller, expression.value, seen)
                count = max((len(self.entries[container]) for container in containers if container[0] == "container"), default=0)
                for index in range(min(count, len(args))):
                    positional.append(self.project(containers, (index,)))
            else:
                positional.append(self.expression(file, caller, expression, seen))
        for argument, values in zip(args, positional):
            self.inputs[(target_file, name)][argument.arg] |= values
            context[argument.arg] = values
        for keyword in call.keywords:
            if keyword.arg:
                values = self.expression(file, caller, keyword.value, seen)
                self.inputs[(target_file, name)][keyword.arg] |= values
                context[keyword.arg] = values
            else:
                values = self.expression(file, caller, keyword.value, seen)
                for argument in args + node.args.kwonlyargs:
                    expanded = self.lookup(values, {("literal", "", repr(argument.arg))})
                    if expanded:
                        context[argument.arg] = expanded
                        self.inputs[(target_file, name)][argument.arg] |= expanded
        if node.args.kwarg:
            keyword_values = {id(keyword): self.expression(file, caller, keyword.value, seen) for keyword in call.keywords}
            signature = self.mapping_signature(set().union(*keyword_values.values()))
            container = ("container", file, f"{caller}:kwargs:{call.lineno}:{call.col_offset}:{target_file}:{name}:{signature}")
            parameter_names = {arg.arg for arg in args + node.args.kwonlyargs}
            for keyword in call.keywords:
                values = self.expression(file, caller, keyword.value, seen)
                if keyword.arg is None:
                    self.copy_mapping(container, values)
                    for parameter in parameter_names:
                        expanded = self.entries[container].get(repr(parameter))
                        if expanded is not None:
                            context[parameter] = set(expanded)
                            self.inputs[(target_file, name)][parameter] |= expanded
                elif keyword.arg not in parameter_names:
                    self.entries[container][repr(keyword.arg)] |= values
                    self.containers[container] |= values
            context[node.args.kwarg.arg] = {container}
            self.inputs[(target_file, name)][node.args.kwarg.arg].add(container)
        return context

    def analyze(self):
        # Iterate argument propagation to a fixed point, with an explicit bound.
        for iteration in range(12):
            self.iterations = iteration + 1
            before = self.state()
            for file, visitor in self.resolver.file_results.items():
                self.assign_subscripts(file, "<module>")
                for scope in visitor.function_nodes:
                    # Known callers are processed under their own bindings.
                    # Replaying their mutations with pooled parameters would
                    # mix dictionary keys and values from unrelated calls.
                    if not any(self.inputs.get((file, scope), {}).values()):
                        self.assign_subscripts(file, scope)
                for caller, call in visitor.call_nodes:
                    self.expression(file, caller, call)
            after = self.state()
            if before == after:
                self.converged = True
                break
        targets = defaultdict(dict)
        for file, visitor in self.resolver.file_results.items():
            for caller, call in visitor.call_nodes:
                key = (file, caller, call.lineno)
                for kind, target_file, name in self.expression(file, caller, call.func):
                    if kind == "function":
                        definition = self.definitions.get((target_file, name))
                    elif kind == "class":
                        definition = self.class_reference(target_file, name)
                        if definition:
                            definition = self.resolver._resolve_constructor(definition)
                            if not self.accepts_keywords(definition, file, caller, call):
                                continue
                    elif kind == "instance":
                        definition = self.resolve_method(target_file, name, "__call__")
                    else:
                        continue
                    if definition:
                        identity = (definition["file"], definition.get("class"), definition["name"])
                        targets[key][identity] = definition
            for caller, attribute in visitor.attribute_nodes:
                self.expression(file, caller, attribute)
            for caller, expression in visitor.with_items:
                for kind, target_file, name in self.expression(file, caller, expression):
                    if kind != 'instance':
                        continue
                    for special in ('__enter__', '__exit__'):
                        definition = self.resolve_method(target_file, name, special)
                        if definition:
                            identity = (definition['file'], definition.get('class'), definition['name'])
                            targets[(file, caller, expression.lineno)][identity] = definition
        for key, definitions in self.implicit_targets.items():
            targets[key].update(definitions)
        return targets

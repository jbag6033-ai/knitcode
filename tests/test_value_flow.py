from analyzer.resolver import CallResolver


def edges(tmp_path, source):
    (tmp_path / "main.py").write_text(source, encoding="utf-8")
    resolver = CallResolver(tmp_path)
    resolver.analyze_project()
    return {
        (result["caller"],
         (result["target"]["class"] + "." if result["target"]["class"] else "") + result["target"]["name"])
        for result in resolver.resolve_calls() if result["target"] is not None
    }


def test_returned_instance_method(tmp_path):
    result = edges(tmp_path, """
class Formatter:
    def format(self): pass
def factory(): return Formatter()
def run():
    value = factory()
    value.format()
""")
    assert ("run", "Formatter.format") in result


def test_default_constructor_stored_on_self(tmp_path):
    result = edges(tmp_path, """
class Formatter:
    def __init__(self): pass
    def format(self): pass
class Parser:
    def __init__(self, factory=Formatter): self.factory = factory
    def make(self): return self.factory()
    def run(self):
        formatter = self.make()
        formatter.format()
""")
    assert ("Parser.make", "Formatter.__init__") in result
    assert ("Parser.run", "Formatter.format") in result


def test_constructor_argument_becomes_attribute_type(tmp_path):
    result = edges(tmp_path, """
class Formatter:
    def format(self): pass
class Section:
    def __init__(self, formatter): self.formatter = formatter
    def run(self): self.formatter.format()
def main(): Section(Formatter())
""")
    assert ("Section.run", "Formatter.format") in result


def test_returned_callable(tmp_path):
    result = edges(tmp_path, """
def factory():
    def callback(): pass
    return callback
def run():
    callback = factory()
    callback()
""")
    assert ("run", "factory.callback") in result


def test_lambda_alias_chain(tmp_path):
    result = edges(tmp_path, """
def run():
    first = lambda: 1
    second = lambda: first()
    second()
""")
    assert ("run.<lambda2>", "run.<lambda1>") in result


def test_callable_list_iteration(tmp_path):
    result = edges(tmp_path, """
def first(): pass
def second(): pass
def run():
    callbacks = []
    callbacks.append(first)
    callbacks.append(second)
    for callback in callbacks: callback()
""")
    assert ("run", "first") in result and ("run", "second") in result


def test_registry_constructor(tmp_path):
    result = edges(tmp_path, """
class Action:
    def __init__(self): pass
class Registry:
    def __init__(self):
        self.entries = {}
        self.register('action', Action)
    def register(self, name, value):
        entries = self.entries.setdefault(name, {})
        entries['default'] = value
    def lookup(self, name): return self.entries[name].get('default')
    def run(self):
        factory = self.lookup('action')
        factory()
""")
    assert ("Registry.run", "Action.__init__") in result


def test_recursive_return_inference_terminates(tmp_path):
    result = edges(tmp_path, """
def first(): return second()
def second(): return first()
def run():
    value = first()
    value.unknown()
""")
    assert not any(target.endswith("unknown") for _, target in result)


def test_registry_keys_do_not_mix_callables(tmp_path):
    result = edges(tmp_path, """
def first(): pass
def second(): pass
def main():
    mapping = {'first': first, 'second': second}
    callback = mapping['first']
    callback()
""")
    assert ("main", "first") in result
    assert ("main", "second") not in result


def test_getattr_from_formatted_literal_attribute(tmp_path):
    result = edges(tmp_path, """
class Service:
    def __init__(self, name='work'): self.name = name
    def handle_work(self): pass
    def run(self):
        callback = getattr(self, 'handle_%s' % self.name)
        callback()
""")
    assert ("Service.run", "Service.handle_work") in result


def test_lambda_definition_alone_does_not_create_call(tmp_path):
    result = edges(tmp_path, """
def run():
    callback = lambda: 1
""")
    assert result == set()


def test_lambda_alternatives_in_unknown_branches(tmp_path):
    result = edges(tmp_path, """
def run(flag):
    if flag:
        callback = lambda: 1
    else:
        callback = lambda: 2
    wrapper = lambda: callback()
    wrapper()
""")
    assert ("run.<lambda3>", "run.<lambda1>") in result
    assert ("run.<lambda3>", "run.<lambda2>") in result


def test_inline_sorted_lambda_is_possible_callback(tmp_path):
    result = edges(tmp_path, """
def run(items): return sorted(items, key=lambda item: item)
""")
    assert ("run", "run.<lambda1>") in result


def test_separate_registry_names_preserve_call_context(tmp_path):
    result = edges(tmp_path, """
class First:
    def __init__(self): pass
class Second:
    def __init__(self): pass
class Registry:
    def __init__(self):
        self.entries = {}
        self.register('first', First)
        self.register('second', Second)
    def register(self, name, value):
        entries = self.entries.setdefault(name, {})
        entries['factory'] = value
    def lookup(self, name): return self.entries[name].get('factory')
    def run(self):
        factory = self.lookup('first')
        factory()
""")
    assert ("Registry.run", "First.__init__") in result
    assert ("Registry.run", "Second.__init__") not in result

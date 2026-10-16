from analyzer.resolver import CallResolver


def resolve(tmp_path, source):
    (tmp_path / "main.py").write_text(source, encoding="utf-8")
    resolver = CallResolver(tmp_path)
    resolver.analyze_project()
    return resolver.resolve_calls()


def pairs(results):
    return {
        (result["caller"],
         (result["target"]["class"] + "." if result["target"]["class"] else "") + result["target"]["name"])
        for result in results if result["target"] is not None
    }


def test_nested_function_uses_enclosing_name(tmp_path):
    results = resolve(tmp_path, """
def helper(): pass
def outer():
    def inner():
        helper()
    inner()
""")
    assert pairs(results) == {("outer", "outer.inner"), ("outer.inner", "helper")}


def test_sibling_nested_functions_are_lexically_resolved(tmp_path):
    results = resolve(tmp_path, """
def outer():
    def first(): second()
    def second(): pass
    first()
def other():
    def second(): pass
    second()
""")
    assert pairs(results) == {
        ("outer", "outer.first"), ("outer.first", "outer.second"), ("other", "other.second"),
    }


def test_nested_function_is_not_visible_outside_owner(tmp_path):
    results = resolve(tmp_path, """
def owner():
    def hidden(): pass
def unrelated(): hidden()
""")
    assert results[0]["target"] is None


def test_nested_method_function_keeps_class_and_self(tmp_path):
    results = resolve(tmp_path, """
class Service:
    def validate(self): pass
    def run(self):
        def callback(): self.validate()
        callback()
""")
    assert pairs(results) == {
        ("Service.run", "Service.run.callback"), ("Service.run.callback", "Service.validate"),
    }


def test_nested_class_method_keeps_full_owner(tmp_path):
    results = resolve(tmp_path, """
class Outer:
    class Inner:
        def validate(self): pass
        def run(self): self.validate()
""")
    assert pairs(results) == {("Outer.Inner.run", "Outer.Inner.validate")}


def test_bound_method_alias_stays_in_its_function(tmp_path):
    results = resolve(tmp_path, """
class Service:
    def validate(self): pass
    def run(self):
        callback = self.validate
        callback()
    def other(self): callback()
""")
    assert pairs(results) == {("Service.run", "Service.validate")}
    assert next(result for result in results if result["caller"] == "Service.other")["target"] is None


def test_super_method_alias(tmp_path):
    results = resolve(tmp_path, """
class Parent:
    def __init__(self): pass
class Child(Parent):
    def __init__(self):
        initialize = super(Child, self).__init__
        initialize()
""")
    assert pairs(results) == {("Child.__init__", "Parent.__init__")}


def test_nested_class_constructor_through_self(tmp_path):
    results = resolve(tmp_path, """
class Outer:
    class Inner:
        def __init__(self): pass
    def run(self): self.Inner()
""")
    assert pairs(results) == {("Outer.run", "Outer.Inner.__init__")}


def test_alias_reassignment_and_parameter_shadowing(tmp_path):
    results = resolve(tmp_path, """
def helper(): pass
callback = helper
def first():
    callback = 1
    callback()
def second(callback): callback()
""")
    assert pairs(results) == set()


def test_inline_lambda_in_methods_keeps_class_owner(tmp_path):
    results = resolve(tmp_path, '''
class First:
    def run(self): return list(map(lambda value: value, [1]))
class Second:
    def run(self): return list(map(lambda value: value, [2]))
''')
    assert pairs(results) == {
        ('First.run', 'First.run.<lambda1>'),
        ('Second.run', 'Second.run.<lambda2>'),
    }


def test_inline_lambda_in_nested_method_function(tmp_path):
    results = resolve(tmp_path, '''
class Outer:
    class Inner:
        def run(self):
            def nested(): return list(map(lambda item: item, [1]))
            return nested()
''')
    assert ('Outer.Inner.run.nested', 'Outer.Inner.run.nested.<lambda1>') in pairs(results)


def test_unused_method_lambda_does_not_create_call(tmp_path):
    results = resolve(tmp_path, '''
class Service:
    def run(self): callback = lambda value: value
''')
    assert pairs(results) == set()

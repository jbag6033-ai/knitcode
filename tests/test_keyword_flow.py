from tests.test_value_flow import edges
from analyzer.resolver import CallResolver


def test_keyword_factory_is_forwarded_through_copy(tmp_path):
    result = edges(tmp_path, """
def first(): pass
def fallback(): pass
def copy(**kwargs): return dict(kwargs, ignored=True)
def choose(**kwargs):
    values = copy(**kwargs)
    return values.pop('factory', fallback)
def run():
    callback = choose(factory=first)
    callback()
""")
    assert ("run", "first") in result
    assert ("run", "fallback") not in result


def test_double_star_binds_explicit_parameter_without_kwargs(tmp_path):
    result = edges(tmp_path, """
def callback(): pass
def forward(function): return function
def run():
    selected = forward(**{'function': callback})
    selected()
""")
    assert ("run", "callback") in result


def test_setdefault_preserves_class_value(tmp_path):
    result = edges(tmp_path, """
class Service:
    def __init__(self): pass
    def run(self): pass
def main():
    values = {}
    factory = values.setdefault('factory', Service)
    instance = factory()
    instance.run()
""")
    assert ("main", "Service.__init__") in result
    assert ("main", "Service.run") in result


def test_type_of_self_can_be_forwarded_as_factory(tmp_path):
    result = edges(tmp_path, """
class Service:
    def __init__(self): pass
    def create(self):
        factory = type(self)
        return factory()
""")
    assert ("Service.create", "Service.__init__") in result


def test_tuple_unpacking_keeps_callable_positions(tmp_path):
    result = edges(tmp_path, """
def first(): pass
def second(): pass
def factory(): return (first, second)
def run():
    callback, ignored = factory()
    callback()
""")
    assert ("run", "first") in result
    assert ("run", "second") not in result


def test_starred_tuple_binds_arguments_in_order(tmp_path):
    result = edges(tmp_path, """
def first(): pass
def second(): pass
def forward(selected, ignored): return selected
def run():
    callback = forward(*(first, second))
    callback()
""")
    assert ("run", "first") in result
    assert ("run", "second") not in result


def test_guarded_duck_method_can_identify_project_provider(tmp_path):
    result = edges(tmp_path, """
class Provider:
    def children(self): pass
def run(value):
    try:
        callback = value.children
    except AttributeError:
        pass
    else:
        callback()
""")
    assert ("run", "Provider.children") in result


def test_recursive_keyword_forwarding_converges(tmp_path):
    (tmp_path / "main.py").write_text(
        "def first(**kwargs): return second(**kwargs)\n"
        "def second(**kwargs): return first(**kwargs)\n",
        encoding="utf-8",
    )
    resolver = CallResolver(tmp_path)
    resolver.analyze_project()
    resolver.resolve_calls()
    assert resolver.value_flow_status["converged"]


def test_constructor_candidates_respect_explicit_keyword_signature(tmp_path):
    result = edges(tmp_path, """
class Accept:
    def __init__(self, value): pass
class Reject:
    def __init__(self): pass
def run(flag):
    factory = Accept if flag else Reject
    factory(value=1)
""")
    assert ("run", "Accept.__init__") in result
    assert ("run", "Reject.__init__") not in result


def test_conditional_setdefault_does_not_guarantee_keyword(tmp_path):
    result = edges(tmp_path, """
class Accept:
    def __init__(self, value=1): pass
class Reject:
    def __init__(self): pass
def run(flag):
    options = {}
    if flag: options.setdefault('value', 1)
    factory = Accept if flag else Reject
    factory(**options)
""")
    assert ("run", "Reject.__init__") in result


def test_reassigned_mapping_does_not_retain_guaranteed_keyword(tmp_path):
    result = edges(tmp_path, """
class Accept:
    def __init__(self, value=1): pass
class Reject:
    def __init__(self): pass
def run(flag):
    options = {}
    options.setdefault('value', 1)
    options = {}
    factory = Accept if flag else Reject
    factory(**options)
""")
    assert ("run", "Reject.__init__") in result

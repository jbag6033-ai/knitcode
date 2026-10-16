from tests.test_value_flow import edges


def test_inherited_enter_preserves_child_receiver(tmp_path):
    result = edges(tmp_path, '''
class Base:
    def __enter__(self): return self
    def __exit__(self, *args): pass
class Left(Base):
    def work(self): pass
class Right(Base):
    def other(self): pass
def left_run():
    with Left() as left: left.work()
    left.other()
def right_run():
    with Right() as right: right.other()
    right.work()
''')
    assert ('left_run', 'Left.work') in result
    assert ('right_run', 'Right.other') in result
    assert ('left_run', 'Right.other') not in result
    assert ('right_run', 'Left.work') not in result


def test_explicit_class_method_keeps_receiver_argument(tmp_path):
    result = edges(tmp_path, '''
def callback(): pass
class Service:
    def apply(self, action): action()
def run(): Service.apply(Service(), callback)
''')
    assert ('Service.apply', 'callback') in result


def test_explicit_base_initializer_keeps_factory_position(tmp_path):
    result = edges(tmp_path, '''
class Product:
    def work(self): pass
class Base:
    def __init__(self, factory): self.factory = factory
    def make(self): return self.factory()
class Child(Base):
    def __init__(self): Base.__init__(self, Product)
def run():
    product = Child().make()
    product.work()
''')
    assert ('run', 'Product.work') in result


def test_staticmethod_argument_named_self_is_an_ordinary_parameter(tmp_path):
    result = edges(tmp_path, '''
def callback(): pass
class Service:
    @staticmethod
    def forward(self): return self
def run():
    selected = Service.forward(callback)
    selected()
''')
    assert ('run', 'callback') in result


def test_nested_function_parameter_self_is_not_a_bound_receiver(tmp_path):
    result = edges(tmp_path, '''
def callback(): pass
class Service:
    def run(self):
        def forward(self): return self
        selected = forward(callback)
        selected()
''')
    assert ('Service.run', 'callback') in result


def test_callable_instance_returns_factory_with_call_context(tmp_path):
    result = edges(tmp_path, '''
def first(): pass
def second(): pass
class Choose:
    def __call__(self, callback): return callback
def run():
    choose = Choose()
    a = choose(first)
    b = choose(second)
    a()
''')
    assert ('run', 'Choose.__call__') in result
    assert ('run', 'first') in result
    assert ('run', 'second') not in result


def test_mapping_values_preserve_callable_sequence(tmp_path):
    result = edges(tmp_path, '''
def callback(): pass
def run():
    mapping = {'key': callback}
    for action in mapping.values(): action()
''')
    assert ('run', 'callback') in result


def test_mapping_items_preserve_key_and_callable_columns(tmp_path):
    result = edges(tmp_path, '''
def callback(): pass
def run():
    mapping = {'key': callback}
    for key, action in mapping.items(): action()
''')
    assert ('run', 'callback') in result


def test_mapping_get_returns_default_only_when_key_is_missing(tmp_path):
    result = edges(tmp_path, '''
def chosen(): pass
def fallback(): pass
def missing(): pass
def run():
    mapping = {'key': chosen}
    a = mapping.get('key', fallback)
    b = mapping.get('absent', missing)
    a()
    b()
''')
    assert ('run', 'chosen') in result
    assert ('run', 'missing') in result
    assert ('run', 'fallback') not in result


def test_context_manager_enter_exit_and_bound_value(tmp_path):
    result = edges(tmp_path, '''
class Resource:
    def work(self): pass
class Manager:
    def __enter__(self): return Resource()
    def __exit__(self, *exc): pass
def run():
    with Manager() as resource:
        resource.work()
''')
    assert ('run', 'Manager.__enter__') in result
    assert ('run', 'Manager.__exit__') in result
    assert ('run', 'Resource.work') in result


def test_context_manager_without_as_still_has_protocol_calls(tmp_path):
    result = edges(tmp_path, '''
class Manager:
    def __enter__(self): pass
    def __exit__(self, *exc): pass
def run():
    with Manager(): pass
''')
    assert ('run', 'Manager.__enter__') in result
    assert ('run', 'Manager.__exit__') in result


def test_from_imported_module_resolves_class_and_context(tmp_path):
    package = tmp_path / 'pkg'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / 'resource.py').write_text('''
class Resource:
    def __init__(self): pass
    def work(self): pass
''')
    result = edges(tmp_path, '''
from pkg import resource as module
def run():
    instance = module.Resource()
    instance.work()
''')
    assert ('run', 'Resource.__init__') in result
    assert ('run', 'Resource.work') in result


def test_imported_nested_class_constructor(tmp_path):
    (tmp_path / 'outer.py').write_text('''
class Outer:
    class Inner:
        def __init__(self): pass
''')
    result = edges(tmp_path, '''
from outer import Outer
def run(): Outer.Inner()
''')
    assert ('run', 'Outer.Inner.__init__') in result


def test_same_line_context_binding_is_available_in_body(tmp_path):
    result = edges(tmp_path, '''
class Resource:
    def work(self): pass
class Manager:
    def __enter__(self): return Resource()
    def __exit__(self, *exc): pass
def run():
    with Manager() as resource: resource.work()
''')
    assert ('run', 'Resource.work') in result


def test_context_receiver_can_reuse_its_binding_name(tmp_path):
    result = edges(tmp_path, '''
class Resource:
    def work(self): pass
class Manager:
    def __enter__(self): return Resource()
    def __exit__(self, *exc): pass
def run():
    manager = Manager()
    with manager as manager:
        manager.work()
''')
    assert ('run', 'Manager.__enter__') in result
    assert ('run', 'Resource.work') in result


def test_same_line_reassignment_uses_latest_finished_value(tmp_path):
    result = edges(tmp_path, '''
def first(): pass
def second(): pass
def run():
    callback = first; callback = second; selected = callback
    selected()
''')
    assert ('run', 'second') in result
    assert ('run', 'first') not in result

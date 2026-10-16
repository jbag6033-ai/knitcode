import pytest

from tests.test_value_flow import edges


def test_builtin_name_does_not_bind_unrelated_method(tmp_path):
    result = edges(tmp_path, '''
class Connection:
    def open(self): pass
def run():
    open('data.txt')
''')
    assert ('run', 'Connection.open') not in result


def test_classmethod_constructs_its_class(tmp_path):
    result = edges(tmp_path, '''
class Group:
    def __init__(self): pass
    @classmethod
    def create(cls): return cls()
''')
    assert ('Group.create', 'Group.__init__') in result


def test_inherited_callable_list_reaches_callable_parameter(tmp_path):
    result = edges(tmp_path, '''
class Callback:
    def __call__(self, parser): parser.finish()
class Base:
    def __init__(self): self.actions = []
    def add(self, action): self.actions.append(action)
class Parser(Base):
    def finish(self): pass
    def execute(self):
        for action in self.actions: action(self)
def main():
    parser = Parser()
    parser.add(Callback())
    parser.execute()
''')
    assert ('Parser.execute', 'Callback.__call__') in result
    assert ('Callback.__call__', 'Parser.finish') in result


@pytest.mark.parametrize('expression', [
    '[callback for callback in [first]]',
    '{callback for callback in [first]}',
    '(callback for callback in [first])',
])
def test_comprehension_and_zip_keep_callback_positions(tmp_path, expression):
    result = edges(tmp_path, '''
def first(): pass
def second(): pass
def run():
    callbacks = EXPRESSION
    for callback, ignored in zip(callbacks, [second]):
        callback()
'''.replace('EXPRESSION', expression))
    assert ('run', 'first') in result
    assert ('run', 'second') not in result


def test_property_read_invokes_getter_and_propagates_return(tmp_path):
    result = edges(tmp_path, '''
class Resource:
    def work(self): pass
class Holder:
    @property
    def resource(self): return Resource()
    def run(self): self.resource.work()
''')
    assert ('Holder.run', 'Holder.resource') in result
    assert ('Holder.run', 'Resource.work') in result


def test_property_reference_on_class_does_not_invoke_getter(tmp_path):
    result = edges(tmp_path, '''
class Holder:
    @property
    def resource(self): pass
def run():
    descriptor = Holder.resource
''')
    assert ('run', 'Holder.resource') not in result


def test_attribute_write_through_argument_is_visible(tmp_path):
    result = edges(tmp_path, '''
class Action:
    def run(self): self.container.finish()
class Container:
    def finish(self): pass
    def add(self, action): action.container = self
def main():
    action = Action()
    container = Container()
    container.add(action)
    action.run()
''')
    assert ('Action.run', 'Container.finish') in result


def test_registry_namespaces_do_not_mix_pooled_parameter_values(tmp_path):
    result = edges(tmp_path, '''
def first(): pass
def second(): pass
class Registry:
    def __init__(self):
        self.entries = {}
        self.register('one', first)
        self.register('two', second)
    def register(self, name, callback):
        mapping = self.entries.setdefault(name, {})
        mapping['default'] = callback
    def lookup(self, name): return self.entries[name]['default']
    def run(self):
        callback = self.lookup('one')
        callback()
''')
    assert ('Registry.run', 'first') in result
    assert ('Registry.run', 'second') not in result

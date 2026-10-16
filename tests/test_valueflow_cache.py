import ast

import pytest

from analyzer.resolver import CallResolver
from analyzer.value_flow import ValueFlow


@pytest.mark.parametrize('source', [
    '''
def first(): pass
def second(): pass
def copy(**kwargs): return dict(kwargs)
def choose(**kwargs): return copy(**kwargs).get('callback', second)
def run():
    callback = choose(callback=first)
    callback()
''',
    '''
class Resource:
    def work(self): pass
class Manager:
    def __enter__(self): return Resource()
    def __exit__(self, *exc): pass
def run():
    with Manager() as resource: resource.work()
''',
    '''
def first(**kwargs): return second(**kwargs)
def second(**kwargs): return first(**kwargs)
''',
])
def test_static_cache_matches_uncached_flow_including_convergence(tmp_path, source):
    (tmp_path / 'main.py').write_text(source)
    resolver = CallResolver(tmp_path)
    resolver.analyze_project()
    cached = ValueFlow(resolver)
    plain = ValueFlow(resolver, cache_static=False)
    assert cached.analyze() == plain.analyze()
    assert cached.state() == plain.state()
    assert (cached.iterations, cached.converged) == (plain.iterations, plain.converged)
    assert any(info['hits'] for info in cached.cache_info().values())
    assert plain.cache_info() == {}


def test_static_cache_does_not_cache_mutable_argument_values(tmp_path):
    (tmp_path / 'main.py').write_text('''
def first(): pass
def second(): pass
def run(callback): return callback
''')
    resolver = CallResolver(tmp_path)
    resolver.analyze_project()
    flow = ValueFlow(resolver)
    expression = resolver.file_results['main.py'].return_expressions['run'][0]
    flow.inputs[('main.py', 'run')]['callback'].add(('function', 'main.py', 'first'))
    assert flow.expression('main.py', 'run', expression) == {('function', 'main.py', 'first')}
    flow.inputs[('main.py', 'run')]['callback'].add(('function', 'main.py', 'second'))
    assert flow.expression('main.py', 'run', expression) == {
        ('function', 'main.py', 'first'), ('function', 'main.py', 'second')}
    assert flow.cache_info()['receiver']['hits'] > 0


def test_metadata_cache_does_not_leak_between_project_analyses(tmp_path):
    path = tmp_path / 'main.py'
    path.write_text('class Service:\n    def first(self): pass\n')
    first_resolver = CallResolver(tmp_path)
    first_resolver.analyze_project()
    first = ValueFlow(first_resolver)
    assert first.resolve_method('main.py', 'Service', 'first') is not None
    assert first.resolve_method('main.py', 'Service', 'second') is None
    path.write_text('class Service:\n    def second(self): pass\n')
    second_resolver = CallResolver(tmp_path)
    second_resolver.analyze_project()
    second = ValueFlow(second_resolver)
    assert second.resolve_method('main.py', 'Service', 'first') is None
    assert second.resolve_method('main.py', 'Service', 'second') is not None
    assert isinstance(first.named('main.py', '<module>', 'Service'), frozenset)

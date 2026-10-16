import pytest

from analyzer.resolver import CallResolver
from backend.export import export_project


def setup(tmp_path, parameter='writer', class_name='Concrete'):
    (tmp_path / 'main.py').write_text('''
class Base:
    def notify(self): pass
class Concrete(Base):
    def write(self): pass
def public(writer):
    def nested():
        writer.write()
        writer.notify()
    nested()
def other(writer): writer.write()
''')
    return {'version': 1, 'entrypoints': [{'file': 'main.py', 'function': 'public',
                                         'parameters': {parameter: [{'file': 'main.py', 'class': class_name}]}}]}


def test_explicit_inputs_reach_nested_calls_without_leaking(tmp_path):
    config = setup(tmp_path)
    resolver = CallResolver(tmp_path, entrypoints=config)
    resolver.analyze_project()
    calls = resolver.resolve_calls()
    found = {(c['caller'], c['target'].get('class'), c['target']['name']) for c in calls if c['target']}
    assert ('public.nested', 'Concrete', 'write') in found
    assert ('public.nested', 'Base', 'notify') in found
    assert ('other', 'Concrete', 'write') not in found
    assert not any(c['target'] and c['target']['name'] == '__init__' for c in calls)


def test_default_analysis_does_not_invent_external_inputs(tmp_path):
    setup(tmp_path)
    resolver = CallResolver(tmp_path)
    resolver.analyze_project()
    assert not any(c['target'] and c['target']['name'] in {'write', 'notify'} for c in resolver.resolve_calls())


@pytest.mark.parametrize('parameter,class_name', [('typo', 'Concrete'), ('writer', 'Missing')])
def test_invalid_contract_fails_instead_of_guessing(tmp_path, parameter, class_name):
    config = setup(tmp_path, parameter, class_name)
    resolver = CallResolver(tmp_path, entrypoints=config)
    resolver.analyze_project()
    with pytest.raises(ValueError):
        resolver.resolve_calls()


def test_export_accepts_input_contract(tmp_path):
    config = setup(tmp_path)
    data = export_project(tmp_path, entrypoints=config)
    assert data['entrypoints'] == config
    assert any(e['source'] == 'main.py::public.nested' and e['target'] == 'main.py::Concrete.write' for e in data['edges'])


@pytest.mark.parametrize('fault', ['version', 'function', 'path', 'shape'])
def test_malformed_contract_has_actionable_error(tmp_path, fault):
    config = setup(tmp_path)
    if fault == 'version':
        config['version'] = 2
    elif fault == 'function':
        config['entrypoints'][0]['function'] = 'missing'
    elif fault == 'path':
        config['entrypoints'][0]['parameters']['writer'][0]['file'] = '../outside.py'
    else:
        config['entrypoints'][0]['parameters'] = []
    resolver = CallResolver(tmp_path, entrypoints=config)
    resolver.analyze_project()
    with pytest.raises(ValueError):
        resolver.resolve_calls()

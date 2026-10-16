from tests.test_value_flow import edges


TEMPLATE = '''
class Service:
    def __init__(self, mode='first'): self.mode = CONFIG
    def _route_first_done(self): pass
    def _route_second_done(self): pass
    def _route_unrelated(self): pass
    def select(self):
        attribute = '_route_%s_done' % self.mode
        try:
            return getattr(self, attribute)
        except AttributeError:
            raise ValueError('invalid mode')
    def execute(self):
        selected = self.select()
        selected()
class Other:
    def _route_third_done(self): pass
'''


def test_constructor_configured_guarded_dispatch_stays_in_method_family(tmp_path):
    result = edges(tmp_path, TEMPLATE.replace('CONFIG', 'mode'))
    assert ('Service.execute', 'Service._route_first_done') in result
    assert ('Service.execute', 'Service._route_second_done') in result
    assert ('Service.execute', 'Service._route_unrelated') not in result
    assert ('Service.execute', 'Other._route_third_done') not in result


def test_fixed_literal_field_does_not_expand_dispatch(tmp_path):
    result = edges(tmp_path, TEMPLATE.replace('CONFIG', "'first'"))
    assert ('Service.execute', 'Service._route_first_done') in result
    assert ('Service.execute', 'Service._route_second_done') not in result


def test_unguarded_getattr_does_not_expand_dispatch(tmp_path):
    source = TEMPLATE.replace('CONFIG', 'mode').replace('''        try:
            return getattr(self, attribute)
        except AttributeError:
            raise ValueError('invalid mode')''', '''        return getattr(self, attribute)''')
    result = edges(tmp_path, source)
    assert ('Service.execute', 'Service._route_first_done') in result
    assert ('Service.execute', 'Service._route_second_done') not in result


def test_guard_without_constructor_parameter_provenance_is_not_enough(tmp_path):
    result = edges(tmp_path, '''
class Service:
    def first(self): pass
    def second(self): pass
    def select(self, attribute):
        try:
            return getattr(self, attribute)
        except AttributeError:
            pass
    def execute(self):
        callback = self.select('first')
        callback()
''')
    assert ('Service.execute', 'Service.first') in result
    assert ('Service.execute', 'Service.second') not in result


def test_reassigned_constructor_parameter_does_not_expand_dispatch(tmp_path):
    source = TEMPLATE.replace('CONFIG', 'mode').replace(
        "def __init__(self, mode='first'): self.mode = mode",
        "def __init__(self, mode='first'):\n        mode = 'first'\n        self.mode = mode")
    result = edges(tmp_path, source)
    assert ('Service.execute', 'Service._route_first_done') in result
    assert ('Service.execute', 'Service._route_second_done') not in result


def test_unstructured_name_does_not_enumerate_all_methods(tmp_path):
    source = TEMPLATE.replace('CONFIG', 'mode').replace("'_route_%s_done'", "'%s'")
    result = edges(tmp_path, source)
    assert ('Service.execute', 'Service._route_second_done') not in result


def test_guarded_bare_return_does_not_crash(tmp_path):
    result = edges(tmp_path, '''
def run():
    try:
        return
    except AttributeError:
        pass
''')
    assert result == set()


def test_getattr_parameter_override_does_not_create_builtin_dispatch_edges(tmp_path):
    source = 'def replacement(receiver, attribute): return None\n' + TEMPLATE.replace('CONFIG', 'mode').replace(
        'def select(self):', 'def select(self, getattr=replacement):')
    result = edges(tmp_path, source)
    assert ('Service.execute', 'Service._route_first_done') not in result
    assert ('Service.execute', 'Service._route_second_done') not in result

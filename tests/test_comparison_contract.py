from analyzer.comparison import compare_pairs, declared_symbols, project_declared_functions
from analyzer.resolver import CallResolver


def test_projection_is_symmetric_and_lists_every_exclusion():
    symbols = {'modules': {'pkg'}, 'functions': {'pkg.run', 'pkg.C.__call__'}, 'classes': {'pkg.C'}}
    truth = {('pkg.run', 'pkg.C.__init__'), ('pkg.run', 'pkg.C')}
    predicted = {('pkg.run', 'pkg.C.__call__'), ('pkg.run', 'pkg.C')}
    projected_truth, excluded_truth = project_declared_functions(truth, symbols)
    projected_predicted, excluded_predicted = project_declared_functions(predicted, symbols)
    assert not projected_truth
    assert projected_predicted == {('pkg.run', 'pkg.C.__call__')}
    assert len(excluded_truth) == 2 and len(excluded_predicted) == 1
    assert {reason for row in excluded_truth for reason in row['reasons']} == {
        'target_not_declared_function', 'target_is_class'}
    # Raw truth remains unchanged; __call__ is not rewritten to a constructor.
    assert ('pkg.run', 'pkg.C.__init__') in truth
    _, diff = compare_pairs(projected_truth, projected_predicted)
    assert diff['false_positive'] == [('pkg.run', 'pkg.C.__call__')]


def test_projection_keeps_real_getters_and_rejects_undeclared_callers(tmp_path):
    (tmp_path / 'main.py').write_text('''
class C:
    @property
    def value(self): return 1
    def run(self): return self.value
''')
    resolver = CallResolver(tmp_path)
    resolver.analyze_project()
    symbols = declared_symbols(resolver, 'pkg')
    getter = ('pkg.main.C.run', 'pkg.main.C.value')
    missing = ('pkg.main.Missing.run', 'pkg.main.C.value')
    included, excluded = project_declared_functions({getter, missing}, symbols)
    assert included == {getter}
    assert excluded == [{'caller': missing[0], 'target': missing[1],
                         'reasons': ['caller_not_declared_scope']}]


def test_raw_comparison_counts_unique_pairs():
    metrics, diff = compare_pairs([('a', 'b'), ('a', 'b')], [('a', 'b'), ('a', 'c')])
    assert (metrics['tp'], metrics['fp'], metrics['fn']) == (1, 1, 0)
    assert metrics['precision'] == 0.5
    assert diff['false_positive'] == [('a', 'c')]

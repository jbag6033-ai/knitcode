"""Explicit call-graph comparison contracts; never rewrite symbol names."""
from pathlib import Path

from analyzer.evaluate import make_qualified_name


def compare_pairs(truth, predicted):
    truth, predicted = set(truth), set(predicted)
    tp, fp, fn = predicted & truth, predicted - truth, truth - predicted
    precision = len(tp) / len(predicted) if predicted else 0
    recall = len(tp) / len(truth) if truth else 0
    return {
        'ground_truth_edges': len(truth), 'predicted_edges': len(predicted),
        'tp': len(tp), 'fp': len(fp), 'fn': len(fn),
        'precision': precision, 'recall': recall,
        'f1': 2 * precision * recall / (precision + recall) if precision + recall else 0,
    }, {'true_positive': sorted(tp), 'false_positive': sorted(fp), 'false_negative': sorted(fn)}


def declared_symbols(resolver, prefix=''):
    def qualified(file, name):
        file = str(Path(prefix) / file) if prefix else file
        return make_qualified_name(file, name)
    modules = {qualified(file, '<module>') for file in resolver.file_results}
    functions = set()
    for definitions in resolver.function_definitions.values():
        for definition in definitions:
            name = definition['name']
            if definition.get('class'):
                name = definition['class'] + '.' + name
            functions.add(qualified(definition['file'], name))
    classes = {qualified(d['file'], d['name'])
               for group in resolver.class_definitions.values() for d in group}
    return {'modules': modules, 'functions': functions, 'classes': classes}


def project_declared_functions(edges, symbols):
    """Keep declared callers and function targets on BOTH sides of comparison.

    Classes remain in the product graph. No project-specific exception list,
    spelling correction, constructor substitution, or property omission.
    """
    scopes = symbols['functions'] | symbols['modules']
    included, excluded = set(), []
    for caller, target in sorted(set(edges)):
        reasons = []
        if caller not in scopes:
            reasons.append('caller_not_declared_scope')
        if target not in symbols['functions']:
            reasons.append('target_is_class' if target in symbols['classes'] else
                           'target_is_module' if target in symbols['modules'] else
                           'target_not_declared_function')
        if reasons:
            excluded.append({'caller': caller, 'target': target, 'reasons': reasons})
        else:
            included.add((caller, target))
    return included, excluded

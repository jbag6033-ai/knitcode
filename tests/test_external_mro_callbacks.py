"""Source-verified external MRO barriers and explicit builtin callbacks."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from ast_parser import scan_repository
from symbol_builder import build_symbol_result
from graph_builder import build_graph
from unresolved_classifier import reclassify_graph
from call_status import annotate_call_statuses
from verify_v23 import verify
from verify_v231 import check_status


class ExternalMROCallbackTests(unittest.TestCase):
    def graph(self, source, extra=None):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'project';root.mkdir()
            for name,code in {'app.py':textwrap.dedent(source),**(extra or {})}.items():
                (root/name).write_text(code)
            facts=scan_repository(root)
            self.assertEqual(facts['parse_errors'],[])
            symbols=build_symbol_result(facts)
            graph=annotate_call_statuses(reclassify_graph(build_graph(symbols),symbols),symbols)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(verify(graph,symbols),0)
            self.assertEqual(check_status(graph,symbols),0)
        return graph

    def targets(self, source, callee, extra=None):
        g=self.graph(source,extra)
        rows=[r for r in g['call_statuses'] if r['callee_text']==callee]
        self.assertEqual(len(rows),1)
        return set(rows[0]['target_ids'])

    def test_known_external_parent_allows_internal_sibling_method(self):
        self.assertEqual(self.targets('''
            import multiprocessing as mp
            class Internal:
                def work(self): pass
            class Worker(mp.Process,Internal): pass
            def go():
                obj=Worker(); obj.work()
        ''','obj.work'),{'METHOD:app.Internal.work'})

    def test_external_descriptor_is_not_skipped(self):
        self.assertEqual(self.targets('''
            from multiprocessing import Process
            class Internal:
                def run(self): pass
            class Worker(Process,Internal): pass
            def go():
                obj=Worker(); obj.run()
        ''','obj.run'),set())

    def test_internal_first_base_still_wins(self):
        self.assertEqual(self.targets('''
            from multiprocessing import Process
            class Internal:
                def run(self): pass
            class Worker(Internal,Process): pass
            def go():
                obj=Worker(); obj.run()
        ''','obj.run'),{'METHOD:app.Internal.run'})

    def test_super_reaches_known_internal_constructor(self):
        self.assertEqual(self.targets('''
            from multiprocessing import Process
            class Parent(Process):
                def __init__(self): pass
            class Child(Parent):
                def __init__(self): super(Child,self).__init__()
        ''','super().__init__'),{'METHOD:app.Parent.__init__'})

    def test_super_stops_at_external_method(self):
        self.assertEqual(self.targets('''
            from multiprocessing import Process
            class Internal:
                def run(self): pass
            class Worker(Process,Internal):
                def go(self): super().run()
        ''','super().run'),set())

    def test_patched_external_member_invalidates_model(self):
        self.assertEqual(self.targets('''
            import multiprocessing as mp
            mp.Process.work=unknown
            class Internal:
                def work(self): pass
            class Worker(mp.Process,Internal): pass
            def go():
                obj=Worker(); obj.work()
        ''','obj.work'),set())

    def test_external_class_alias_patch_invalidates_model(self):
        self.assertEqual(self.targets('''
            import multiprocessing as mp
            P=mp.Process
            P.work=unknown
            class Internal:
                def work(self): pass
            class Worker(mp.Process,Internal): pass
            def go():
                obj=Worker(); obj.work()
        ''','obj.work'),set())

    def test_dead_platform_patch_does_not_invalidate_model(self):
        self.assertEqual(self.targets('''
            import multiprocessing as mp
            import sys
            if sys.platform.startswith('__impossible_platform__'):
                mp.Process=unknown
            class Internal:
                def work(self): pass
            class Worker(mp.Process,Internal): pass
            def go():
                obj=Worker(); obj.work()
        ''','obj.work'),{'METHOD:app.Internal.work'})

    def test_unrecognized_stdlib_layout_stays_unknown(self):
        with patch('stdlib_mro.multiprocessing_contract',return_value=({},[])):
            self.assertEqual(self.targets('''
                from multiprocessing import Process
                class Internal:
                    def work(self): pass
                class Worker(Process,Internal): pass
                def go():
                    obj=Worker(); obj.work()
            ''','obj.work'),set())

    def test_conditional_import_cannot_use_stdlib_contract(self):
        self.assertEqual(self.targets('''
            if flag:
                from multiprocessing import Process
            class Internal:
                def work(self): pass
            class Worker(Process,Internal): pass
            def go():
                obj=Worker(); obj.work()
        ''','obj.work'),set())

    def test_local_stdlib_namesake_is_not_trusted(self):
        self.assertEqual(self.targets('''
            import multiprocessing as mp
            class Internal:
                def work(self): pass
            class Worker(mp.Process,Internal): pass
            def go():
                obj=Worker(); obj.work()
        ''','obj.work',{'multiprocessing.py':'class Process(Unknown): pass\n'}),set())

    def callbacks(self,g):
        return [e for e in g['edges'] if e['evidence'].get('callback_call_id')]

    def test_sorted_lambda_callback_has_separate_trigger(self):
        g=self.graph('def go(values):\n    return sorted(values,key=lambda x:x)\n')
        edges=self.callbacks(g)
        self.assertEqual(len(edges),1)
        self.assertTrue(edges[0]['target'].startswith('LAMBDA:app.go.'))
        self.assertEqual(edges[0]['source'],'FUNCTION:app.go')
        self.assertEqual(edges[0]['evidence']['certainty'],'callback_may_execute')
        self.assertIsNone(edges[0]['evidence']['call_id'])
        self.assertEqual(next(r for r in g['call_statuses'] if r['callee_text']=='sorted')['status'],'KNOWN_NON_INTERNAL')

    def test_named_key_callback_is_not_omitted_to_match_benchmark(self):
        g=self.graph('def key(x): return x\ndef go(values): return sorted(values,key=key)\n')
        self.assertEqual([e['target'] for e in self.callbacks(g)],['FUNCTION:app.key'])

    def test_arbitrary_lambda_argument_is_not_assumed_invoked(self):
        g=self.graph('def go(external): external(lambda x:x)\n')
        self.assertEqual(self.callbacks(g),[])
        self.assertFalse(any(e['target'].startswith('LAMBDA:') for e in g['edges']))

    def test_shadowed_sorted_does_not_get_builtin_callback_semantics(self):
        for code in ['def sorted(values,key=None): return values\ndef go(v): return sorted(v,key=lambda x:x)\n',
                     'def go(sorted,v): return sorted(v,key=lambda x:x)\n']:
            with self.subTest(code=code):
                self.assertEqual(self.callbacks(self.graph(code)),[])

    def test_empty_sorted_input_has_no_callback(self):
        for source in ['[]','()','{}',"''"]:
            with self.subTest(source=source):
                self.assertEqual(self.callbacks(self.graph(f'def go(): return sorted({source},key=lambda x:x)\n')),[])

    def test_direct_lambda_call_resolves_without_evaluating_body(self):
        ts=self.targets('def go():\n    fn=lambda x:x\n    fn(1)\n','fn')
        self.assertEqual(len(ts),1)
        self.assertTrue(next(iter(ts)).startswith('LAMBDA:app.go.'))

    def test_uninvoked_lambda_does_not_add_call_to_lambda(self):
        g=self.graph('def go(): return lambda x:x\n')
        self.assertFalse(any(e['target'].startswith('LAMBDA:') and e['type']=='CALLS' for e in g['edges']))

    def test_two_callback_sites_are_not_deduplicated(self):
        g=self.graph('def key(x): return x\ndef go(v):\n    sorted(v,key=key)\n    sorted(v,key=key)\n')
        self.assertEqual(len(self.callbacks(g)),2)

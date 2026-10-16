import pytest

from tests.test_value_flow import edges


def test_namespace_keeps_defaults_at_parse_time(tmp_path):
    source = '''
import argparse
observed = []
def before(): observed.append('before')
def after(): observed.append('after')
def build():
    parser = argparse.ArgumentParser()
    parser.set_defaults(cmd=before)
    first = parser.parse_args([])
    parser.set_defaults(cmd=after)
    second = parser.parse_args([])
    return first, second
def first_run():
    first, second = build()
    first.cmd()
def second_run():
    first, second = build()
    second.cmd()
'''
    result = edges(tmp_path, source)
    namespace = {}
    exec(compile(source, str(tmp_path / 'main.py'), 'exec'), namespace)
    namespace['first_run']()
    namespace['second_run']()
    assert namespace['observed'] == ['before', 'after']
    assert ('first_run', 'before') in result
    assert ('first_run', 'after') not in result
    assert ('second_run', 'after') in result
    assert ('second_run', 'before') not in result


def test_selected_child_snapshot_does_not_follow_later_override(tmp_path):
    source = '''
import argparse
observed = []
def parent(): observed.append('parent')
def before(): observed.append('before')
def after(): observed.append('after')
def build():
    parser = argparse.ArgumentParser()
    parser.set_defaults(cmd=parent)
    sub = parser.add_subparsers()
    child = sub.add_parser('child', aliases=['c'])
    child.set_defaults(cmd=before)
    first = parser.parse_args(['c'])
    child.set_defaults(cmd=after)
    second = parser.parse_args(['child'])
    return first, second
def first_run():
    first, second = build()
    first.cmd()
def second_run():
    first, second = build()
    second.cmd()
'''
    result = edges(tmp_path, source)
    namespace = {}
    exec(compile(source, str(tmp_path / 'main.py'), 'exec'), namespace)
    namespace['first_run']()
    namespace['second_run']()
    assert namespace['observed'] == ['before', 'after']
    assert {target for caller, target in result if caller == 'first_run' and target in {'parent', 'before', 'after'}} == {'before'}
    assert {target for caller, target in result if caller == 'second_run' and target in {'parent', 'before', 'after'}} == {'after'}


def test_argparse_commands_flow_through_namespace(tmp_path):
    result = edges(tmp_path, '''
import argparse as ap
class Command:
    def __init__(self): pass
    def execute(self): pass
def main():
    parser = ap.ArgumentParser()
    subparsers = parser.add_subparsers()
    child = subparsers.add_parser('run')
    child.set_defaults(cmd=Command)
    args = parser.parse_args()
    command = args.cmd()
    command.execute()
''')
    assert ('main', 'Command.__init__') in result
    assert ('main', 'Command.execute') in result


def test_argparse_independent_roots_do_not_mix(tmp_path):
    result = edges(tmp_path, '''
from argparse import ArgumentParser as Parser
def left(): pass
def right(): pass
def choose_left():
    a = Parser()
    b = Parser()
    a.set_defaults(cmd=left)
    b.set_defaults(cmd=right)
    args = a.parse_args()
    args.cmd()
''')
    assert ('choose_left', 'left') in result
    assert ('choose_left', 'right') not in result


def test_argparse_parameter_shadow_does_not_activate_model(tmp_path):
    result = edges(tmp_path, '''
import argparse
def target(): pass
def run(argparse):
    parser = argparse.ArgumentParser()
    parser.set_defaults(cmd=target)
    args = parser.parse_args()
    args.cmd()
''')
    assert ('run', 'target') not in result


def test_argparse_explicit_argv_does_not_pool_commands(tmp_path):
    result = edges(tmp_path, '''
import argparse
def target(): pass
def run():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    child = sub.add_parser('go')
    child.set_defaults(cmd=target)
    args = parser.parse_args([])
    args.cmd()
''')
    assert ('run', 'target') not in result


def test_unrelated_parser_api_does_not_activate_stdlib_model(tmp_path):
    result = edges(tmp_path, '''
from external import ArgumentParser
def target(): pass
def run():
    parser = ArgumentParser()
    parser.set_defaults(cmd=target)
    args = parser.parse_args()
    args.cmd()
''')
    assert ('run', 'target') not in result


def test_later_default_replaces_previous_command(tmp_path):
    result = edges(tmp_path, '''
import argparse
def old(): pass
def current(): pass
def run():
    parser = argparse.ArgumentParser()
    parser.set_defaults(cmd=old)
    parser.set_defaults(cmd=current)
    args = parser.parse_args()
    args.cmd()
''')
    assert ('run', 'current') in result
    assert ('run', 'old') not in result


def test_explicit_argv_selects_only_matching_command(tmp_path):
    result = edges(tmp_path, '''
import argparse
def left(): pass
def right(): pass
def run():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    a = sub.add_parser('left')
    b = sub.add_parser('right')
    a.set_defaults(cmd=left)
    b.set_defaults(cmd=right)
    argv = ['left']
    args = parser.parse_args(args=argv)
    args.cmd()
''')
    assert ('run', 'left') in result
    assert ('run', 'right') not in result


def test_nested_subcommand_alias_and_child_override(tmp_path):
    result = edges(tmp_path, '''
import argparse
def parent(): pass
def leaf(): pass
def sibling(): pass
def run():
    parser = argparse.ArgumentParser()
    parser.set_defaults(cmd=parent)
    sub = parser.add_subparsers()
    group = sub.add_parser('group', aliases=['g'])
    nested = group.add_subparsers()
    child = nested.add_parser('leaf')
    other = nested.add_parser('other')
    child.set_defaults(cmd=leaf)
    other.set_defaults(cmd=sibling)
    args = parser.parse_args(('g', 'leaf'))
    args.cmd()
''')
    assert ('run', 'leaf') in result
    assert ('run', 'parent') not in result
    assert ('run', 'sibling') not in result


def test_parser_factory_calls_keep_defaults_separate(tmp_path):
    result = edges(tmp_path, '''
import argparse
def left(): pass
def right(): pass
def make(command):
    parser = argparse.ArgumentParser()
    parser.set_defaults(cmd=command)
    return parser
def left_run():
    parser = make(left)
    args = parser.parse_args([])
    args.cmd()
def right_run():
    parser = make(right)
    args = parser.parse_args([])
    args.cmd()
''')
    assert ('left_run', 'left') in result
    assert ('right_run', 'right') in result
    assert ('left_run', 'right') not in result
    assert ('right_run', 'left') not in result


def test_unknown_conditional_defaults_preserve_both_branches(tmp_path):
    result = edges(tmp_path, '''
import argparse
def left(): pass
def right(): pass
def run(flag):
    parser = argparse.ArgumentParser()
    if flag:
        parser.set_defaults(cmd=left)
    else:
        parser.set_defaults(cmd=right)
    args = parser.parse_args([])
    args.cmd()
''')
    assert ('run', 'left') in result
    assert ('run', 'right') in result


def test_invalid_command_does_not_invent_dispatch(tmp_path):
    result = edges(tmp_path, '''
import argparse
def command(): pass
def run():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    child = sub.add_parser('known')
    child.set_defaults(cmd=command)
    args = parser.parse_args(['invalid'])
    args.cmd()
''')
    assert ('run', 'command') not in result


def test_factory_known_condition_selects_correct_registration(tmp_path):
    result = edges(tmp_path, '''
import argparse
def left(): pass
def right(): pass
def make(flag):
    parser = argparse.ArgumentParser()
    if flag:
        parser.set_defaults(cmd=left)
    else:
        parser.set_defaults(cmd=right)
    return parser
def left_run():
    args = make(True).parse_args([])
    args.cmd()
def right_run():
    args = make(False).parse_args([])
    args.cmd()
''')
    assert ('left_run', 'left') in result
    assert ('right_run', 'right') in result
    assert ('left_run', 'right') not in result
    assert ('right_run', 'left') not in result


@pytest.mark.parametrize('argv, expected', [([], 'fallback'), (['left'], 'left'), (['l'], 'left'), (['right'], 'right')])
def test_known_selection_agrees_with_real_argparse(tmp_path, argv, expected):
    source = '''
import argparse
observed = []
def fallback(): observed.append('fallback')
def left(): observed.append('left')
def right(): observed.append('right')
def run():
    parser = argparse.ArgumentParser()
    parser.set_defaults(cmd=fallback)
    sub = parser.add_subparsers()
    a = sub.add_parser('left', aliases=['l'])
    b = sub.add_parser('right')
    a.set_defaults(cmd=left)
    b.set_defaults(cmd=right)
    args = parser.parse_args(ARGV)
    args.cmd()
'''.replace('ARGV', repr(argv))
    result = edges(tmp_path, source)
    namespace = {}
    exec(compile(source, str(tmp_path / 'main.py'), 'exec'), namespace)
    namespace['run']()
    assert namespace['observed'] == [expected]
    assert {name for caller, name in result if caller == 'run' and name in {'fallback', 'left', 'right'}} == {expected}

import pytest

from analyzer.resolver import CallResolver


def analyze(tmp_path, files):
    for name, source in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    resolver = CallResolver(tmp_path)
    resolver.analyze_project()
    return resolver.resolve_calls()


def test_relative_import_from_package_reexport(tmp_path):
    results = analyze(tmp_path, {
        "__init__.py": "from .connection import Connection\n",
        "connection.py": "class Connection:\n    def __init__(self): pass\n",
        "executor.py": "from . import Connection\ndef run(): Connection()\n",
    })
    target = results[0]["target"]
    assert (target["file"], target["name"]) == ("connection.py", "__init__")


def test_cross_file_parent_and_super(tmp_path):
    results = analyze(tmp_path, {
        "base.py": "class Parent:\n    def work(self): pass\n",
        "pkg/__init__.py": "",
        "pkg/child.py": "from ..base import Parent as Base\nclass Child(Base):\n    def run(self):\n        self.work()\n        super().work()\n",
    })
    targets = [r["target"] for r in results if r["callee"].endswith(".work")]
    assert len(targets) == 2
    assert all(t and t["file"] == "base.py" and t["class"] == "Parent" for t in targets)


def test_external_qualified_parent_does_not_bind_local_namesake(tmp_path):
    results = analyze(tmp_path, {
        "main.py": "import external\nclass Builder(external.Builder):\n    def __init__(self): super().__init__()\n",
    })
    assert all(r["target"] is None for r in results)


def test_reexport_cycle_terminates(tmp_path):
    results = analyze(tmp_path, {
        "__init__.py": "from .a import Unknown\n",
        "a.py": "from . import Unknown\ndef run(): Unknown()\n",
    })
    assert results[0]["target"] is None


@pytest.mark.parametrize('statement,call', [
    ('import pkg.sub.worker', 'pkg.sub.worker.run()'),
    ('import pkg.sub.worker as alias', 'alias.run()'),
    ('import pkg.sub as alias', 'alias.run()'),
    ('import pkg', 'pkg.sub.worker.run()'),
])
def test_dotted_module_import_and_reexport_calls(tmp_path, statement, call):
    results = analyze(tmp_path, {
        'pkg/__init__.py': '',
        'pkg/sub/__init__.py': 'from .worker import run\n',
        'pkg/sub/worker.py': 'def run(): pass\n',
        'main.py': statement + '\n' + call + '\n',
    })
    calls = results
    assert len(calls) == 1
    assert all(r['target'] and r['target']['file'] == 'pkg/sub/worker.py' and r['target']['name'] == 'run' for r in calls)


def test_dotted_import_does_not_guess_external_or_unbound_alias(tmp_path):
    results = analyze(tmp_path, {
        'pkg/sub.py': 'def run(): pass\n',
        'other.py': 'def run(): pass\n',
        'main.py': 'import external.sub\nimport pkg.sub as alias\nexternal.sub.run()\npkg.sub.run()\n',
    })
    assert all(r['target'] is None for r in results)


def test_module_function_lookup_does_not_bind_class_method(tmp_path):
    results = analyze(tmp_path, {
        'pkg/sub.py': 'class Service:\n    def run(self): pass\n',
        'main.py': 'import pkg.sub\npkg.sub.run()\n',
    })
    assert all(r['target'] is None for r in results)

import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

from backend.export import export_project
from git_analyzer.history import read_history
from scripts.package_extension import package


def test_export_includes_isolated_definitions_and_skips_invalid_and_venv(tmp_path):
    (tmp_path / 'main.py').write_text('def isolated():\n    pass\n\ndef caller():\n    isolated()\n')
    (tmp_path / 'broken.py').write_text('def broken(')
    env = tmp_path / 'myenv'
    env.mkdir()
    (env / 'pyvenv.cfg').write_text('')
    (env / 'noise.py').write_text('def noise(): pass')
    data = export_project(tmp_path)
    assert data['summary'] == {'files': 1, 'resolved': 1, 'unresolved': 0}
    assert len(data['warnings']) == 1
    isolated = next(n for n in data['nodes'] if n['id'] == 'main.py::isolated')
    assert isolated['callers'] == 1
    assert not data['history']['available']
    ids = {n['id'] for n in data['nodes']}
    assert all(e['source'] in ids and e['target'] in ids for e in data['edges'])
    json.dumps(data)


def test_history_cochange_in_subfolder(tmp_path):
    def git(*args):
        return subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    git('init')
    project = tmp_path / 'app'
    project.mkdir()
    for i in range(2):
        for name in ('a.py', 'b.py'):
            (project / name).write_text(f'value = {i}\n')
        git('add', '.')
        git('-c', 'user.name=KnitCode Test', '-c', 'user.email=test@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-m', f'change {i}')
    history = read_history(project, {'a.py', 'b.py'})
    assert history['available']
    assert history['changes'] == {'a.py': 2, 'b.py': 2}
    assert len(history['pairs']) == 1
    assert len(history['pairs'][0]['commits']) == 2
    assert read_history(project, {'a.py', 'b.py'}, limit=1)['pairs'] == []


def test_vsix_contains_engine_and_resources(tmp_path):
    with ZipFile(package(tmp_path / 'knitcode.vsix')) as archive:
        assert archive.testzip() is None
        assert 'extension/vendor/analyzer/value_flow.py' in archive.namelist()
        assert 'extension/vendor/backend/export.py' in archive.namelist()
        assert 'extension/media/map.js' in archive.namelist()
        manifest = json.loads(archive.read('extension/package.json'))
        assert manifest['main'] == './extension.js'

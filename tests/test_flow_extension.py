import json
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from backend.export import export_project
from scripts.package_flow_extension import package

ROOT = Path(__file__).resolve().parents[1]


def test_flow_package_has_distinct_identity_and_command(tmp_path):
    original = json.loads((ROOT / 'vscode-extension/package.json').read_text())
    with ZipFile(package(tmp_path / 'flow.vsix')) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read('extension/package.json'))
        assert manifest['name'] == 'knitcode-flow'
        assert manifest['name'] != original['name']
        assert manifest['contributes']['commands'][0]['command'] == 'knitcodeFlow.open'
        xml = ElementTree.fromstring(archive.read('extension.vsixmanifest'))
        ns = {'v': 'http://schemas.microsoft.com/developer/vsx-schema/2011'}
        identity = xml.find('v:Metadata/v:Identity', ns)
        assert identity.attrib['Id'] == manifest['name']
        assert 'extension/vendor/backend/export.py' in archive.namelist()
        assert 'extension/media/map.css' in archive.namelist()
        assert 'extension/media/map.js' in archive.namelist()


def test_flow_webview_behavior(tmp_path):
    jsc = shutil.which('jsc') or '/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc'
    if not Path(jsc).exists():
        pytest.skip('JavaScriptCore executable is unavailable')
    payload = tmp_path / 'analysis.json'
    payload.write_text(json.dumps(export_project(ROOT / 'tests/fixtures/advanced_project')))
    result = subprocess.run([jsc, 'tests/flow_webview_smoke.js', '--', str(payload)], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr

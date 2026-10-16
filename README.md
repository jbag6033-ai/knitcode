# KnitCode

Python 소스의 함수·클래스·호출 관계를 정적으로 분석하고, Git 변경 이력과 함께 VS Code에서 탐색하는 프로젝트입니다. 분석 대상 코드를 실행하지 않습니다.

두 확장은 각자의 화면과 명령을 유지하며 같은 분석기를 사용합니다.

| 확장 | 인터페이스 | 실행 명령 |
|---|---|---|
| [KnitCode](vscode-extension/README.md) | 코드 관계 그래프·파일 탐색 | `KnitCode: Open Code Map` |
| [KnitCode Flow](vscode-flow-extension/README.md) | 호출자 → 선택 함수 → 호출 대상 | `KnitCode Flow: Open Call Flow` |

## 시작하기

Python 3.10 이상, VS Code 1.85 이상이 필요합니다. Git 이력 기능에는 Git이 필요합니다. 핵심 분석기·JSON export·확장 패키징은 Python 표준 라이브러리만 사용합니다. 검증 환경은 Python 3.12.2입니다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m backend.export tests/fixtures/advanced_project
```

아래 명령으로 현재 분석기를 포함한 설치 파일을 만듭니다. npm이나 외부 웹 서버는 필요하지 않습니다.

```sh
.venv/bin/python scripts/package_extension.py
.venv/bin/python scripts/package_flow_extension.py
```

생성 파일은 `dist/knitcode-0.1.1.vsix`, `dist/knitcode-flow-0.1.1.vsix`입니다. VS Code에서 **Extensions → Install from VSIX…**로 각각 설치하고 분석할 Python 프로젝트 폴더를 연 뒤 위 명령을 실행합니다. 두 확장은 동시에 설치할 수 있습니다.

첫 확인에는 `tests/fixtures/advanced_project` 폴더를 사용하세요. Python 경로를 찾지 못하면 `knitcode.pythonPath` 또는 `knitcodeFlow.pythonPath`에 가상환경 Python의 절대 경로를 설정합니다. 파일을 저장한 뒤 패널의 **재분석**으로 갱신합니다. 분석기 소스 변경은 이미 설치한 확장에 자동 반영되지 않으므로 다시 패키징·설치해야 합니다.

## 분석 범위

- 프로젝트 내부 호출, 상속·생성자·메서드, 일부 인자·반환값·컨테이너 값 흐름을 추론합니다.
- property, with, lambda 및 제한된 동적 메서드 호출과 argparse 명령 등록·선택을 처리합니다.
- 외부 라이브러리와 동적 Python 기능 전체를 해석하지 않습니다. 정적 후보가 모든 입력에서 실행된다는 뜻은 아닙니다.
- Git 공동 변경은 기본 최근 90일/비병합 커밋 최대 300개에서 두 파일이 함께 변경된 기록이며 인과관계가 아닙니다.
- 확장은 신뢰한 workspace에서 저장된 소스만 분석합니다. 큰 프로젝트의 전체 성능은 보장하지 않으며 실행 제한은 180초입니다.

선택적으로 공개 함수의 외부 입력 타입을 JSON 계약으로 제공할 수 있습니다. [예제](reports/release-2026-10-16/entrypoints.example.json)는 asciinema 소스 루트 기준입니다. 명시한 타입은 추가 입력 가정이며 자동 추론 결과와 구분해야 합니다.

```sh
.venv/bin/python -m backend.export /path/to/python/project --entrypoints /path/to/entrypoints.json
```

Python API는 `CallResolver(root, entrypoints=config)` 및 `export_project(root, entrypoints=config)`를 지원합니다. 외부 입력 계약은 현재 확장의 별도 UI 설정으로 제공하지 않습니다.

기존 HTML 그래프 기능인 `analyzer.visualize`를 사용할 때만 별도로 `pip install pyvis`가 필요합니다.

## 검증 결과

2026-10-16 기본 분석, 원본 ground truth, 명시적 외부 입력 없음:

| 프로젝트 | Python 줄 수 | TP | FP | FN | F1 |
|---|---:|---:|---:|---:|---:|
| Sublist3r | 1,672 | 115 | 0 | 0 | 1.0000 |
| autojump | 2,945 | 205 | 15 | 12 | 0.9382 |
| fabric | 2,303 | 44 | 8 | 18 | 0.7719 |
| face_classification | 1,895 | 97 | 4 | 2 | 0.9700 |
| asciinema | 1,553 | 131 | 50 | 13 | 0.8062 |

테스트 **139개 통과**. 테스트에는 분석기 회귀, JSON/Git 이력, VSIX 내용, 사용 가능한 환경에서의 JavaScriptCore 기반 Flow 모의 DOM 검증이 포함됩니다. 실제 VS Code Extension Host의 설치·레이아웃은 별도 확인이 필요합니다.

정답과의 불일치에는 분석 실패뿐 아니라 표기·범위 차이가 포함될 수 있습니다. 정답 교정안이나 외부 입력을 적용한 수치를 기본 F1로 보고하지 않습니다. [검증 요약·재현 방법](reports/release-2026-10-16/README.md), [입력·정답·분석기 해시](reports/release-2026-10-16/summary.json)를 참고하세요.

## 저장소 구성

- `analyzer/`: AST·호출 해석·값 흐름·평가
- `backend/export.py`: 분석 결과 JSON CLI/API
- `git_analyzer/`: Git 이력·공동 변경
- `vscode-extension/`, `vscode-flow-extension/`: 두 확장 소스
- `tests/`: 테스트와 작은 자체 fixture
- `scripts/`: 평가 및 패키징 도구
- `reports/release-2026-10-16/`: 공개 검증 스냅샷

가상환경, 외부 benchmark 복사본, 생성 HTML/VSIX 및 새 중간 실험 자료는 Git에 포함하지 않습니다. 이전 커밋에 이미 포함된 baseline 보고서는 이력으로 유지합니다. 현재 개발 상태는 [CHECKPOINT.md](CHECKPOINT.md)에 기록합니다.

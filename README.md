# KnitCode Static Flow

Python 소스를 실행하지 않고 함수·메서드 호출 관계를 분석하고 VS Code에서 탐색합니다. 이 저장소의 현재 파일은 최신 엔진과 확장, 회귀 테스트, 최신 평가 결과입니다.

## VS Code에서 사용

최신 설치 파일: [knitcode-static-0.3.1.vsix](dist/knitcode-static-0.3.1.vsix).

1. VS Code의 Extensions에서 **Install from VSIX…**를 선택합니다.
2. VSIX를 설치하고 Python 프로젝트 폴더를 엽니다.
3. 명령 팔레트에서 **KnitCode Static Flow: Open Call Flow**를 실행합니다.

VS Code 1.85 이상과 Python 3.10 이상이 필요합니다. 설정은 `knitcodeStatic.pythonPath`, `knitcodeStatic.historyDays`, `knitcodeStatic.commitLimit`입니다.

## 명령줄 분석

```sh
python3 main.py /path/to/project --output-dir output
```

`graph_result.json`, HTML 보고서, 호출 상태 JSON/CSV 및 `external_call_graph.json`을 생성합니다. src layout은 자동 감지하며 `--source-root src`로 지정할 수 있습니다. 설치된 외부 라이브러리의 소스 확인은 `--analyze-deps --dep-root /path/to/dependencies`로 요청할 수 있습니다.

## 현재 지원 기능

- 함수·클래스·import·상속 및 객체·필드·반환값 흐름 분석
- classmethod, 중첩 클래스, property getter 및 기본 인자 처리
- await, 작은 컨테이너 요소, 분기·반환 흐름 처리
- 내장 클래스 상속 메서드와 sorted/map 콜백 추적
- 외부 import·별칭·인자·필드의 호출 후보와 외부 반환 계약
- 호출 근거·소스 위치 및 Git 공동 변경 이력 탐색

결과는 정적 may-call 후보입니다. 외부 기호 경로는 실제 구현·반환 타입의 확인과 구분되며 런타임의 모든 동작을 포착하지는 못합니다.

## 검증과 최신 평가

```sh
python3 -m unittest discover -s tests -q
python3 scripts/package_extension.py
```

[최신 평가 보고서](validation/latest/REPORT.md)와 [프로젝트별 지표](validation/latest/summary.json)를 제공합니다. 개발 과정의 중간 결과와 이전 산출물은 현재 파일 목록에서 제거했으며 Git 이력에는 보존돼 있습니다.

`verify_v23.py`, `verify_v231.py`, `verify_v24.py`는 현재 테스트와 분석 결과 검증에 쓰는 도구입니다. 파일명의 버전 표시는 도구를 처음 추가한 시점의 이름이며 과거 엔진 복사본이 아닙니다.

외부 입력 프로젝트를 이용한 전체 정답 재평가는 `python3 scripts/evaluate_paper.py`로 실행합니다. 원본 benchmark 데이터 위치는 최신 평가 보고서를 참고하세요.

# PyAnalyzer 대규모 대상 베이스라인 — 2026-10-14

분석기 구현을 변경하지 않고 RQ3 macro-benchmark C의 소스와 ground truth를 비교했습니다. 이번에 추가한 것은 별도 실행 스크립트와 결과 파일입니다.

## 선별 기준과 분석 범위

핵심 소스의 `.py` 파일 전체 줄 수(주석, docstring, 빈 줄 포함)가 Sublist3r의 1,672줄보다 큰 대상만 선별했습니다. 파일 수나 전체 저장소 크기를 기준으로 삼지 않았습니다. 테스트, 문서 빌드 코드, 설치 도구는 패키지 밖에 있으면 제외했습니다.

| 프로젝트 | 대상 디렉터리 | Python 파일 | 줄 수 | 선정 |
|---|---|---:|---:|---|
| Sublist3r | 프로젝트 루트 | 4 | 1,672 | 비교 기준 |
| asciinema | `asciinema/` | 24 | 1,553 | 제외 |
| autojump | `bin/` | 4 | 2,945 | 선정 |
| fabric | `fabric/` | 12 | 2,303 | 선정 |
| face_classification | `src/` | 20 | 1,895 | 선정 |

Sublist3r은 기존 평가 범위를 유지하려고 루트를 사용했습니다. autojump에는 확장자가 없는 실행 파일도 있지만 현재 분석기가 `.py`만 읽으므로 이 실행 파일은 평가 범위에 포함하지 않았습니다. autojump의 크기에는 저장소에 포함된 `autojump_argparse.py`도 포함됩니다. 따라서 결과는 각 저장소 전체의 정확도를 의미하지 않습니다.

## 평가 방법

- 양쪽 endpoint가 분석 대상의 Python 모듈 namespace에 속하는 ground-truth edge만 비교합니다. 외부 라이브러리 edge와 대상 밖의 테스트/예제 호출은 제외합니다.
- 예측 edge에도 같은 범위 필터를 적용하고 중복 없는 caller–callee 쌍을 비교합니다.
- 패키지 상대 경로에는 `fabric.` 등 실제 패키지 접두어를 붙입니다. `bin/`과 `src/`는 import namespace가 아니므로 접두어에서 제외합니다. `__init__.py`는 패키지 모듈 이름으로 변환합니다.
- 함수, 메서드, 생성자, lambda 이름은 기존 평가 방식 그대로 사용합니다. 평가 점수를 높이기 위한 edge 병합이나 중첩 함수 이름 보정은 하지 않았습니다.
- 모듈 namespace 필터는 소스 파일에서 생성하며 정의별 정답 여부를 별도 수동 검증한 것은 아닙니다. 생성자/lambda 등의 의미 차이와 ground truth의 누락 가능성은 이 수치만으로 판정할 수 없습니다.
- 예외가 발생하면 해당 프로젝트를 실패로 기록하며, 실패한 호출을 건너뛰어 임의의 부분 점수를 계산하지 않습니다.

## 결과

| 프로젝트 | GT | 예측 | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sublist3r (기준) | 115 | 115 | 115 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| autojump | 217 | 156 | 134 | 22 | 83 | 0.8590 | 0.6175 | 0.7185 |
| fabric | 62 | — | — | — | — | — | — | 분석 중단 |
| face_classification | 99 | 97 | 95 | 2 | 4 | 0.9794 | 0.9596 | 0.9694 |

GT는 전체 JSON edge 수가 아니라 위 평가 범위에서 남긴 내부 edge 수입니다. 기존 회귀 테스트 18개도 통과했습니다.

## 확인된 차이와 오류

### autojump

중첩 함수의 이름 표현이 다릅니다. 예를 들어 예측은 `autojump_argparse.ArgumentParser.consume_optional`을 사용하지만 ground truth는 `autojump_argparse.ArgumentParser._parse_known_args.consume_optional`을 사용합니다. 이 차이는 FP와 FN 양쪽에 집계됩니다. 단순히 모든 FP가 엉뚱한 실행 대상을 선택했다고 해석하면 안 됩니다.

그 밖에 `ArgumentParser._get_formatter → HelpFormatter.__init__` 등 누락 edge도 있습니다. 전체 원인 분류는 아직 하지 않았습니다.

### fabric

파싱 및 visitor 수집 이후 호출 해석 중 다음 예외로 중단되었습니다.

```text
executor.py:84
ConnectionCall.make_context → Connection
AttributeError: 'NoneType' object has no attribute 'replace'
```

`from . import Connection`에서 AST의 `ImportFrom.module`이 `None`인데 resolver가 `module.replace()`를 호출합니다. 현재 베이스라인에는 수정하지 않았습니다. 전체 traceback은 `summary.json`에 있습니다.

### face_classification

FP 두 개는 다음입니다.

- `utils.grad_cam.compile_gradient_function → utils.grad_cam.compile_gradient_function.<lambda1>`
- `utils.visualizer → utils.datasets.get_labels`

FN 네 개는 다음입니다.

- `image_gradcam_demo → utils.grad_cam.load_image`
- `utils.data_augmentation.ImageGenerator.flow → utils.preprocessor._imread`
- `utils.data_augmentation.ImageGenerator.flow → utils.preprocessor._imresize`
- `web.faces.upload → web.emotion_gender_processor.process_image`

이는 ground truth와의 차이 목록이며, 각 항목의 실행 의미를 모두 수동 판정한 목록은 아닙니다.

## 결과 파일과 재실행

- `summary.json`: 선별 목록, 결과, 분석기·입력 소스·ground truth의 SHA-256, 환경 정보, 예외
- `<프로젝트>-edges.json`: TP/FP/FN 전체 목록
- `<프로젝트>-calls.json`: 미해결을 포함한 전체 resolver 결과 (정상 완료한 프로젝트만)

현재 분석기는 이전 안정화 작업의 미커밋 변경을 포함합니다. 비교할 때 Git HEAD보다 기록한 분석기 소스 해시를 사용해야 합니다.

프로젝트 루트에서 새 출력 폴더를 지정하면 기준 결과를 덮어쓰지 않고 재평가할 수 있습니다.

```bash
PYTHONDONTWRITEBYTECODE=1 Knitcode/bin/python scripts/pyanalyzer_baseline.py --output reports/pyanalyzer-next
PYTHONDONTWRITEBYTECODE=1 Knitcode/bin/python -m pytest -q -p no:cacheprovider
```

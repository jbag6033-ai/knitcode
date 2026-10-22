# PyCG 논문 기준 전체 호출 평가 (2026-10-22)

## 결론

내부 호출 필터를 제거하고 원본 채점 함수를 그대로 사용했다. Fabric F1은 **71.75%**, 논문 PyCG의 반올림된 정밀도·재현율로 계산한 F1은 **75.96%**다. 현재 Fabric에서는 PyCG보다 낮다. 이전 내부 호출 F1 77.06%와는 입력 파일 범위와 정답 분모가 다르다.

## 재현 근거

- [원본 재현 패키지](https://doi.org/10.5281/zenodo.4456583)의 `scripts/compare_macro_benchmark_cg.py`를 수정 없이 실행했다. 정밀도·재현율 함수 원문과 SHA-256은 reference/에 보관했다.
- `generate_pycg_cgs.sh`의 입력 파일 선택 규칙을 적용했다. Fabric은 패키지 12개 파일만이 아니라 integration, tasks, sites 등을 포함해 **20개 Python 파일**이다. `tests`와 `setup.py`는 원본 스크립트대로 제외했다.
- 5개 프로젝트 모두 원본 패키지와 **선택된 파일 목록 및 모든 입력 Python 파일 SHA-256이 일치**한다. `knitcode_test`의 ground truth JSON도 원본 패키지와 동일하다. 결과의 artifact_check에 기록했다.
- 모든 정답 간선을 분모에 남겼다. 외부 대상, 내장 함수/타입, integration caller, 이름 오탈자를 삭제하지 않았다. 예측에도 caller/namespace 필터나 suffix 매칭을 적용하지 않았다.
- 정답을 사용해 예측 간선을 보정하지 않았다. 람다 및 내장 타입 표기만 변환한다. 같은 생성 지점에 `__init__` 호출이 있으면 별도 클래스 INSTANTIATES 간선은 함수 호출 출력에서 제외한다. 원본 내부 클래스 간선을 포함한 진단 결과도 각 results.json에 남긴다.

## 전체 호출 결과

| 프로젝트 | 정답 항목 수 | 우리 정밀도 | 우리 재현율 | 우리 F1 | 논문 PyCG F1* |
|---|---:|---:|---:|---:|---:|
| autojump | 537 | 93.61% | 70.95% | 80.72% | 80.93% |
| fabric | 381 | 83.33% | 62.99% | 71.75% | 75.96% |
| asciinema | 341 | 83.28% | 71.85% | 77.14% | 80.95% |
| face_classification | 435 | 90.11% | 94.25% | 92.13% | 94.35% |
| Sublist3r | 406 | 89.49% | 69.21% | 78.06% | 75.89% |

* 논문 Table IV의 반올림된 P/R로 계산한 값이며, 이번 작업에서 PyCG 바이너리를 재실행한 값은 아니다. 원본 재현 패키지 table4.txt는 asciinema 재현율을 68.3%로 표시하고 논문은 68%로 표시한다. 표는 논문 68%를 사용했다. 다른 4개 프로젝트의 P/R은 두 표가 일치한다.

원본 scorer는 정답 배열의 중복 항목도 재현율 분모와 적중 수에 포함한다. autojump는 고유 정답 쌍 535개/원본 항목 537개, asciinema는 340개/341개다. 원본 동작을 유지했다. results.json의 TP/FP/FN은 고유 쌍의 진단 수이고, precision/recall은 원본 함수를 따른다.

## 외부 호출 지원

기존 기능은 외부 provenance 분류와 선택적인 설치된 dependency 소스 분석이었다. 이번에는 기본 분석에서 `external_call_graph.json`을 생성하도록 추가했다.

- 표준 라이브러리·외부 import 별칭과 내장 함수/타입 메서드를 호출 후보로 내보낸다.
- 외부 함수 참조와 생성 결과를 함수 별칭, 인자, 객체 필드 및 내부 함수의 반환 경로를 통해 추적한다.
- 단일 명시적 외부 기반 클래스의 상속 호출과 super 호출을 기호 경로로 기록한다. 다중 미확인 기반 클래스의 MRO를 추측하지 않는다.
- 인자 가림, 재할당, 명시적 속성 덮어쓰기를 검사한다. 출처 없는 수신자는 메서드 이름만으로 외부 대상에 연결하지 않는다.
- 내부 그래프의 상태 집계를 유지한다. 외부 간선은 `CALLS_EXTERNAL`과 근거 위치·규칙·certainty를 가진 별도 그래프다. 설치된 dependency 소스의 실제 정의 확인은 기존 `--analyze-deps --dep-root ...` 경로에서 별도 제공한다.

외부 import 경로와 생성 결과의 메서드는 **기호적 may-call 후보**다. `Client()`의 실제 반환 타입, 라이브러리의 re-export에 숨겨진 정의 모듈, C 확장, 동적 메타프로그래밍을 완전히 복원하지는 못한다. 이 경우 추측을 검증된 구현으로 표시하지 않는다. 원본 ground truth의 경로와 다르면 그대로 FP/FN에 반영한다.

## 외부 출력 유무 비교

아래의 전 값은 같은 현재 엔진의 내부 그래프만 전체 정답에 채점한 비교값이다. 이전 내부 호출 평가 점수 또는 이전 버전 실행값이 아니다.

| 프로젝트 | 외부 출력 없음 F1 | 외부 출력 포함 F1 |
|---|---:|---:|
| autojump | 44.51% | 80.72% |
| fabric | 28.63% | 71.75% |
| asciinema | 44.66% | 77.14% |
| face_classification | 36.47% | 92.13% |
| Sublist3r | 44.06% | 78.06% |

## 검증 및 재실행

외부 참조 전파·가림·상속에 관한 회귀 테스트 15개와 원본 scorer의 전체 범위·중복·정확 이름 비교 테스트 3개를 추가했다. 전체 **386개 테스트 통과**. 원본 프로젝트 코드를 import하거나 실행하지 않고 AST로만 분석했다.

```sh
python3 scripts/evaluate_paper.py
python3 -m unittest discover -s tests -q
```

원본 패키지가 있으면 입력 일치 검증도 반복할 수 있다.

```sh
python3 scripts/evaluate_paper.py --artifact-root /path/to/pycg-artifact
```

`comparison.json`에는 논문 수치와 현재 측정값, 각 프로젝트 `results.json`에는 모든 TP/FP/FN 및 소스 해시, `predicted.json`에는 원본 scorer에 전달한 인접 리스트, `evidence.json`에는 호출 근거가 있다.

## 후속 Fabric 개선

이 문서의 측정값은 외부 호출을 처음 추가한 시점의 결과다. [후속 개선](../fabric_precision_2026_10_22/REPORT.md)에서 Fabric의 FP 48→43, FN 141→136, F1 71.75%→73.24%를 확인했다. 다른 네 프로젝트에서도 새 FP와 기존 TP 손실은 없었다.

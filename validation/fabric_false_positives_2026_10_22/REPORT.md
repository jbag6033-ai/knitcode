# Fabric 추가 오탐 감소 (2026-10-22)

## 결과

동일한 원본 PyCG 입력 파일·전체 ground truth·채점 함수를 사용했다. 원본 재현 패키지와의 입력 파일 선택·소스 해시·정답 일치 검사도 통과했다. 기준선은 fabric_precision_2026_10_22/improved 결과를 복사해 보존했다.

| 지표 | 전 | 후 |
|---|---:|---:|
| TP | 245 | 245 |
| FP | 43 | 42 |
| FN | 136 | 136 |
| 정밀도 | 85.07% | 85.37% |
| 재현율 | 64.30% | 64.30% |
| F1 | 73.24% | 73.35% |

5개 프로젝트 모두 새 FP **0개**, 잃은 TP **0개**. 다른 네 프로젝트의 지표는 유지됐다. 쌍 단위 검사 결과는 comparison.json에 있다. 전체 **403개 테스트 통과**.

## 수정

`path.local.mkdtemp().join(...)`에서 `py.path.local.mkdtemp.join`을 만들어 내던 잘못된 외부 반환 타입 추론을 제거했다. `mkdtemp` 호출 자체는 유지한다. 결과 객체의 실제 메서드를 복원할 dependency source 정보가 없으면 반환값을 opaque로 유지하며 함수 자체의 인스턴스로 만들지 않는다.

이 동작은 프로젝트별 정답 예외가 아니라 기존 외부 API 반환 요약에 추가한 명시적 API 계약이다. primitive 반환 계약과 객체 factory 계약을 구분했다. object flow와 legacy flow snapshot 모두 같은 요약을 사용한다. 알려진 API에만 적용되며, 다른 패키지의 동명 메서드는 이 계약을 적용하지 않는다.

API 근거: [py 1.4.31 문서](https://pylib.readthedocs.io/en/stable/path.html), [py 공식 소스 문서](https://py.readthedocs.io/en/latest/_modules/py/_path/local.html). `LocalPath.mkdtemp`는 Path 객체를 반환한다. `.join`은 factory 함수의 인스턴스 메서드가 아니다. 문서나 프로젝트 코드를 실행하지 않고 정적 규칙으로 처리했다.

직접 체인, 지역 변수 별칭, 다른 패키지의 동명 API에 대한 회귀 테스트 3개를 추가했다.

## 남은 오탐 검토

정답에 없는 42개 쌍과 근거 위치를 remaining_fp_audit.json에 저장했다. 그중 8개는 소스에서 실제로 관찰되는 property 접근이다. 다른 사례에는 `socket.socket` 대 정답의 `socket.Socket`, 소스 import의 `invoke.util.ExceptionHandlingThread` 대 정답의 `invoke.exceptions.ExceptionHandlingThread`, 명시적 외부 `__init__` 대 정답의 클래스 이름처럼 경로·표현 차이가 있다.

이 차이를 근거 없이 프로젝트별 치환으로 처리하거나, 정답에 없다는 이유로 소스에 있는 호출을 삭제하지 않았다. 따라서 이번 개선 폭은 FP 1개 감소다. 나머지가 모두 런타임 오탐이라고 확정한 것은 아니며, dependency 정의와 호출 표현을 추가로 검증해야 한다. 논문 PyCG F1 약 75.96%보다 현재 점수는 여전히 낮다.

## 재현

```sh
python3 scripts/evaluate_paper.py --output validation/fabric_false_positives_2026_10_22/improved
python3 scripts/compare_paper_runs.py validation/fabric_false_positives_2026_10_22/baseline validation/fabric_false_positives_2026_10_22/improved --output validation/fabric_false_positives_2026_10_22/comparison.json
python3 -m unittest discover -s tests -q
```

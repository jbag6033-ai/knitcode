# Ground truth 기반 macro 평가 (2026-10-22)

원본 knitcode_test의 release-2026-10-16과 소스 및 ground truth SHA-256을 대조했다. 대상 코드는 실행하지 않고 AST로만 분석했다. 기존 작업 트리의 변경을 포함한 시작 상태를 baseline으로 사용했다.

## 비교 기준

주 지표는 내부 FUNCTION/METHOD/LAMBDA를 대상으로 하는 CALLS 간선의 고유 caller–callee 쌍이다. 정답의 클래스 대상 쌍도 분모에 유지한다. 생성자 치환이나 간선 보정은 없다. 람다 이름만 소스 순서로 정규화한다. fabric/asciinema는 정답의 패키지 이름과 import 해석을 맞추기 위해 해시를 확인한 파일만 임시 패키지 디렉터리에 복사했다. 각 프로젝트 results.json에는 클래스 대상 포함 raw 지표와 선언된 함수만의 projection도 별도로 보관한다.

| 프로젝트 | 파일 | TP 전→후 | FP 전→후 | FN 전→후 | 정밀도 | 재현율 | F1 전→후 |
|---|---:|---:|---:|---:|---:|---:|---:|
| autojump | 4 | 147→154 | 1→1 | 70→63 | 99.35% | 70.97% | 80.55%→82.80% |
| fabric | 12 | 38→38 | 1→1 | 24→24 | 97.44% | 61.29% | 75.25%→75.25% |
| face_classification | 20 | 97→97 | 0→0 | 2→2 | 100.00% | 97.98% | 98.98%→98.98% |
| asciinema | 24 | 103→103 | 1→1 | 41→41 | 99.04% | 71.53% | 83.06%→83.06% |

## 수정과 검증

- 인스턴스로 접근한 중첩 클래스와 그 별칭을 클래스 참조로 유지해 생성 후 메서드와 필드 흐름을 연결했다. 인스턴스 필드와 명시적 namespace 변경이 우선한다.
- 생략된 인자의 단순 이름/상수 기본값을 정의의 바깥 스코프에서 해석한다. 명시적 인자는 기본값보다 우선한다. 이 수정만으로는 이번 macro 점수 변화가 없었다. 기본값의 호출식/가변 객체는 재평가하지 않는다.
- 일반화한 회귀 테스트 6개를 추가했다. 전체 테스트 결과는 unit_tests.log 참조.
- Sublist3r 재검증: TP 115, FP 1, FN 0 (함수 호출 기준).

## 남은 항목

- autojump: 레지스트리에서 꺼낸 action 클래스, 중첩 함수의 자유 변수, 컨테이너에 저장한 콜백 및 super 별칭 등이 남는다. 누락 전체를 실제 런타임 오류로 단정하지 않는다.
- asciinema: contextmanager의 합성 __enter__/__exit__ 이름, 명령 클래스 선택 및 외부 콜백 연결이 남는다.
- fabric: property 접근, 외부 기반 클래스와 decorator/callback, 합성·상속된 함수 이름의 차이가 남는다.
- face_classification: load_image 및 web 모듈의 실행 경로 의존 import 두 쌍이 남는다. 임의의 suffix 매칭으로 보정하지 않았다.
- raw 클래스 포함 기준에서는 autojump TP 147→154, FP 11→14, FN 70→63이다. 추가 클래스 생성 간선 때문에 함수 기준과 오탐 수가 다르다.

## 재현

```sh
python3 scripts/evaluate_sublist3r.py --project autojump --output validation/macro_2026_10_22/rerun/autojump
python3 -m unittest discover -s tests -q
```

## 후속 Fabric 개선

이 문서의 표는 첫 macro 평가 당시 결과다. property 및 classmethod 추적을 추가한 후속 결과는 [Fabric 집중 평가](../fabric_focus_2026_10_22/REPORT.md) 참조. Fabric F1은 75.25%→77.06%이며, 원본 정답에 없는 property 간선도 늘었다. 다른 프로젝트의 점수 변화도 후속 문서에 기록했다.

## 논문 기준 전체 호출 재평가

외부 호출을 포함하고 원본 재현 패키지의 채점 함수·입력 파일 범위를 적용한 최신 결과는 [논문 기준 평가](../paper_2026_10_22/REPORT.md)에 있다. 원본과 입력 소스 및 ground truth의 일치를 확인했다. Fabric 전체 호출 F1은 71.75%이며, 이 문서의 내부 호출 점수와는 분모가 다르다.

## Fabric 오탐·미탐 동시 개선

최신 전체 정답 기준 Fabric F1은 **71.75%→73.24%**, FP **48→43**, FN **141→136**이다. 5개 프로젝트 모두 새 오탐과 기존 정답 적중 손실 없이 개선 또는 유지됐다. [상세 결과](../fabric_precision_2026_10_22/REPORT.md)를 참조한다.

## 추가 오탐 감소

최신 전체 정답 기준 Fabric은 FP **43→42**, TP **245 유지**, FN **136 유지**, F1 **73.24%→73.35%**다. 다른 네 프로젝트의 지표도 유지됐다. [변경 근거와 남은 오탐 검토](../fabric_false_positives_2026_10_22/REPORT.md)를 참조한다.

## GitHub 도입 이후 전체 개선 이력

Git 도입 커밋을 복원한 동일 기준 재평가와 단계별 개선·PyCG 비교를 [Notion용 종합 문서](../github_progress_2026_10_22/NOTION_REPORT_KO.md)에 정리했다.

# Fabric 집중 개선 (2026-10-22)

기준선은 앞선 macro 평가의 improved/fabric/results.json이며 baseline.json에 복사해 보존했다. 소스 및 정답 해시는 평가기가 기존 release 기록과 검증했다. 원본 ground truth는 수정하지 않았다.

## PyCG 논문 확인

PyCG ICSE 2021 논문 [Table IV, PDF 9쪽](https://arxiv.org/pdf/2103.00587)은 Fabric에 대해 **정밀도 98.3%, 재현율 61.9%**를 보고한다. F1 자체를 표에 싣지는 않았고, 두 반올림된 수치로 계산하면 **약 75.96%**이다. F1=1이 아니다. 같은 행 Depends 열의 100은 정밀도이며 재현율은 6.3%다.

[PyAnalyzer 데이터셋 설명](https://github.com/2024icse/PyAnalyzer#rq3-what-is-the-general-accuracy-of-pyanalyzer-to-analyze-real-world-projects)은 macro-benchmark C와 ground truth가 PyCG에서 온 것임을 명시한다. 논문은 외부 라이브러리 호출도 평가한다. 현재 평가는 source-derived namespace 내부 쌍으로 제한하므로 논문 수치와 직접적인 우열 비교는 하지 않는다.

## 동일 원본 정답에 대한 결과

주 지표는 CALLS의 함수/메서드/람다 대상 고유 caller–callee 쌍이다. 정답 62개는 전부 분모에 유지했다.

| 지표 | 전 | 후 |
|---|---:|---:|
| TP | 38 | 42 |
| FP | 1 | 5 |
| FN | 24 | 20 |
| 정밀도 | 97.44% | 89.36% |
| 재현율 | 61.29% | 67.74% |
| F1 | 75.25% | 77.06% |

클래스 대상도 포함하는 raw 기준은 TP 39→43, FP 17→22, FN 23→19, F1 66.10%→67.72%이다. 선언된 함수만 비교하는 projection은 F1 81.72%→83.17%이며 주 지표와 분모가 다르다.

## 엔진 수정

- builtin `@property` getter를 인스턴스 속성 읽기에서 실행되는 암묵적 호출로 기록하고 반환 객체를 추적한다. 일반 AST Call의 상태 집계와 분리하고, 원본 속성 위치와 표현식을 근거로 저장한다.
- property는 data descriptor이므로 인스턴스 필드보다 우선한다. 클래스/인스턴스의 일반 메서드 조회는 기존 동작을 유지한다.
- 상속, 하위 클래스의 descriptor 가림, 기본 decorator 이름의 재정의 및 클래스 속성 패치를 검사한다. 임의의 decorator를 property로 가정하지 않는다.
- 외부 호출자가 없어도 classmethod 본문을 소유 클래스 참조로 분석한다.

추가 적중: `Connection.open → is_connected`, `Fab.load_collection → _remainder_only`, `Transfer.get → sftp`, `Group.from_connections → __init__`.

추가 FP로 집계된 네 쌍도 소스의 property 접근이다: `Connection.close → is_connected`, `Fab.no_tasks_given → _remainder_only`, `Transfer.is_remote_dir → sftp`, `Transfer.put → sftp`. 같은 property 접근인데 원본 정답에 포함된 caller와 없는 caller가 다르다. 이를 정답 누락 후보로 기록했으며 점수에서 제거하거나 정답을 보정하지 않았다. 위치·표현식은 added_pair_audit.json 참조.

## 다른 프로젝트와 검증

| 프로젝트 | F1 전 | F1 후 |
|---|---:|---:|
| autojump | 82.80% | 82.80% |
| asciinema | 83.06% | 80.93% |
| face_classification | 98.98% | 98.98% |
| Sublist3r | 99.57% | 99.57% |

asciinema는 TP 103→104, FP 1→9로 변한다. 추가 FP 8개는 main에서 Config property를 읽는 간선이다. 원본 정답과의 점수 하락을 그대로 보고한다. 실제 런타임 전체에 대한 완전성은 주장하지 않는다.

일반화한 회귀 테스트 8개를 추가했다. 전체 테스트 실행 결과는 unit_tests.log에 있다. raw 정답에는 `Connetion` 및 `merga`처럼 소스 선언과 맞지 않는 이름도 남아 있다. 이번 수정에서는 이 이름이나 생성자 쌍을 보정하지 않았다.

```sh
python3 scripts/evaluate_sublist3r.py --project fabric --output validation/fabric_focus_2026_10_22/rerun
python3 -m unittest discover -s tests -q
```

## 후속 전체 호출 평가

[논문 기준 전체 호출 평가](../paper_2026_10_22/REPORT.md)는 원본 scorer와 전체 ground truth를 사용한다. Fabric F1은 71.75%이며 위 내부 호출 점수와 직접 비교하지 않는다.

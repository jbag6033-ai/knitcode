# Fabric 오탐·미탐 동시 개선 (2026-10-22)

## 결과

원본 PyCG 채점 함수, 전체 ground truth, 입력 파일 범위를 유지했다. 기준선은 직전 paper_2026_10_22 평가 결과이며 baseline/에 복사해 보존했다. ground truth 및 프로젝트 소스는 수정하지 않았다. 개선 후에도 원본 재현 패키지와 파일 목록·소스 해시·정답의 일치를 검증했다.

| Fabric | 전 | 후 |
|---|---:|---:|
| 정답 적중 TP | 240 | 245 |
| 오탐 FP | 48 | 43 |
| 미탐 FN | 141 | 136 |
| 정밀도 | 83.33% | 85.07% |
| 재현율 | 62.99% | 64.30% |
| F1 | 71.75% | 73.24% |

기존 정답 적중 손실 **0개**, 새 오탐 **0개**다. 원본 정답 381개 전체를 유지했다. 논문 PyCG의 반올림 수치로 계산한 F1 약 75.96%에는 아직 미치지 못한다.

## 구현 및 수정

1. **내장 클래스 상속 메서드 추적**: 단일 기반 클래스가 소스상 가려지지 않은 builtin list/dict 등으로 확인되면 지원되는 메서드를 연결한다. 사용자 메서드·클래스 속성의 가림과 다중 미확인 기반 클래스는 보수적으로 처리한다.
2. **지연 map의 소비 지점에서 콜백 추적**: join/list/tuple 등 확인된 소비자에 직접 전달된 map의 외부·builtin 콜백을 기록한다. 소비되지 않은 map, 빈 리터럴 입력, 가려진 map/콜백에는 호출을 추가하지 않는다.
3. **외부 호출 반환값 오인 수정**: 문자열·바이트를 반환하는 것으로 알려진 os.path 함수의 결과를 그 함수 자체의 인스턴스로 취급하지 않는다. object flow와 기존 flow snapshot 양쪽의 잘못된 constructor-result 후보 생성을 차단한다.
4. **잘못된 경로 중복 추론 제거**: 함수 호출 괄호를 포함한 문자열을 canonical API 이름으로 내보내지 않는다. 실제 객체 흐름으로 추적하지 못한 중첩 호출을 source 문자열만으로 생성자라고 가정하던 inline fallback을 제거한다.

정답을 참조하는 프로젝트별 예외, 이름 오탈자 보정, 임의 suffix 매칭, property 간선 삭제는 추가하지 않았다. primitive-return 목록은 알려진 API 의미에 따른 일반 규칙이다.

## Fabric에서 추가한 정답 쌍

- `fabric._version → <builtin>.str`
- `fabric.group.Group.__init__ → <**PyList**>.extend`
- `fabric.group.Group.from_connections → <**PyList**>.extend`
- `fabric.group.GroupResult._bifurcate → <**PyDict**>.items`
- `integration.connection.Connection_.run.simple_command_with_pty → <builtin>.int`

## Fabric에서 제거한 오탐 쌍

- `fabric.transfer.Transfer.put → os.path.abspath.seek`
- `fabric.transfer.Transfer.put → os.path.abspath.tell`
- `integration.transfer.Transfer_.put.base_case → py.path.local().as_cwd`
- `integration.transfer.Transfer_.put.setup → py.path.local.mkdtemp().join`
- `integration.transfer.Transfer_.put.setup → py.path.local.mkdtemp().join().realpath`

## 전체 프로젝트 회귀 평가

| 프로젝트 | TP 전→후 | FP 전→후 | FN 전→후 | F1 전→후 | 새 FP / 잃은 TP |
|---|---:|---:|---:|---:|---:|
| Sublist3r | 281→281 | 33→30 | 125→125 | 78.06%→78.38% | 0 / 0 |
| asciinema | 244→244 | 49→47 | 96→96 | 77.14%→77.39% | 0 / 0 |
| autojump | 381→382 | 26→24 | 154→153 | 80.72%→81.02% | 0 / 0 |
| fabric | 240→245 | 48→43 | 141→136 | 71.75%→73.24% | 0 / 0 |
| face_classification | 410→410 | 45→40 | 25→25 | 92.13%→92.66% | 0 / 0 |

5개 프로젝트 모두 오탐·미탐 수가 늘지 않았으며, 쌍 단위에서도 새 FP와 잃은 TP가 없었다. 이 보장은 평가한 소스 스냅샷과 정답에 한정된다. 정답의 누락·오탈자는 원본 그대로 남아 있다.

## 검증 및 재현

일반화한 의미 회귀 테스트 12개와 쌍 단위 회귀 방지 검사 테스트 2개를 추가했다. 전체 **400개 테스트 통과**. 실행 결과는 unit_tests.log에 보관한다. comparison.json에는 입력 동일성·전후 지표·추가/삭제된 쌍을 저장한다.

```sh
python3 scripts/evaluate_paper.py --output validation/fabric_precision_2026_10_22/improved
python3 scripts/compare_paper_runs.py validation/fabric_precision_2026_10_22/baseline validation/fabric_precision_2026_10_22/improved --output validation/fabric_precision_2026_10_22/comparison.json
python3 -m unittest discover -s tests -q
```

비교 검사는 FP/FN 수 증가뿐 아니라 기존 FP 하나를 새 FP 하나로 바꾸거나 기존 TP를 잃고 다른 TP로 만회하는 경우에도 실패한다.

## 후속 오탐 감소

외부 factory 반환 계약을 보완해 FP 43→42, F1 73.24%→73.35%로 개선했다. TP와 FN은 유지했다. [후속 결과](../fabric_false_positives_2026_10_22/REPORT.md) 참조.

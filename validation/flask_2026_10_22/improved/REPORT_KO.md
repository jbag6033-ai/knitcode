# Flask 기준 분석 엔진 개선 — 2026-10-22

Flask 소스와 정답 기대치를 바꾸지 않고 분석기만 수정했다.
고정 커밋은 `d086db856be187255b8ec61ef409357393020f32` (3.2.0.dev)이다.
VSIX는 변경하거나 새로 생성하지 않았다.

## 결과

| 항목 | 개선 전 | 개선 후 |
|---|---:|---:|
| 본체 내부 연결 호출 | 148 / 1,223 | **207 / 1,223** |
| 본체 내부 연결 비율 | 12.1% | **16.9%** |
| 본체 비내부 출처 분류 | 584 | 584 |
| 본체 UNKNOWN | 491 | **432** |
| 전체 저장소 내부 연결 호출 | 736 / 3,961 | **844 / 3,961** |
| 전체 저장소 비내부 출처 분류 | 1,181 | 1,182 |
| 전체 저장소 UNKNOWN | 2,044 | **1,935** |
| 직접 바인딩 검토 14곳 정확 일치 | 12 | **14** |
| 위 14곳의 잘못 연결한 대상 | 2 | **0** |
| 기본 객체 시나리오 필수 후보 16곳 누락 | 12 | **3** |

본체는 새로 연결한 호출 59곳, 기존에 해결했던 호출 지점 소실 0곳,
대상 변경 2곳이다. 두 대상 변경은 JSON의 잘못된 재귀 연결 수정이다.
전체 저장소는 새 연결 108곳, 해결 지점 소실 0곳, 대상 변경 110곳이다.
전체의 대상 변경에는 기존 클래스 생성 호출에 생성자 간선이 추가되는 경우도 포함한다.
**연결 증가를 전부 TP라고 판정하지 않았으며, 위 비율은 Recall이 아니다.**

검토한 30곳은 개발에 사용한 표본이므로 독립적인 전체 정확도 평가가 아니다.
16곳의 기본 객체 시나리오는 필요한 후보만 검사하며, 다른 후보를 모두 정답/오답으로
판정하는 완전한 oracle이 아니다. 전후 source SHA-256과 기대 대상·시나리오가 같은지
`compare_flask.py`에서 검사했다.

## 바꾼 동작

### 1. 함수의 lexical scope와 클래스 namespace 구분

메서드에서 bare name을 해석할 때 바깥 클래스의 동명 메서드를 함수 closure처럼 검색하지
않는다. 함수의 closure, 모듈의 정의 및 import를 사용한다.
클래스 본문과 메서드 기본값 평가에서는 해당 클래스의 현재 namespace를 유지한다.
import·변수 바인딩 조회와 builtin 출처 분류에도 같은 클래스 경계 원칙을 반영했다.

이로써 `json/tag.py:323`의 `dumps`와 `:327`의 `loads`가 각각
`flask.json.dumps`, `flask.json.loads`로 연결된다. 이전의 동명 메서드 재귀 간선은 제거됐다.

### 2. 조건부 클래스 변경을 무조건적인 변경과 구분

Flask의 조건부 setattr를 보고 89개 메서드를 일괄 UNKNOWN으로 만들던 규칙을 수정했다.
**조건부로 바뀔 수 있으면 기존 바인딩도 가능한 후보로 유지하고 `MAY_CALL`로 표시한다.**
간선에는 `conditional_namespace_may_call`과 교체 대상을 모두 모델링하지 않았다는 근거를 남긴다.
속성 이름의 유한 후보 12개를 정밀하게 추적하는 기능을 구현한 것은 아니다.

원래 메서드의 반환·heap 상태만 확정하지 않도록 알 수 없는 교체 경로와 병합한다.
실제 대입/삭제/setattr가 수행된 경로에는 namespace 쓰기를 기록해,
그 경로 안에서 덮어쓴 이전 메서드를 다시 연결하지 않는다.
변경 전에 저장한 bound method와 변경 후 새로 조회한 descriptor도 구분한다.
if 상수·빈 반복·짧은 회로 조건의 불가능한 쓰기를 제외한다.
무조건적인 변경 및 알 수 없는 데코레이터에 대한 기존 연결 유보는 유지한다.

### 3. classmethod의 cls 바인딩 수정

새 연결을 감사하면서 `AppContext.from_environ`의 `cls(...)`가
전달받은 Flask 앱의 `__call__`로 연결될 수 있는 오류를 발견했다.
classmethod 호출에는 실제 수신 클래스(상속 시 자식 클래스)를 넘기도록 수정했다.
현재 `ctx.py:348`은 `AppContext`와 그 `__init__`로 연결된다.
클래스·인스턴스를 통한 호출 및 staticmethod와 일반 라이브러리 메서드 안의 호출도 검사했다.

### 4. 검증기의 lambda 누락 수정

소스 위치 검증에 `ast.Lambda`를 포함하고 인코딩 선언을 존중해 읽는다.
Flask의 정상 lambda 심볼을 누락으로 보고하던 오류를 수정했다.
현재 본체·전체 분석의 구조 16개, 호출 상태 10개 및 실제 AST 위치 검증이 모두 통과한다.

## 테스트 및 성능

- 기존 309개 + 신규 25개 = **334개 테스트 통과** (`unit_tests.log`).
- import/동명 메서드, closure·클래스 경계, 클래스 기본값, 조건부·확정 변경,
  변경 경로 안의 잘못된 후보 억제, 저장한 bound method, short-circuit,
  classmethod/staticmethod, lambda·인코딩 검증을 포함한다.
- 기존 합성 22사례는 동일 소스/기대치에서 **15/22, TP=15 FP=1 FN=6 유지**.
- 본체 약 1.68초(기존 1.17초), 전체 약 4.52초(기존 3.17초).
  복구된 호출 컨텍스트와 경로 검사가 늘어 비용도 증가했다. 동시에 시작한 단일 실행의
  관측치이므로 정밀한 성능 비교로 해석하지 않는다.
- 흐름 분석 제한 도달 횟수: 본체 4회, 전체 12회. 완전한 고정점 분석이 아니다.

## 남은 범위

검토 표본의 3개 누락은 `templating.py:125`의 `app.update_template_context`와
`json/__init__.py:41,103`의 `current_app.json.dumps/loads`다.
컨텍스트·LocalProxy·객체 필드 연결과 wrapper/closure 해석은 계속 개선이 필요하다.
조건부 변경의 정확한 교체 대상과 동적 namespace 변경 전체를 해결하지 않았다.
저장소 전체의 독립 정답이나 독립 검토자의 확인도 아직 없다.

## 재현

```sh
python3 -m unittest discover -s tests -q
python3 -B scripts/analyze_project.py benchmarks/flask/src --output validation/flask_2026_10_22/improved/production
python3 -B scripts/analyze_project.py benchmarks/flask --source-root src --output validation/flask_2026_10_22/improved/full
python3 -B scripts/review_flask.py --analysis-root validation/flask_2026_10_22/improved
python3 -B scripts/evaluate_engine.py --output validation/flask_2026_10_22/improved/synthetic_probes.json
python3 -B audit_realworld_changes.py validation/flask_2026_10_22/production/graph_result.json validation/flask_2026_10_22/improved/production/graph_result.json --repo-root benchmarks/flask/src --sample-size 100 --output-dir validation/flask_2026_10_22/improved/audit_production
python3 -B audit_realworld_changes.py validation/flask_2026_10_22/full/graph_result.json validation/flask_2026_10_22/improved/full/graph_result.json --repo-root benchmarks/flask --sample-size 30 --output-dir validation/flask_2026_10_22/improved/audit_full
python3 -B scripts/compare_flask.py
```

`comparison.json`에 전후 비교, `source_review.json/csv`에 고정한 30개 검토,
`audit_production`에 본체 신규 연결 59곳 전체의 검토 자료,
`audit_full`에 전체 변경 목록과 선정 표본을 남겼다.
기존 개선 전 산출물은 상위 폴더에 보존했다.

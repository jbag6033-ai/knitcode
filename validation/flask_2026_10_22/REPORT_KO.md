# Flask 실제 프로젝트 분석 — 2026-10-22

이 문서는 **개선 전 분석**이다. 이를 기준으로 수정한 결과는
[`improved/REPORT_KO.md`](improved/REPORT_KO.md)를 참고한다.

## 대상 및 범위

- 공식 저장소: https://github.com/pallets/flask
- 고정 커밋: `d086db856be187255b8ec61ef409357393020f32` (2026-10-07, `fix typing`).
- 체크아웃의 pyproject 버전: **3.2.0.dev**. 정식 릴리스 평가로 표현하지 않는다.
- 로컬 소스: `benchmarks/flask` (Git 추적 대상에서 제외).
- Python 3.12.2 / macOS. Flask·의존성 설치 및 Flask 소스 실행 없이 AST로 분석했다.
- 이번 작업에서는 분석 엔진을 수정하거나 VSIX를 만들지 않았다.

Flask 본체와 테스트·문서·예제를 포함한 전체 저장소를 분리해 분석했다.
본체는 `benchmarks/flask/src`, 전체는 저장소 루트와 `--source-root src`를 사용했다.
외부 의존성 소스는 포함하지 않았다. 따라서 Werkzeug·Jinja·Click 호출이 Flask 내부 간선으로
연결되지 않는 것은 그 자체로 미탐이 아니다.

## 실행 결과

| 항목 | Flask 본체 | 테스트·예제 등 포함 |
|---|---:|---:|
| Python 파일 | 24 | 83 |
| 소스 줄 수 (주석·문자열 포함) | 9,507 | 18,333 |
| 명시적 AST 호출 지점 | 1,223 | 3,961 |
| 내부 대상 연결 지점 | 148 | 736 |
| 비내부 출처로 분류 | 584 | 1,181 |
| UNKNOWN | 491 | 2,044 |
| 문법/읽기 오류 | 0 | 0 |
| 노드 | 450 | 1,684 |
| 간선 (구조 관계 포함) | 453 | 1,312 |
| 분석·산출물 저장 시간 | 약 1.17초 | 약 3.17초 |
| 재귀·작업량 제한 도달 횟수 | 4 | 11 |

두 실행은 동시에 시작했으며 시간은 이 환경의 단일 관측이다. 일반적인 성능 보장이 아니다.
비내부 분류도 분석기의 판단이며 독립 검토한 전체 정답이 아니다.
**148/1,223을 Recall로 계산하면 안 된다. UNKNOWN 491개도 모두 내부 호출 미탐은 아니다.**

## 직접 소스 검토한 30곳

이전의 합성 예제가 아닌 실제 Flask 호출 위치를 읽고 기대 대상을 작성했다.
동일한 assistant가 검토했으며 외부 검토자가 확인한 정답 데이터는 아니다.
오류 조사 중 선택한 표본이므로 전체 프로젝트의 Precision/Recall 추정에 사용하지 않는다.

### 직접 바인딩 14곳

모듈 함수·명시적 import 및 표준 json 호출을 검사했다.
**12곳 일치, 2곳 오연결**이다. 이 중 내부 호출 12곳의 간선은 TP=10, FP=2, FN=2이며,
나머지 2곳은 표준 json 함수에 대한 비내부 출처 분류를 확인했다.

확인한 오연결:

1. `src/flask/json/tag.py:323`의 `dumps(...)`
   - 정답: `FUNCTION:flask.json.dumps`.
   - 관측: `METHOD:flask.json.tag.TaggedJSONSerializer.dumps`.
2. 같은 파일 `:327`의 `loads(...)`
   - 정답: `FUNCTION:flask.json.loads`.
   - 관측: `METHOD:flask.json.tag.TaggedJSONSerializer.loads`.

파일 56–57행에 `from ..json import dumps, loads`가 명시돼 있다.
이름 기반 해석기가 메서드 내부의 비한정 이름을 클래스 namespace에서도 검색하면서,
import 함수 대신 동명 메서드를 선택했다. Python의 메서드 본문에서 클래스 namespace는
일반 함수의 바깥 lexical scope처럼 취급할 수 없다.
상대 import의 canonical origin 추적 자체는 `flask.json.dumps`를 올바르게 찾는다.
잘못된 선택은 이후 호출 해석의 `lexical_nested_function` 경로에서 발생했다.
이 두 연결은 모두 `SOURCE_BACKED`로 표시되므로 우선적으로 수정해야 한다.

### 기본 객체 시나리오의 필요한 후보 16곳

사용자가 메서드를 바꾸거나 서브클래스를 만들지 않은 기본 Flask/Config/serializer 객체와,
기본 JSON provider가 활성화된 앱 컨텍스트를 가정했다.
그 상황에서 가능한 **필수 후보**를 검사했으며, 다른 후보를 모두 열거한 것은 아니다.
추가 후보는 이 평가에서 FP로 계산하지 않았다.

**4곳은 필요한 후보를 찾았고, 12곳은 놓쳤다.** 누락 위치:

- `app.py:987` → `Flask.make_default_options_response`
- `app.py:1014` → `Flask.preprocess_request`
- `app.py:1016` → `Flask.dispatch_request`
- `app.py:1018` → `Flask.handle_user_exception`
- `app.py:1019` → `Flask.finalize_request`
- `app.py:1039` → `Flask.make_response`
- `app.py:1041` → `Flask.process_response`
- `app.py:1075` → `Flask.async_to_sync`
- `app.py:1597` → `Flask.full_dispatch_request`
- `templating.py:125` → `Flask.update_template_context`
- `json/__init__.py:41` → `DefaultJSONProvider.dumps`
- `json/__init__.py:103` → `DefaultJSONProvider.loads`

Config의 3개 내부 메서드 호출과 TaggedJSONSerializer의 `self.tag`는 연결했다.
서브클래스·확장·런타임 상태를 전부 포함한 전체 정답 집합과는 구별해야 한다.

## 확인한 주요 원인

1. **클래스 스코프에서 동명 메서드를 잘못 선택**: 앞의 JSON 오연결 2곳.
2. **동적 변경 경계의 과도한 범위**: `app.py:306`의
   `setattr(Flask, method.__name__, add_ctx(base_method))`를 보고 속성 이름을 `*`로 처리한다.
   이 때문에 Flask와 그 상위 클래스에서 **89개 메서드 정의를 일괄 유보**한다.
   실제 소스에는 변경을 검토하는 12개 메서드의 유한한 튜플이 있고, 조건 분기도 있다.
   이 범위와 wrapper의 의미를 반영하지 못해 기본 Flask 객체의 요청 처리 흐름까지 누락한다.
3. **LocalProxy·객체 필드·컨텍스트 전달 한계**: `current_app.json` 및
   `ctx.app`을 기본 Flask/JSON provider로 연결하지 못한다.
4. **데코레이터의 반환 callable을 추적하지 못함**: setupmethod, Click 등은 보수적으로
   유보한다. 이를 해결하려면 단순히 데코레이터를 무시하지 말고 wrapper·closure의 호출
   관계를 모델링해야 한다. 유보한 모든 호출이 미탐이라고 판정한 것은 아니다.

이번 실제 프로젝트에서는 앞서 합성 사례에서 좋아진 안전 규칙이 오히려
다수 호출을 막는 상황이 확인됐다. 기존 합성 표본의 Precision 93.8%를 Flask에 적용할 수 없다.

## 검증 도구의 한계도 별도로 확인

구조 무결성 16개 검사와 호출 상태 10개 검사는 두 범위 모두 통과했다.
다만 기존 `verify_v23 --repo`와 `verify_v231 --repo`는 소스 위치 검증에서 실패했다.
이 검증기는 `ast.Lambda`를 정의 집합에서 빼놓아, 정상 LAMBDA 심볼을 누락으로 보고한다.
본체 11개, 전체 26개가 모두 이 경우였다. 비제로 종료와 원래 로그는 보존했다.

별도로 lambda를 포함해 실제 파일의 AST와 대조한 결과,
본체 심볼 427개/호출 1,223개, 전체 심볼 1,606개/호출 3,961개 모두 위치가 존재했다.
이 검증은 위치·무결성만 확인하며 호출 대상의 정확성을 보장하지 않는다.

## 다음 개선 순서

1. 클래스 namespace와 함수 closure 검색을 구분해 동명 import 함수의 오연결을 수정한다.
2. setattr의 유한한 속성 이름 후보와 변경 조건을 추적해 일괄 UNKNOWN 범위를 줄인다.
3. wrapper/closure 및 컨텍스트·필드 전달을 지원한다. 특히 Flask의 요청 처리 흐름을
   실제 소스의 고정 호출 위치로 회귀 검증한다.
4. 수정에 쓰지 않은 다른 파일·다른 커밋/프로젝트에서 별도 평가한다.

## 개선 전 산출물과 현재 엔진 재실행

- `production/report.html`: 본체 오프라인 보고서.
- `full/report.html`: 전체 오프라인 보고서.
- 각 폴더의 `metadata.json`: 커밋·소스/엔진 SHA-256·규모·시간.
- `source_review.csv` / `source_review.json`: 30개 호출의 소스 발췌, 호출자,
  기대/관측 대상, 시나리오, 대상 정의 위치.
- 각 폴더의 원본 JSON/CSV 및 `verify_*.log`.

```sh
# benchmarks/flask가 위 커밋의 체크아웃인지 먼저 확인
git -C benchmarks/flask rev-parse HEAD
python3 -B scripts/analyze_project.py benchmarks/flask/src --output validation/flask_2026_10_22/improved/production
python3 -B scripts/analyze_project.py benchmarks/flask --source-root src --output validation/flask_2026_10_22/improved/full
python3 -B scripts/review_flask.py --analysis-root validation/flask_2026_10_22/improved
```

개선 전 실행에는 검증기의 lambda 문제로 종료 코드 1이 발생했다. 해당 원래 로그를 보존한다.
현재 엔진과 검증기로 위 명령을 실행하면 개선 폴더에 새 결과를 만들며, lambda 검증 문제는
해결돼 종료 코드 0을 반환한다.

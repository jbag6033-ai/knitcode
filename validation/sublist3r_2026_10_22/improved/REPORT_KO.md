# Sublist3r 누락 기능 보강 및 상속 개선 — 2026-10-22

## 측정 결과

동일한 소스 4개 파일과 원본 내부 함수 호출 정답 **115쌍**을 사용했다.
소스 및 정답의 SHA-256이 개선 전과 같은지 검사했고 정답은 수정하지 않았다.

| 함수 호출 쌍 기준 | 개선 전 | 개선 후 |
|---|---:|---:|
| TP | 83 | **115** |
| FP (원본 정답과 불일치) | 0 | **1** |
| FN | 32 | **0** |
| Precision | 100.0% | **99.1%** |
| Recall | 72.2% | **100.0%** |
| F1 | 83.8% | **99.6%** |

정답에 있던 누락 32쌍은 모두 복구했다. 이 점수는 현재 환경과 해당 benchmark의 일치도이며
모든 Python 프로젝트의 정확도 또는 독립적인 일반화 성능을 의미하지 않는다.
이번 수정에 정답의 누락 목록을 사용했으므로 개발용 평가다.

## 무엇을 개선했나

### 1. 알려진 표준 라이브러리 기반 클래스의 상속

기존에는 `multiprocessing.Process`가 상속에 포함되면 전체 MRO를 unknown으로 남겼다.
이제 설치된 Python 표준 라이브러리의 `multiprocessing/context.py`, `process.py`를
AST로 읽고 `Process → BaseProcess → object` 구조와 클래스 멤버를 확인한다.
확인한 외부 클래스는 C3 계산에 포함하지만 프로젝트 노드나 외부 메서드 간선을 만들지 않는다.

외부 부모에 실제로 존재하는 메서드/속성은 lookup 장벽으로 삼는다.
예를 들어 `Process.run`이 앞에 있으면 뒤의 내부 `run`으로 건너뛰지 않는다.
반면 해당 외부 부모에 없는 `print_` 등은 알려진 내부 부모에서 찾을 수 있다.
이 원칙으로 내부 상속 메서드·부모 생성자 관련 누락 **31쌍**을 복구했다.

표준 라이브러리 소스가 없거나 예상 구조와 다름, 조건부 import, 로컬 동명 모듈,
감지한 명시적 patch 등에서는 기존처럼 UNKNOWN을 유지한다.
임의 외부 라이브러리의 모든 상속을 지원하는 것은 아니다.

Sublist3r에는 Windows에서 `multiprocessing.Process = threading.Thread`로 바꾸는 코드가 있다.
`sys.platform.startswith(문자열)`이 신뢰 가능한 stdlib sys에 대한 접근임을 확인한 경우에만
현재 대상 환경에 맞춰 분기의 도달 가능성을 정적으로 판정한다.
이번 실행 환경은 **macOS / Python 3.12.2**다. 활성화되는 patch는 모델을 무효화하므로
Windows에서 같은 복구율을 보장하지 않는다. 임의 patch를 무시한 것은 아니다.
사용한 stdlib 파일 해시, 멤버 목록, Python 버전과 플랫폼은
`analysis/graph_result.json`의 `stdlib_mro_sources`에 기록했다.

### 2. lambda 직접 호출과 sorted key 콜백 추가

- lambda 생성 값을 소스 위치에 대응하는 callable 참조로 추적한다.
- 추적한 lambda를 직접 호출하면 해당 lambda로 간선을 만든다.
- unshadowed builtin `sorted`의 `key`가 알려진 내부 함수·메서드·lambda라면
  조건부 콜백 간선을 만든다. 임의 외부 함수의 lambda 인자는 자동 실행으로 간주하지 않는다.
- 비어 있는 리터럴 입력, 가려진 sorted, 알 수 없는 callback은 추측하지 않는다.
- lambda 본문/closure의 일반적인 반환값 실행 해석을 구현한 것은 아니다.

sorted 호출 자체와 key 실행은 별개다. 콜백 간선에는 일반 `call_id` 대신
`callback_call_id`로 실제 sorted 호출을 가리키며 `callback_may_execute` 근거를 붙인다.
따라서 sorted의 호출 상태를 INTERNAL로 바꾸거나 직접 해석 호출 수를 부풀리지 않는다.
이 근거와 콜백 간선의 중복·무결성도 검사한다.

엔진 lambda 식별자는 `<lambda@행:열>`로 유지한다. 평가할 때만 source scope 안의 순서를
이용해 benchmark의 `<lambda1>` 표기로 이름을 정규화한다.
간선의 추가/삭제/타깃 치환이나 정답 수정은 하지 않았다. 정규화 표는 `results.json`에 있다.

## 정답 대비 추가 1쌍은 왜 남겼나

추가된 관계는 다음이다.

```text
sublist3r.main → sublist3r.subdomain_sorting_key
```

원본 `sublist3r.py:963`에는 다음 코드가 있다.

```python
subdomains = sorted(subdomains, key=subdomain_sorting_key)
```

이는 비어 있지 않은 유효한 입력에서 key callback이 호출되는 소스 근거다.
원본 정답에는 해당 쌍이 없어 **benchmark 비교에서는 FP 1로 그대로 계산**했다.
정답의 누락인지 문서화되지 않은 범위 차이인지는 별도 확인이 필요하다.
lambda만 연결하고 이름 있는 callback은 일부러 누락시키는 방식으로 점수를 맞추지 않았다.

제품 그래프의 클래스 생성 `INSTANTIATES` 14쌍까지 원시 비교에 합치면
TP=115, FP=15, FN=0, F1=93.9%다. 추가 14쌍은 기존과 동일한 표현 범위 차이다.
함수 호출 점수에서 `__init__` 간선은 계속 포함하며 클래스 노드만 분리한다.

## 회귀 검증

- 기존 334개 + 신규 19개 = **353개 테스트 통과** (`unit_tests.log`).
- 외부 메서드 장벽, 내부 우선순위, super, patch·별칭·가려진 import,
  지원하지 않는 stdlib 구조의 유보와 callback의 실행/비실행 구분 등을 검사한다.
- Sublist3r의 구조 16개·상태 10개·실제 AST 위치 검증 통과 (`verification.log`).
- 기존 합성 22사례는 **15/22, TP=15 FP=1 FN=6 유지**.
- Flask 본체: 내부 연결 207 / 비내부 584 / UNKNOWN 432 유지.
- Flask 전체: 내부 연결 844 / 비내부 1,182 / UNKNOWN 1,935 유지.
- Flask 고정 검토 표본: 직접 바인딩 14/14, 필수 후보 13/16 유지.
- Flask 두 범위 모두 구조·상태·소스 위치 검사 통과.
- 대상 Sublist3r 프로그램과 네트워크 스캔은 실행하지 않았다.
- VSIX는 수정/생성하지 않았으며 기존 artifact 해시가 유지됨을 확인했다.

## 재현 및 산출물

```sh
python3 -W ignore::SyntaxWarning -m unittest discover -s tests -q
python3 -W ignore::SyntaxWarning -B scripts/evaluate_sublist3r.py --output validation/sublist3r_2026_10_22/improved
```

- `results.json`: 점수, 입력/엔진 해시, TP/FP/FN 전체, lambda 정규화 표.
- `comparison.json`: 동일 입력 확인과 전후/Flask 비교.
- `predicted_evidence.json`: 간선별 소스 위치 및 근거.
- `analysis/`: 원본 AST·심볼·그래프·CSV/HTML.
- `flask/`: 최신 엔진의 Flask 재실행 및 검토 결과.
- 상위 `before/results.json`: 개선 전 점수 보존본.

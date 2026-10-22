# 현재 엔진의 Sublist3r 평가 — 2026-10-22

이 문서는 **개선 전 측정**을 보존한다. 최신 결과는
[`improved/REPORT_KO.md`](improved/REPORT_KO.md)를 참고한다.

`knitcode_test/benchmark/PyAnalyzer/Data/RQ3/macro-benchmark C`의 평가용 소스와
원본 정답을 읽었다. 소스 4개 파일과 정답 JSON의 SHA-256은 2026-10-16 기존 평가 기록과
동일함을 검사했다. 별도의 `benchmark/Sublist3r` 복사본은 사용하지 않았다.
소스·정답·분석 엔진·VSIX는 변경하지 않았다. 평가 스크립트와 결과만 추가했다.

## 함수 호출 그래프 비교

분석 대상 내부 caller–callee 이름을 정확히 비교하고 중복 호출 쌍을 제거한다.
기존 정답의 내부 쌍 **115개를 모두 유지**한다. 예측에서는 `CALLS`로 연결한 함수·메서드·lambda를
비교하며, `INSTANTIATES`의 클래스 노드는 별도 집계한다. `__init__` 호출은 함수 비교에 포함한다.
suffix matching, 생성자 치환, 정답 교정은 적용하지 않았다.

| 지표 | 현재 knitcode |
|---|---:|
| 정답 쌍 | 115 |
| 예측 함수 호출 쌍 | 83 |
| TP | 83 |
| FP | 0 |
| FN | 32 |
| Precision | 100.0% |
| Recall | 72.2% |
| F1 | 83.8% |

이것은 원본 benchmark와의 일치도다. FP=0이 모든 런타임에서 분석기가 무오류라는 뜻은 아니다.
현재는 이 정답 기준으로는 미탐이 주된 문제다.

참고로 `knitcode_test`의 별도 엔진은 같은 소스·정답으로 TP=115, FP=0, FN=0을 기록했다.
그 수치는 기존 기록이며 이번에는 이전 엔진을 다시 실행하지 않았다.

## 클래스 간선을 포함한 원시 비교도 보존

현재 제품 그래프는 클래스 생성 자체에 `INSTANTIATES` 간선 14쌍을 추가한다.
원본 정답에는 이 클래스 노드들이 함수 호출 대상으로 없으므로, 이를 그대로 합치면
예측 97, TP=83, FP=14, FN=32, Precision=85.6%, Recall=72.2%, F1=78.3%다.
추가 14쌍은 모두 클래스 생성 표현 범위의 차이이며 이 사실만으로 실제 호출 오탐이라고
단정하지 않았다. 제품 그래프에서 해당 간선을 삭제하지 않았다.

또한 기존 도구의 `source-declared-functions-v1` 방식처럼 양쪽을 현재 선언 함수에 투영하면
정답이 114쌍으로 줄어 TP=83, FP=0, FN=31, F1=84.3%가 된다.
이때 빠지는 정답은 `extract_subdomains → extract_subdomains.<lambda1>`다.
표기 및 callback 표현 검토가 필요하므로 이를 제외한 수치를 기본 점수로 사용하지 않았다.

## 미탐 및 검증

누락은 주로 `enumratorBase.print_`, `enumratorBase.get_response`,
`enumratorBaseThreaded.__init__`, 상속된 `enumerate`와 lambda callback 관계다.
`multiprocessing.Process`라는 외부 기반 클래스가 상속에 포함되면 현재 C3 MRO는
`unknown_base`로 남고, 일부 소스 내부 상속 후보도 연결을 유보하는 것이 확인됐다.
32개 전체의 원인 검토·수정은 이번 측정 범위에서 수행하지 않았다.

호출 지점은 515개, 내부 연결 지점은 91개다. 이 수치는 중복 제거한 정답 쌍 점수와 다르다.
파싱 오류는 없고, 구조 16개·상태 10개·실제 AST 위치 검증이 통과했다.
검증은 대상 프로그램 실행 없이 수행했다.

## 재현 및 파일

```sh
python3 -W ignore::SyntaxWarning -B scripts/evaluate_sublist3r.py
```

- `results.json`: 세 평가 계약의 점수, TP/FP/FN 전체 목록, 입력·엔진 해시.
- `predicted_evidence.json`: 각 간선의 호출 위치와 추론 근거.
- `analysis/`: 원래 AST·심볼·그래프 및 HTML/CSV 보고서.
- `verification.log`: 구조·상태·소스 위치 검사 결과.

재현 스크립트는 기존 release 기록과 소스·정답 해시가 달라지면 평가를 중단한다.

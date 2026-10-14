# KnitCode 작업 체크포인트

기록일: 2026-10-14 (Asia/Seoul)

## 현재 상태

Python 정적 호출 분석기의 첫 안정화와 Flask 및 PyAnalyzer 베이스라인 평가를 완료했습니다. 다음 분석 개선은 아직 적용하지 않았습니다.

- lambda 본문 중복 순회 제거
- 호출 순서와 무관하게 메서드 노드의 타입·클래스·줄 번호 유지
- 로컬 및 `from ... import Class` 생성자 해석 통일
- `pytest.ini`로 기본 수집 범위를 `tests/`로 제한
- 기존 10개 + 회귀 8개 = 테스트 18개 통과

## 결과와 재현 자료

- Flask: `reports/flask-baseline-2026-10-14/README.md`
  - 24파일, 9,507줄, 호출 관계 1,230개 중 237개 해석 (19.27%)
  - ground truth가 없어 정확도/F1을 측정한 것은 아님
  - Flask 커밋: `d086db856be187255b8ec61ef409357393020f32`
- PyAnalyzer: `reports/pyanalyzer-baseline-2026-10-14/README.md`
  - Sublist3r: TP 115 / FP 0 / FN 0, F1 1.0000
  - autojump: TP 134 / FP 22 / FN 83, F1 0.7185
  - face_classification: TP 95 / FP 2 / FN 4, F1 0.9694
  - fabric: 상대 import 해석 예외로 중단, 점수 없음
  - 테스트·예제 등을 제외한 핵심 `.py` 소스 줄 수가 Sublist3r보다 큰 프로젝트만 선정
- 실행 스크립트: `scripts/flask_baseline.py`, `scripts/pyanalyzer_baseline.py`
- 전체 호출, 차이 목록, 입력 및 분석기 해시는 각 보고서 디렉터리의 JSON/CSV에 보관

## 다음 작업

1. fabric의 `executor.py:84`, `ConnectionCall.make_context → Connection`에서 발생하는 상대 import 오류부터 해결한다.
   - `from . import Connection`의 `ImportFrom.module`은 `None`이다.
   - resolver의 `module.replace()` 예외를 재현하는 회귀 테스트를 먼저 추가한다.
   - 단순히 예외를 건너뛰지 말고 패키지 및 상대 import 의미를 고려한다.
2. 새 출력 폴더로 PyAnalyzer를 재평가하고 기존 베이스라인과 비교한다.
3. autojump의 중첩 함수 전체 이름/scope 처리를 개선한다.
   - 현재 `ArgumentParser.consume_optional` 대신 ground truth는 `ArgumentParser._parse_known_args.consume_optional`을 사용한다.
4. 이후 파일 간 상속과 외부 부모 클래스 이름 충돌을 개선한다.
   - Flask `testing.py:86`의 외부 부모 생성자가 로컬 동명 클래스 생성자로 잘못 연결된다.

변경 시 기존 테스트와 Sublist3r의 115개 edge를 유지한다. 원본 베이스라인을 덮어쓰지 않는다. 다음 작업은 계획이며 아직 구현되지 않았다.

## 검증 명령

프로젝트 루트에서 실행한다.

```bash
PYTHONDONTWRITEBYTECODE=1 Knitcode/bin/python -m pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 Knitcode/bin/python -m analyzer.evaluate
PYTHONDONTWRITEBYTECODE=1 Knitcode/bin/python scripts/pyanalyzer_baseline.py --output reports/pyanalyzer-next
PYTHONDONTWRITEBYTECODE=1 Knitcode/bin/python scripts/flask_baseline.py --output reports/flask-next
```

## 로컬 환경 주의 사항

`benchmark/`, 가상환경 `Knitcode/`, 생성 HTML 및 `lib/`는 기존 `.gitignore` 규칙으로 커밋에서 제외된다. 현재 머신에는 입력 소스와 HTML이 남아 있다. 다른 머신에서는 동일한 benchmark 데이터와 Python 의존성을 별도로 준비해야 한다. 보고서와 JSON/CSV, 재현 스크립트는 체크포인트에 포함한다. Flask HTML은 스크립트로 재생성할 수 있다.

베이스라인의 `knitcode_head`는 측정 당시 HEAD이며, 당시 안정화 변경은 미커밋 상태였다. 실제 구현 비교에는 `analyzer_sha256`을 사용한다.

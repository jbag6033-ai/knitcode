# Flask 분석 베이스라인

2026-10-14, 분석기 구현을 변경하지 않고 현재 작업 트리로 측정했습니다.

- Flask 커밋: `d086db856be187255b8ec61ef409357393020f32`
- 범위: `benchmark/Flask/src/flask` 전체. 테스트, 예제, 외부 의존성 소스 제외.
- Python: `summary.json`에 기록. 분석기 및 Flask 소스 SHA-256도 함께 보관.
- 분석기에는 이전 안정화 작업의 미커밋 변경이 포함되어 있으므로 Git HEAD만으로 구현을 식별하면 안 됩니다.

| 항목 | 결과 |
|---|---:|
| 분석 파일 | 24 |
| 소스 줄 수 (주석·docstring·빈 줄 포함) | 9,507 |
| AST의 실제 Call 표현 | 1,223 |
| visitor의 호출 관계 기록 | 1,230 |
| 대상 해석 성공 기록 | 237 |
| 미해결 기록 | 993 |
| 호출 관계 기록 기준 해석 비율 | 19.27% |
| 그래프 노드 | 363 |
| 그래프 edge 기록 | 237 |
| 중복 제거 caller–callee 쌍 | 202 |
| 분석 및 그래프 구성 시간 (단일 실행, HTML 생성 제외) | 약 0.036초 |

해석 비율은 정확도, Precision, Recall 또는 F1이 아닙니다. Ground truth가 없으며, 미해결 기록에는 내장 함수와 외부 API도 포함됩니다. 해석 성공 기록에도 오연결이 있을 수 있습니다. visitor는 lambda 표현에 대한 합성 관계를 포함하며, 중첩 호출 표현을 단순화하므로 호출 기록 수는 실제 AST Call 수와 다릅니다. 노드 수 또한 전체 정의 수 또는 분석 커버리지를 의미하지 않습니다.

## 소스로 대조한 대표 사례

| 호출 위치 | 현재 결과 | 소스 대조 |
|---|---|---|
| `app.py:614`, `Flask.update_template_context`의 `self.ensure_sync(func)` | `app.py:1065`, `Flask.ensure_sync` | 같은 클래스 메서드 연결은 맞음. 반환된 callable의 호출도 같은 이름으로 기록되어 동일 위치의 관계가 중복됨. 실제 콜백 대상을 해석했다는 의미는 아님. |
| `app.py:321`, `Flask.__init__`의 `super().__init__` | 미해결 | 내부 부모 `sansio/app.py`의 `App.__init__` 호출 누락. |
| `app.py:356`, `Flask.__init__`의 `self.add_url_rule` | 미해결 | 내부 부모 `sansio/app.py:606`의 `App.add_url_rule` 호출 누락. |
| `testing.py:86`, `EnvironBuilder.__init__`의 `super().__init__` | 자기 자신의 `testing.py:49` 생성자로 연결 | 부모는 외부 `werkzeug.test.EnvironBuilder`. 모듈 접두어를 제거하면서 로컬 동명 클래스를 선택한 잘못된 내부 edge. |

이 표는 제한된 수동 점검이며 전체 graph의 정확도 평가가 아닙니다. 다음 개선 우선순위는 상대 import와 파일 간 상속 해석, 외부 부모 클래스의 이름 충돌 방지입니다. 이 베이스라인에는 해당 수정이 반영되지 않았습니다.

## 저장된 결과

- `summary.json`: 집계, 파일별 통계, 실행 환경, 소스 해시, 미해결 이름 상위 목록
- `calls.json`: 미해결을 포함한 resolver 전체 결과
- `graph.json`: 그래프 데이터
- `unresolved.csv`: 파일·caller·callee·줄 번호별 미해결 목록
- `graph.html`: 현재 시각화 코드로 생성한 그래프 (로컬 `lib/` 자산과 함께 보관)

HTML과 `lib/`는 기존 `.gitignore` 규칙으로 버전 관리에서 제외됩니다. JSON·CSV와 실행 스크립트로 재생성할 수 있습니다.

## 재실행

프로젝트 루트에서 다른 출력 폴더를 지정하여 기준 결과를 보존합니다.

```bash
PYTHONDONTWRITEBYTECODE=1 Knitcode/bin/python scripts/flask_baseline.py --output reports/flask-next
PYTHONDONTWRITEBYTECODE=1 Knitcode/bin/python -m pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 Knitcode/bin/python -m analyzer.evaluate
```

이번 실행에서 프로젝트 테스트 18개가 통과했고, Sublist3r은 TP 115 / FP 0 / FN 0, Precision·Recall·F1 모두 1.0000을 유지했습니다. Flask는 AST로 읽었으며 프레임워크를 실행하거나 Flask 자체 테스트를 실행한 것은 아닙니다.

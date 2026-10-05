# KnitCode

KnitCode는 **Python 프로젝트의 코드 관계를 정적 분석하고 시각화하는 도구**입니다.

Python의 AST(Abstract Syntax Tree)를 기반으로 소스 코드를 분석하여 함수, 클래스, import, 함수 호출 등의 정보를 추출하고, 실제 코드 정의를 추적하여 **caller → callee 관계를 Call Graph 형태로 구성**합니다.

분석한 결과는 그래프로 시각화할 수 있으며, 정답 데이터가 존재하는 프로젝트에 대해서는 Precision, Recall, F1-score를 이용한 정량 평가도 수행할 수 있습니다.

---

## 주요 기능

현재 KnitCode에서는 다음 기능을 지원합니다.

- Python 소스 코드 AST 파싱
- 함수 및 클래스 정의 추출
- `import`, `from ... import ...` 분석
- 함수 및 메서드 호출 추출
- Caller → Callee 관계 분석
- 파일 간(Cross-file) 함수 호출 추적
- 클래스 상속 관계 분석
- `self.method()` 호출 해석
- `super().method()` 호출 해석
- 명시적인 부모 클래스 메서드 호출 해석
- 클래스 생성자 호출 → `__init__` 연결
- 변수에 저장된 callable을 통한 간접 호출 분석
- List Comprehension 내부 호출 분석
- Nested Lambda Scope 처리
- Call Graph 생성
- Interactive HTML 그래프 시각화
- Precision / Recall / F1-score 기반 성능 평가

---

## 분석 과정

KnitCode의 기본 분석 파이프라인은 다음과 같습니다.

```text
Python Project
      │
      ▼
  parser.py
      │
      ▼
  visitor.py
      │
      ▼
 resolver.py
      │
      ▼
   graph.py
      │
      ├──────────────► evaluate.py
      │
      ▼
 visualize.py
      │
      ▼
Interactive Call Graph
```

### `parser.py`

Python 파일을 읽고 `ast.parse()`를 이용하여 소스 코드를 AST로 변환합니다.

### `visitor.py`

`ast.NodeVisitor`를 기반으로 AST를 순회하면서 다음과 같은 정보를 수집합니다.

- 함수 정의
- 클래스 정의
- import
- 함수 및 메서드 호출
- scope
- source location

### `resolver.py`

`visitor.py`에서 수집한 호출 정보를 실제 코드 정의와 연결합니다.

단순한 함수 호출뿐만 아니라 파일 간 호출, 클래스 메서드, 상속 관계, `self`, `super()` 등의 Python 코드 패턴을 고려하여 caller와 callee를 해석합니다.

### `graph.py`

분석된 caller → callee 관계를 이용하여 프로젝트의 Call Graph를 구성합니다.

### `visualize.py`

생성된 Call Graph를 Interactive HTML 형태로 시각화합니다.

### `evaluate.py`

KnitCode가 분석한 Call Edge와 Ground Truth를 비교하여 다음 지표를 계산합니다.

- Precision
- Recall
- F1-score

---

## 프로젝트 구조

```text
knitcode/
├── analyzer/
│   ├── __init__.py
│   ├── parser.py
│   ├── visitor.py
│   ├── resolver.py
│   ├── graph.py
│   ├── visualize.py
│   └── evaluate.py
│
├── git_analyzer/
│   ├── history.py
│   └── cochange.py
│
├── backend/
│   └── api.py
│
├── frontend/
│
├── tests/
│   ├── fixtures/
│   ├── test_parser.py
│   └── test_advanced_project.py
│
├── .gitignore
└── README.md
```

---

## Benchmark

KnitCode의 Call Graph 분석 성능을 확인하기 위해 **PyAnalyzer benchmark의 Sublist3r 프로젝트**를 이용하여 평가했습니다.

평가 대상은 Sublist3r 프로젝트 내부의 함수 및 메서드 호출 관계입니다.

### 최종 결과

| 평가 지표 | 결과 |
|---|---:|
| Ground Truth Edge | 115 |
| True Positive | 115 |
| False Positive | 0 |
| False Negative | 0 |
| Precision | 1.0000 |
| Recall | 1.0000 |
| F1-score | 1.0000 |

현재 구현에서는 평가 대상인 **Sublist3r의 Project-internal Call Edge 115개를 모두 정확하게 탐지**했습니다.

---

## 분석 기능 개선 과정

초기 구현에서는 기본적인 함수 호출 관계만 분석할 수 있었지만, 실제 Python 프로젝트를 분석하면서 다양한 호출 패턴을 순차적으로 지원하도록 개선했습니다.

```text
기본 함수 호출 분석
        ↓
상속 / self 메서드 처리
        ↓
super() / 부모 클래스 메서드 처리
        ↓
클래스 생성자 → __init__ 처리
        ↓
Callable Collection / List Comprehension 처리
        ↓
Cross-module Import 처리
        ↓
Nested Lambda Scope 처리
```

이러한 개선을 통해 Sublist3r benchmark에서 최종적으로 다음 성능을 달성했습니다.

```text
Precision = 1.0000
Recall    = 1.0000
F1-score  = 1.0000
```

---

## 실행 방법

프로젝트 루트 디렉터리에서 실행합니다.

### Call Graph 생성

```bash
python -m analyzer.graph
```

### 그래프 시각화

```bash
python -m analyzer.visualize
```

### Benchmark 평가

```bash
python -m analyzer.evaluate
```

### 테스트 실행

```bash
pytest
```

---

## 현재 범위

현재 KnitCode는 **Python 프로젝트의 정적 분석**을 중심으로 개발하고 있습니다.

Sublist3r benchmark에서 F1-score 1.0을 달성했지만, 이는 현재 평가한 Sublist3r의 Project-internal Call Edge를 기준으로 한 결과입니다.

따라서 모든 Python 프로젝트의 호출 관계를 완벽하게 분석할 수 있다는 의미는 아닙니다. Python의 동적 특성으로 인해 runtime monkey patching, reflection, 동적으로 생성되는 함수 호출 등은 추가적인 분석 방법이 필요할 수 있습니다.
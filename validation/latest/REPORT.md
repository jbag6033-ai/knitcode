# 최신 전체 호출 평가

2026-10-22 기준. 원본 PyCG 입력 범위와 전체 ground truth, 원본 채점 함수로 평가했다. 프로젝트 소스와 정답은 변경하지 않았다.

| 프로젝트 | TP | FP | FN | 정밀도 | 재현율 | F1 |
|---|---:|---:|---:|---:|---:|---:|
| autojump | 382 | 24 | 153 | 94.09% | 71.14% | 81.02% |
| asciinema | 244 | 47 | 96 | 83.85% | 71.85% | 77.39% |
| fabric | 245 | 42 | 136 | 85.37% | 64.30% | 73.35% |
| face_classification | 410 | 40 | 25 | 91.11% | 94.25% | 92.66% |

각 프로젝트 JSON은 고유 caller–callee 쌍의 TP/FP/FN, 입력 해시, 원본 재현 패키지 일치 검사 결과를 포함한다. 원본 scorer는 정답 배열의 중복도 재현율에 반영한다. 원본 엔진 해시는 이 결과를 측정한 시점의 기록이다.

Fabric F1은 73.35%이며 논문 PyCG의 반올림된 P/R에서 계산한 약 75.96%보다 낮다. 실제 소스에 존재하는 property 접근 누락 후보와 import 경로 차이가 정답 기준 FP에 포함될 수 있다. 이 결과는 임의 프로젝트의 런타임 정확도 보장이 아니다.

## 재평가

원본 benchmark 데이터는 이 저장소에 포함하지 않는다. 기본 데이터 위치는 저장소와 형제 디렉터리의 `knitcode_test/benchmark/PyAnalyzer/Data/RQ3/macro-benchmark C`이다.

```sh
python3 scripts/evaluate_paper.py
python3 -m unittest discover -s tests -q
```

원본 scorer 및 라이선스: `scripts/reference/pycg/`. [논문](https://arxiv.org/pdf/2103.00587), [재현 패키지](https://doi.org/10.5281/zenodo.4456583).

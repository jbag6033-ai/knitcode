# 공개 검증 스냅샷 · 2026-10-16

Python 3.12.2, pytest 9.1.1 환경에서 테스트 139개 통과. 기본 모드는 원본 ground truth와 프로젝트 내부 unique caller–callee pair를 비교하며 외부 입력 계약과 정답 교정안을 적용하지 않는다.

| 프로젝트 | TP | FP | FN | F1 |
|---|---:|---:|---:|---:|
| Sublist3r | 115 | 0 | 0 | 1.0000 |
| autojump | 205 | 15 | 12 | 0.9382 |
| fabric | 44 | 8 | 18 | 0.7719 |
| face_classification | 97 | 4 | 2 | 0.9700 |
| asciinema | 131 | 50 | 13 | 0.8062 |

소스/정답/분석기/평가 runner 해시와 수렴 정보는 [summary.json](summary.json)에 있다. 결과는 정답과의 일치도이며 모든 가능한 Python 동작의 완전 분석을 뜻하지 않는다. source/정답 표기 차이도 raw FP/FN에 포함한다.

## 재현

저장소 루트에서 실행한다. 외부 benchmark 저장소는 별도로 내려받으며 Git에 다시 포함하지 않는다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
git clone https://github.com/2024icse/PyAnalyzer.git benchmark/PyAnalyzer
git -C benchmark/PyAnalyzer checkout ea143ef8bdec2b5f8841bb600b348f0975b90349
.venv/bin/python scripts/pyanalyzer_baseline.py --include-smaller --output reports/local-reproduction
```

`asciinema`는 Sublist3r보다 작으므로 --include-smaller로 명시적으로 포함한다. 실행 시간은 환경에 따라 달라진다. Git/JavaScriptCore 등 환경별 검증과 실제 Extension Host 화면 확인은 구분한다.

## 외부 입력 조건의 별도 평가

[entrypoints.example.json](entrypoints.example.json)은 asciinema의 공개 pty.record에 raw writer 및 TerminalNotifier를 전달한다는 명시적 가정이다. 원본 소스만으로 이 외부 입력을 자동 발견했다는 뜻이 아니다.

```sh
.venv/bin/python scripts/pyanalyzer_baseline.py --projects asciinema --include-smaller --entrypoints reports/release-2026-10-16/entrypoints.example.json --output reports/local-entrypoints
```

이 조건에서는 원본 정답 기준 134/50/10, F1 0.8171이다. 기본 결과와 혼합하지 않는다. 별도 정답 교정 실험은 이 공개 기본 평가에 적용하지 않았다.

## 배포 범위

분석기/JSON export/Git 이력/두 확장 소스, 테스트, 패키징/기본 평가/성능 측정 도구를 포함한다. 중간 probe, 전체 반복 call JSON, 특정 로컬 산출물에 의존하는 일회성 감사 스크립트, benchmark 복사본, VSIX는 새 커밋에서 제외했다. 이전 커밋의 기존 baseline 자료는 이력으로 유지한다.

설치 파일은 README의 두 패키징 명령으로 생성한다. 실제 VS Code 설치·화면 배치는 자동 테스트만으로 보증하지 않는다.

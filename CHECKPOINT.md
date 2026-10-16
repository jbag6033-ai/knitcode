# KnitCode 작업 체크포인트

기준일: 2026-10-16 (Asia/Seoul)

## 현재 구현

- Python AST 호출 해석과 bounded ValueFlow: 상속, 생성자, 메서드, 인자/반환값, 컨테이너, property, with, lambda, 제한된 guarded getattr.
- 불변 AST/정의 정보는 분석 인스턴스별로 캐시하며 상태 의존 expression/invoke 결과는 캐시하지 않음.
- argparse 등록/Namespace 전달, 명시 문자열 argv의 subcommand/alias 선택, parser factory의 최대 3개 호출 위치 문맥, 제한된 if/else guard, parse 위치 이전 default 재생.
- opt-in 외부 입력 계약: 함수/매개변수/프로젝트 클래스 검증 후 instance 값을 입력으로 제공. API 및 --entrypoints CLI 지원. target 코드를 실행하거나 정답 edge를 직접 주입하지 않음.
- 두 독립 확장: KnitCode / KnitCode Flow. 기존 화면·명령·설정 유지. 소스 패키징 시 현재 분석기를 각각 번들. 설치된 구버전 VSIX는 자동 업데이트되지 않음.

## 최신 검증

테스트 **139개 통과**. 기본 모드의 5개 프로젝트 전체 raw edge/호출 레코드는 직전 개선 전후 동일함을 검증.

| 프로젝트 | TP | FP | FN | F1 |
|---|---:|---:|---:|---:|
| Sublist3r | 115 | 0 | 0 | 1.0000 |
| autojump | 205 | 15 | 12 | 0.9382 |
| fabric | 44 | 8 | 18 | 0.7719 |
| face_classification | 97 | 4 | 2 | 0.9700 |
| asciinema | 131 | 50 | 13 | 0.8062 |

최근 parser snapshot 수정은 재현된 오연결을 복구했으나 현재 benchmark에 해당 패턴이 없어 위 점수는 유지됨.

## 해석 시 구분

- asciinema는 초기 117/45/27에서 기본 131/50/13으로 개선. FP 50개는 통제된 입력과 네트워크/PTY/프로세스 경계 대체 하에서 호출 근거를 관찰. 전체 실제 환경에서의 완전성이나 benchmark 작성 의도 증명은 아님.
- asciinema 남은 13개: 소스/정답 차이 10개 + 공개 API 입력 범위 3개. 명시적 입력 계약 적용 시 원본 정답 기준 134/50/10, F1 0.8171. 별도 교정안까지 적용한 145/39/0, F1 0.8815는 입력 가정 및 정답 변경 효과를 포함하며 기본 정확도가 아님.
- autojump의 생성자/__call__, MRO/이름 차이는 별도 정답 검토 대상으로 조사. 기본 원시 점수는 유지.
- 일반적인 완전한 경로/객체 민감 분석은 아님. 옵션 arity, namespace 주입, 모든 복합 조건, 함수 사이 임의 mutation 순서, 같은 호출 위치의 반복 객체 완전 구분은 미지원.
- 실제 Extension Host 설치/화면 및 대형 저장소 전체 성능, 캐시 peak memory는 별도 검증 필요.

## 공개 자료와 로컬 기록

공개할 결과는 [release 검증 요약](reports/release-2026-10-16/README.md)에 모음. 상세 source/GT/analyzer 해시도 해당 폴더에 보관. 재현에 필요한 benchmark URL/commit 및 명령을 기록함.

전체 과거 체크포인트/README는 로컬 `reports/local-publication-backup-2026-10-16/`에 백업했으며 기존 상세 실험 자료도 로컬에 보존. benchmark 복사본, 중간 보고서, 구형 VSIX를 이번 새 커밋에 추가하지 않음. 이전 커밋의 기존 baseline 자료는 이력을 유지.

다음 정확도 개선은 실제 실패 관계를 먼저 재현하고 수정하며, 전체 TP/FP 목록과 5개 프로젝트 회귀를 확인할 것. 정답 수정 효과·외부 입력 조건·기능 확장을 원본 benchmark 개선과 혼동하지 않을 것.

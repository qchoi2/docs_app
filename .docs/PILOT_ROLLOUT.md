# PILOT_ROLLOUT — 소규모 파일셋으로 먼저 돌린 뒤 전체로 확장하는 운용 절차

## 목적
처음부터 2,000개 이상의 계약서를 전부 색인하지 않고, 일부 샘플로 성능·검색 품질·분류 규칙을 검증한 뒤 전체 코퍼스로 확장한다.

## PC 로컬 실행 주의

기본 환경은 Windows PC 로컬 실행이다. 원본 계약서는 PC 로컬 폴더 또는 읽기 전용 네트워크 드라이브에 둘 수 있지만, `--out`으로 지정하는 `cs_index`는 반드시 PC 로컬 디스크에 둔다. SQLite 파일을 네트워크 드라이브에 두지 않는다.

## 권장 방식
가장 안전한 방식은 **최종 운영 루트를 그대로 두고, root 기준 상대경로 목록(`--file-list`)으로 일부 파일만 먼저 색인하는 것**이다. 이렇게 하면 파일을 복사하지 않아도 되고, 나중에 전체 파일을 추가 색인할 때 path 충돌이 생기지 않는다.

예:

```text
pilot_files.txt
01_SPA/sample_001.docx
01_SPA/sample_002.docx
02_SHA/sample_003.docx
```

```bash
python3 index_contracts.py --root /path/to/contracts_root --out ./cs_index \
  --file-list pilot_files.txt --batch-label pilot_001
python3 eval_search.py --out ./cs_index

# 만족 후 같은 root/out에 전체 파일 증분 추가
python3 index_contracts.py --root /path/to/contracts_root --out ./cs_index --batch-label full_001
python3 eval_search.py --out ./cs_index
```

직접 파일 목록을 고르기 어렵다면 결정적 샘플링을 쓴다.

```bash
python3 index_contracts.py --root /path/to/contracts_root --out ./cs_index \
  --sample 200 --sample-seed 42 --batch-label pilot_001
```

`--file-list`와 `--sample`은 동시에 쓰지 않는다.

## 피해야 할 방식
파일럿을 위해 계약서를 임시 폴더에 복사했다가 나중에 전체 원본 폴더를 `--root`로 바꾸면 path가 달라져 이동/삭제/복원 리포트가 복잡해질 수 있다. 이 경우에는 전체 운영용 `cs_index`를 새로 만드는 것이 안전하다.

```bash
# 임시 파일럿 색인
python3 index_contracts.py --root /tmp/pilot_contracts --out ./cs_index_pilot --batch-label pilot_001

# 전체 운영 색인은 새로 생성
python index_contracts.py --root "D:\Contracts\contracts_root" --out "C:\contract-search\cs_index_full" --batch-label full_001 --full
```

## 파일럿 완료 기준
다음 기준을 만족하면 전체 파일을 추가한다.

1. 파일럿 문서 100~300건 기준 색인이 정상 완료된다.
2. `status=ok` 비율이 90% 이상이다. 단, `unsupported`는 분모에서 제외할 수 있다.
3. `unsupported` 제외 후 `empty/error` 비율이 10% 이하이거나, 초과 원인이 암호 PDF·스캔 PDF 등으로 설명 가능하다.
4. 미분류 ctype 비율이 20% 이하이거나, `manual_overrides.yaml`로 보정 가능하다.
5. 주요 유형(SPA/SHA/SSA)의 오분류가 수동 보정 가능한 수준이다.
6. 자주 사용할 질의 10개 중 7개 이상이 기대 결과를 상위 10개 안에 반환한다.
7. 검색 결과 JSON에 `why`, `score_breakdown`, `snippet_paras`가 표시된다.
8. 단일 검색은 대체로 3초 안팎으로 끝난다.
9. `eval_search.py`가 오류 없이 완주한다. 실코퍼스 기준 expected_files가 없는 문항은 부분채점이어도 된다.

## 파일럿 중 확인할 명령

```bash
# 검색
python3 search_contracts.py --out ./cs_index --type SPA --kw earnout --limit 10 --json

# 특정 결과 디버깅
python3 inspect_file.py --out ./cs_index --file-key <FILE_KEY> --show-dup-group

# 스니펫 주변 원문 확인
python3 open_text.py --out ./cs_index --file-key <FILE_KEY> --para 42 --context 3

# 전체 확장 전 Phase 2 추출 후보 미리 보기
python3 plan_extract.py --out ./cs_index --limit 100
```

## 답변 표기 원칙
파일럿 단계에서 Claude Code 또는 answer_quick.py가 답할 때는 반드시 “현재 색인된 파일럿 코퍼스 기준”이라고 표시한다. 전체 코퍼스 추가 후에는 `batch_label`이 pilot/full로 섞일 수 있으므로 필요한 경우 결과 표에 batch_label을 포함한다.

## 전체 확장 후 할 일
1. `index_contracts.py` 증분 실행 리포트에서 신규/이동/삭제/missing 건수를 확인한다.
2. `eval_search.py`를 다시 실행한다.
3. `query_log.jsonl`과 `agent_log.jsonl`을 보고 golden_queries.yaml에 실제 자주 쓰는 질의를 보강한다.
4. 미분류 폴더와 오분류 파일은 `manual_overrides.yaml`에 반영한다.
5. 빈 PDF·암호 PDF가 많으면 OCR 도입 여부를 별도로 결정한다.

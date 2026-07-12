# T3 clause_map quality sample - SHA/MOU/ATA-BTA

- Date: 2026-07-12
- Scope: each 5 representative ok documents from SHA, MOU, ATA/BTA after full .doc conversion and T3 v2 enrichment.
- Method: deterministic txt-cache spot check. `OK` means the stored paragraph range contains the clause keyword family; `OK(absent)` means the same keyword family was not detected in the document; `manual-review` means present/location should be manually reviewed.
- No changes were made to `extract_prompt_v1.md` or `term_dict.yaml`.

## SHA sample

### `864f6db985afc5a9` - 03-1_SHA_국문/(기존) Stella-11번가- SHA-#2616210-v21-Drag 강함(27241.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 23-26 | OK |
| 선행조건 | false | - | OK(absent) |
| 확약 | true | 40-43 | OK |
| 손해배상 | true | 7-10 | OK |
| 해제 | true | 37-40 | OK |
| 경업금지 | true | 116-119 | OK |
| 분쟁해결 | true | 102-105 | evidence-ok/range-review |

### `87d047c3b929ed20` - 03-1_SHA_국문/(유사) Jupiter-에스케이온-투자자들, SK이노베이션-SHA-체결본-20221202-Drag 강함(35496.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 54-57 | OK |
| 선행조건 | false | - | OK(absent) |
| 확약 | true | 82-85 | OK |
| 손해배상 | true | 51-54 | OK |
| 해제 | true | 65-68 | OK |
| 경업금지 | true | 137-140 | OK |
| 분쟁해결 | true | 72-75 | OK |

### `2ff313fccd7963cb` - 03-1_SHA_국문/(유사) 리딩에이스캐피탈_주주간계약서-#5154064-v8-Drag 강함(27242.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | false | - | OK(absent) |
| 선행조건 | false | - | OK(absent) |
| 확약 | true | 11-14 | OK |
| 손해배상 | true | 36-39 | OK |
| 해제 | true | 51-54 | OK |
| 경업금지 | false | - | OK(absent) |
| 분쟁해결 | true | 90-93 | evidence-ok/range-review |

### `753aeef4b323e391` - 03-1_SHA_국문/(유사) 순돌이드론_주주간계약_초안_BKL_20201222v1-Drag 강함(27243.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 55-58 | OK |
| 선행조건 | false | - | OK(absent) |
| 확약 | true | 19-22 | OK |
| 손해배상 | true | 55-58 | OK |
| 해제 | true | 22-25 | OK |
| 경업금지 | false | - | OK(absent) |
| 분쟁해결 | true | 149-152 | OK |

### `f2e4f205454dec9a` - 03-1_SHA_국문/(유사) 파두-BKL-#2737259-v7A-Forward_SHA-Drag 강함(27240.v1).doc

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 59-62 | OK |
| 선행조건 | false | - | OK(absent) |
| 확약 | true | 68-71 | OK |
| 손해배상 | true | 24-27 | OK |
| 해제 | true | 37-40 | OK |
| 경업금지 | true | 70-73 | OK |
| 분쟁해결 | true | 49-52 | OK |

## MOU sample

### `30fae2c6d27a9f8c` - 09-1_MOU_양해각서_국문/(간단; 실사비용 부담) KTB (베디베로)_MOU(30078.v1).doc

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 38-41 | OK |
| 선행조건 | true | 31-34 | OK |
| 확약 | true | 31-34 | OK |
| 손해배상 | true | 17-20 | OK |
| 해제 | true | 39-42 | OK |
| 경업금지 | true | 39-42 | OK |
| 분쟁해결 | true | 18-21 | OK |

### `d4cabc19206b1697` - 09-1_MOU_양해각서_국문/Ace(에임시스템)_양해각서_매수인 초안_170407 (K)(17878.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 27-30 | OK |
| 선행조건 | true | 42-45 | OK |
| 확약 | true | 42-45 | OK |
| 손해배상 | true | 42-45 | OK |
| 해제 | true | 47-50 | OK |
| 경업금지 | true | 42-45 | OK |
| 분쟁해결 | true | 53-56 | evidence-ok/range-review |

### `07ae56ed2b4c19ba` - 09-1_MOU_양해각서_국문/Apex_양해각서_seller draft(17879.v1).doc

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | false | - | OK(absent) |
| 선행조건 | false | - | OK(absent) |
| 확약 | false | - | OK(absent) |
| 손해배상 | false | - | OK(absent) |
| 해제 | true | 22-25 | OK |
| 경업금지 | false | - | OK(absent) |
| 분쟁해결 | true | 30-33 | OK |

### `db48c96960abaeae` - 09-1_MOU_양해각서_국문/Apex_양해각서_매수인 1st markup (out to seller)(17880.v1).doc

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | false | - | OK(absent) |
| 선행조건 | false | - | OK(absent) |
| 확약 | false | - | OK(absent) |
| 손해배상 | false | - | OK(absent) |
| 해제 | true | 22-25 | OK |
| 경업금지 | false | - | OK(absent) |
| 분쟁해결 | true | 29-32 | OK |

### `df62694f21e3def0` - 09-1_MOU_양해각서_국문/Bidder A. MOU Markup(30077.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 23-26 | OK |
| 선행조건 | true | 130-133 | OK |
| 확약 | true | 57-60 | OK |
| 손해배상 | true | 85-88 | OK |
| 해제 | true | 16-19 | OK |
| 경업금지 | false | - | OK(absent) |
| 분쟁해결 | true | 34-37 | OK |

## ATA/BTA sample

### `2451d23c54c1327a` - 04-1_ATA_BTA_국문/(2021) 엘지전자 영업양수도 매각 - 매도인 Project Cupid_Kick-off Material_bkl_2021 0304-#4908527-v1 - 영업양수도 양도인 대리(25196.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 41-44 | OK |
| 선행조건 | true | 23-26 | OK |
| 확약 | true | 42-45 | OK |
| 손해배상 | true | 41-44 | OK |
| 해제 | false | - | OK(absent) |
| 경업금지 | false | - | OK(absent) |
| 분쟁해결 | false | - | OK(absent) |

### `28a686358eaa35f3` - 04-1_ATA_BTA_국문/11번가(기프티콘의 발행 및 관리 사업 부문)_SK플래닛_영업양수도계약_Buyer draft(127015.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 23-26 | OK |
| 선행조건 | true | 59-62 | OK |
| 확약 | true | 72-75 | OK |
| 손해배상 | true | 140-143 | OK |
| 해제 | true | 43-46 | OK |
| 경업금지 | true | 191-194 | OK |
| 분쟁해결 | true | 12-15 | OK |

### `0700787da0d8047d` - 04-1_ATA_BTA_국문/11번가(기프티콘의 발행 및 관리 사업 부문)_SK플래닛_영업양수도계약_체결본_20251029(127016.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 23-26 | OK |
| 선행조건 | true | 68-71 | OK |
| 확약 | true | 86-89 | OK |
| 손해배상 | true | 45-48 | OK |
| 해제 | true | 166-169 | OK |
| 경업금지 | true | 204-207 | OK |
| 분쟁해결 | true | 12-15 | OK |

### `c3bc7c850ee55223` - 04-1_ATA_BTA_국문/Aloe_LG화학(에스테틱 사업부 & 중국법인 전체 지분)_VIG파트너스_영업 및 지분양수도계약서_Buyer 1st markup(38460.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 13-16 | OK |
| 선행조건 | true | 144-147 | OK |
| 확약 | true | 52-55 | OK |
| 손해배상 | true | 106-109 | OK |
| 해제 | true | 60-63 | OK |
| 경업금지 | true | 55-58 | OK |
| 분쟁해결 | true | 22-25 | OK |

### `d03712977d39d5d2` - 04-1_ATA_BTA_국문/Aloe_LG화학(에스테틱 사업부 & 중국법인 전체 지분)_VIG파트너스_영업 및 지분양수도계약서_Seller Draft(38461.v1).docx

| clause | present | loc | check |
|---|---:|---|---|
| 진술보장 | true | 84-87 | OK |
| 선행조건 | true | 114-117 | OK |
| 확약 | true | 115-118 | evidence-ok/range-review |
| 손해배상 | true | 83-86 | OK |
| 해제 | true | 56-59 | OK |
| 경업금지 | true | 161-164 | OK |
| 분쟁해결 | true | 21-24 | OK |

## Items to review

| ctype | file_key | clause | issue |
|---|---|---|---|
| SHA | `864f6db985afc5a9` | 분쟁해결 | evidence-ok/range-review |
| SHA | `2ff313fccd7963cb` | 분쟁해결 | evidence-ok/range-review |
| MOU | `d4cabc19206b1697` | 분쟁해결 | evidence-ok/range-review |
| ATA/BTA | `d03712977d39d5d2` | 확약 | evidence-ok/range-review |

## Prompt/dictionary improvement suggestions only

- For non-SPA types, require the extractor to classify generic `termination/haeji/end` language separately from actual contract rescission/termination rights, because ordinary definitions can look like clause hits.
- For SHA and MOU, add guidance that `representations/warranties` may be absent or much narrower than SPA-style R&W, and confidence should be lower when only table-of-contents hits are found.
- For ATA/BTA, keep `business-transfer/asset-transfer` consideration and transfer-closing concepts distinct from share-purchase consideration; do not infer SPA-like clauses unless the paragraph range contains the relevant heading or operative language.
- Do not update `extract_prompt_v1.md` or `term_dict.yaml` without owner approval; these are recommendations only.

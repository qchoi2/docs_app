# 코퍼스 사각지대 실측 — 스캔 PDF·미변환 .doc·판독불가 별지 (2026-07-29, Claude)

리뷰어(Fable) 지적 "스캔 PDF 48건과 미변환 .doc는 추출 품질을 올려도 영원히 검색 밖"을
운영 DB(`cs_index/catalog.sqlite`, **읽기 전용**) 직접 조회 + 원본 파일 바이트 검사로 검증했다.

**결론 요약**
- **"48건"은 정확하다.** 단, 그것은 `status='empty'`만 센 수치이고, **실제 검색 사각지대는 90건**이다
  (empty 48 + unsupported 41 + error 1). 논리 문서 단위로 환산하면 **56건**.
- **이 90건 중 이미 검색 가능한 문서의 중복은 0건.** 전부 순수 손실이다.
- **.doc 변환은 이미 완료됐다.** 잔여는 **5건뿐**이며, 그 5건은 OCR이 아니라 **확장자만 .doc인 RTF**로,
  변환기의 OLE2 가드에 걸린 것이다. 코드 한 줄 수준의 문제다.
- **OCR은 신규 의존성 없이 지금 당장 가능하다.** 이 PC의 Windows에 **한국어 OCR 엔진이 이미 설치돼 있다**
  (`Windows.Media.Ocr`, `ko`). 실제 코퍼스 스캔 PDF로 PoC를 돌려 한국어 계약서 원문을 뽑았다(아래 §4).
- 리뷰어가 "더 클 수 있다"고 본 **판독불가 별지 가설은 실측 결과 성립하지 않는다.** 별지 `missing` 502건은
  "파일이 안 읽혀서"가 아니라 **원본 파일이 코퍼스에 아예 없어서**다(§3). 성격이 다른 결함이다.

---

## 1. 검색 사각지대 실측 — 90건 / 56 논리문서

### 1.1 status별 전수

```sql
SELECT status, COUNT(*) FROM files GROUP BY 1;
SELECT status, ctype, lang, ext, COUNT(*) FROM files WHERE status<>'ok' GROUP BY 1,2,3,4;
SELECT status, error_reason, COUNT(*) FROM files WHERE status<>'ok' GROUP BY 1,2;
```

| status | 건수 | ext | error_reason |
|---|---|---|---|
| ok | 2,016 | — | — |
| **empty** | **48** | .pdf 48 | `pdf_text_empty` 48 |
| **unsupported** | **41** | .jpg 34 / .doc 5 / .xlsx 1 / .eml 1 | `unsupported_ext` 41 |
| **error** | **1** | .docx 1 | `docx_extract_failed` 1 |
| 계 | 2,106 | | 사각지대 **90건 (4.3%)** |

`status='missing'`은 0건이다.

### 1.2 실제 실패 원인 — 원본 바이트 검사

48개 PDF를 전부 열어 `/Encrypt`·`/Subtype/Image`·`/Type/Font`·필터·`/Producer`를 확인했다.

| 판정 | 건수 | 근거 |
|---|---|---|
| **스캔 이미지 PDF** | **47** | 폰트 객체 0개 + 페이지당 이미지 1개 이상. Producer가 전부 복합기 모델명 (`RICOH IM C4500`, `SINDOH D410/D412/D420`, `ApeosPort-IV/V/VI/VII`, `Apeos C6580`, `SCX-8123`) |
| 스캔 PDF(텍스트 잔재 有) | 1 | `64d35f3c5688fb4a` — `Acrobat 5.0 Scan Plug-in`, 이미지 58개 + 폰트 2개. 실질 스캔 |
| **암호화 PDF** | **0** | 48건 전부 `/Encrypt` 없음 |
| 0바이트 / 파서 실패 | 0 | 최소 72KB, 최대 31.8MB |

이미지 필터 분포: `DCTDecode`(JPEG) 우세, `CCITTFaxDecode`(G4 흑백팩스) 다수, `JBIG2Decode` 3건.
**즉 48건 전부 "OCR 가능한 이미지 레이어를 실제로 갖고 있다."** 암호·손상으로 인한 사각지대는 없다.

- `.docx` error 1건(`4394faf90bdd0189`)은 **스캔이 아니다.** 정상 zip이며 `word/document.xml`도 있는데
  python-docx가 `KeyError: customXML/item2.xml`(관계 참조 깨짐)로 실패한다. **OCR 불요, 복구 가능**(§3.3).
- `.jpg` 34건은 전부 `04-1_ATA_BTA_국문/N_영업양수도계약서_체결본_volume2_17638_v1/` 한 폴더의
  `S50C-213092308080_0026~0059.jpg` 연속 스캔이다 — **파일 34개지만 논리 문서는 1건(34쪽)**.

### 1.3 이미 검색 가능한 문서의 중복인가 — 아니다 (0건)

```sql
-- 각 non-ok 파일에 대해 같은 dup_group / content_hash 를 가진 status='ok' 형제 탐색
```
**90건 중 OK 형제를 가진 문서: 0건.**

주의할 함정 하나: non-ok 90건은 `content_hash`가 전부 `e3b0c44298fc1c14`로 **동일하다.**
이 값은 **빈 문자열의 SHA-256**이다 — `content_hash`는 원본 바이트가 아니라 **추출된 텍스트**의 해시이므로,
추출 실패 문서는 전부 "같은 해시"가 된다. `content_hash`로 중복 판정하면 **90건이 서로 중복인 것처럼 보이는
가짜 신호**가 나온다. `dup_group`은 각자 자기 file_key로 세팅돼 있어 정상이다.
→ **사각지대 문서에 대해 `content_hash` 기반 중복 판정을 쓰면 안 된다.** (별도 방어 필요 — §5.4)

### 1.4 논리 문서 단위 환산

| 단위 | 건수 |
|---|---|
| 파일 기준 | 90 |
| 논리 문서 기준 | **56** (= 스캔PDF 48 + jpg묶음 1 + RTF .doc 5 + 깨진 docx 1 + xlsx 1 + eml 1 — 그중 docx·xlsx·eml는 OCR 대상 아님) |
| **OCR이 필요한 논리 문서** | **49** (스캔PDF 48 + jpg 1묶음) |
| OCR 없이 해결되는 것 | 7 (RTF 5 + 깨진 docx 1 + xlsx 1). eml 1건은 별도 판단 |

**OCR 대상 총 페이지 수(pdfminer 실측): 1,931쪽** (국문 1,312 / 영문 619). jpg 34쪽 추가 → **약 1,965쪽.**

---

## 2. 이 사각지대가 실제로 무엇을 막고 있나 — 계약유형 × V4 평가

```sql
SELECT ctype, SUM(status='ok'), SUM(status='empty'), SUM(status IN ('unsupported','error')) FROM files GROUP BY 1;
SELECT ctype, COUNT(DISTINCT d.file_key) FROM v4_document_coverage d JOIN files f USING(file_key) GROUP BY 1;
```

| ctype | ok | V4 평가완료 | V4 도달률 | empty | unsup/err | **사각지대 비율** |
|---|---|---|---|---|---|---|
| SPA | 677 | 671 | 99.1% | 14 | 0 | 2.0% |
| SHA | 378 | **8** | **2.1%** | **10** | 0 | 2.6% |
| SSA | 366 | 103 | 28.1% | 9 | 0 | 2.4% |
| **ATA/BTA** | 213 | 12 | 5.6% | 2 | **40** | **16.5%** |
| CB인수 | 126 | 121 | 96.0% | 5 | 0 | 3.8% |
| MOU | 104 | 0 | 0% | 1 | 1 | 1.9% |
| JVA | 55 | 0 | 0% | 0 | 1 | 1.8% |
| BW인수 | 35 | 34 | 97.1% | 5 | 0 | 12.5% |
| **주식교환** | 10 | 0 | 0% | **2** | 0 | **16.7%** |
| EB인수 | 16 | 15 | 93.8% | 0 | 0 | 0% |
| 공동투자 / 분할합병 / 분할계획서 | 32 | 0 | 0% | 0 | 0 | 0% |

**해석 — 리뷰어의 우선순위 판단은 옳지만 대상은 조금 다르다:**

1. **SHA 10건이 가장 아프다.** SHA는 V4 평가가 2.1%(8/378)뿐이라 지금 확장이 예정된 축인데,
   스캔 10건(417쪽)은 확장을 아무리 해도 **영구히 도달 불가**다. 이 10건에는
   `Jade_씨티알_SHA_체결본_20251031`, `Volt_근우_..._SHA_체결본_20251212`,
   `한국디지털에셋_주주간계약 변경계약서_20251111` 등 **2025년 최신 체결본**이 포함된다.
2. **ATA/BTA가 비율로는 최악(16.5%)이다.** 213 ok 대비 42건이 밖에 있고,
   V4 도달률도 5.6%다. 다만 42건 중 40건은 OCR이 아니라 **포맷 문제(jpg 34 = 1문서, RTF 5, xlsx 1)**이고,
   그중 **RTF 5건은 즉시 회수 가능하다**(§3.2). ATA/BTA는 **OCR보다 포맷 처리의 ROI가 훨씬 크다.**
3. **주식교환 2/12(16.7%)** — 모수가 10건뿐이라 2건 회수가 코퍼스를 20% 늘린다.
4. SPA는 14건이지만 모수 677 대비 2.0%이고 V4 도달률이 이미 99.1%다. **우선순위 최하위.**

> **주의**: 위 "사각지대 비율"은 어디까지나 *색인된 파일 기준*이다. 코퍼스에 애초에 없는 계약은 계산 밖이다.

---

## 3. 별지·부속서 사각지대 — 리뷰어 가설 검증 결과 **불성립**

리뷰어는 "otherwise-searchable 계약의 **읽을 수 없는 별지**가 더 큰 사각지대일 수 있다"고 봤다.
`v4_source_coverage`를 전수 조회해 검증했다.

### 3.1 별지 source 5,160행의 상태

| status | 행 | 문서 |
|---|---|---|
| partial | 3,572 | 479 |
| complete | 1,086 | 349 |
| **missing** | **502** | **148** |

`missing` 502행 내역: schedule 251 / annex 186 / exhibit 52 / disclosure_schedule 13.
family별: RW 229 / COV 91 / DEF 79 / CP 70 / REM 19 / PAY 14.

### 3.2 결정적 실측 — missing의 원인은 "판독 불가"가 아니다

```sql
SELECT COUNT(*) FROM v4_source_coverage WHERE status='missing'
  AND storage_file_key IS NOT NULL AND storage_file_key<>'';        -- 0
SELECT status, COUNT(*) FROM v4_source_coverage
  WHERE storage_file_key IS NULL OR storage_file_key='' GROUP BY 1;  -- missing 502 (전부)
SELECT COUNT(*) FROM v4_source_coverage sc JOIN files f
  ON f.file_key=sc.storage_file_key WHERE f.status<>'ok';            -- 0
```

- **`missing` 502행은 전부 `storage_file_key`가 NULL이다.** 즉 가리킬 파일 자체가 없다.
  reason도 전부 `"입력 inventory 상태를 보존함"` — 본문이 별지를 *언급*했는데 **그 파일이 코퍼스에 없다**는 뜻이다.
- **`storage_file_key`가 non-ok 파일(스캔·미변환)을 가리키는 행은 0건이다.**
  참조된 storage_file_key 640개는 **전원 `status='ok'`**이고, files에 없는 dangling 참조도 0건이다.

**→ 별지 사각지대는 "읽을 수 없어서"가 아니라 "수집되지 않아서" 생긴다.**
OCR로는 1건도 해결되지 않는다. 이건 **자료 수집(§5 권고 5) 문제**이지 추출 문제가 아니다.
`색인 업데이트 설명서.md` §3.2가 이미 "본문에서 언급한 별지가 실제로 포함됐는지 확인한다"고 요구하는데,
502행이 그 요구가 지켜지지 않은 결과다. 집중도도 높다 — 상위 10개 문서가 11~22행씩 차지한다
(`08fa9db87c5acaad` SSA국문 22, `dbd22f19819dede0` SPA영문 21, `1f9352be4b914100` SSA영문 15…).

규모 비교(문서 기준): **문서 전체가 안 읽히는 것 56건 vs 별지가 없는 문서 148건.**
별지 쪽이 문서 수로는 2.6배 크지만 **성격이 다르고 OCR로 못 고친다.**

### 3.3 부수 발견 — `annex_status='not_evaluated'`

`v4_document_coverage`의 annex_status에 family별 20~72건의 `not_evaluated`가 남아 있다(RW 72, COV 42, CP 35).
이건 사각지대가 아니라 **미평가**다. CLAUDE.md 워크플로우 1의 원칙(생략=미평가 ≠ present=false)이
별지 축에도 그대로 적용돼야 하며, 부재 판정 시 `annex_status`를 반드시 함께 봐야 한다.

---

## 4. .doc 변환 감사 — **이미 완료됨. 잔여 5건, 원인은 RTF**

`convert_doc.py` + `convert_doc_worker.ps1`(Word COM, `SaveAs2(..., 16)`)은 **실제로 실행됐고 완주했다.**
증거: `cs_index/converted/manifest.json`(2026-07-12 기록) + `cs_index/converted/*.docx` 497개 실물.

| 항목 | 수치 | 확인 방법 |
|---|---|---|
| manifest 항목 | 562 | manifest.json |
| 변환 성공(`status='ok'`) | **557** | manifest.json |
| 변환 실패 | **5** | 전부 `error_reason='not_ole2_rtf'` |
| 디스크상 `.doc` 실물 | 561 | `contract_docs` 재귀 스캔 |
| manifest에만 있고 디스크엔 없음 | 1 | `sample.doc` (테스트 잔재) |
| 디스크에 있고 manifest에 없음 | **0** | ← **누락 없이 전수 처리됨** |
| 변환 산출물(distinct target) | 497 | target명 = source SHA-256 |
| 산출물 실물 존재 | **497 / 497** | 전부 존재 |
| files 테이블 `.doc` 행 | 502 | ok 497 + unsupported 5 |
| **본문 텍스트 사용 가능** | **497** | char_count 최소 696, 평균 44,593, **500자 미만 0건** |
| `.doc` 출신 V4 평가 완료 | 163 | `v4_document_coverage` 조인 |

**"변환 ok 557 vs 색인 497"의 60건 차이 — 손실 아님(검증 완료).**
target 파일명이 원본 SHA-256이라 **바이트 동일한 .doc는 같은 산출물로 수렴**한다.
색인에 없는 60건을 전수 확인한 결과 **60/60이 이미 색인된 .doc와 바이트 동일**하고, **고아는 0건**이다.
(예: `Carlyle2_3_epivalley/Final_Execution_Copies/crl002.sha.041203.doc` 등 폴더 중복본)

### 4.1 잔여 5건의 정확한 원인

| file_key | 크기 | 매직 | 파일명 |
|---|---|---|---|
| `8904694795c0e4b2` | 238KB | `{\rtf1\ansi\kis94\de` | 영업양수도계약-위니아(만도기계)-국문번역(워드파일)(17614.v1).doc |
| `511bca280cb08d1a` | 200KB | `{\rtf1\ansi\kis94\de` | 영업양수도계약.한화.국문번역(17602.v1).doc |
| `5bfcb2f202b6c1ae` | 370KB | `{\rtf1\ansi\kis94\de` | 자산양수도계약-르노삼성(17605.v1).doc |
| `87f136a5daced5d4` | 1.44MB | `{\rtf1\ansi\ansicpg9` | 자산양수도계약-르노삼성-국문번역(워드파일)(17620.v1).doc |
| `b37dfb10baab5c83` | 304KB | `{\rtf1\ansi\ansicpg9` | 자산양수도계약서-WHJ 작성 초안 샘플(17624.v1).doc |

전부 **확장자만 `.doc`인 RTF**다. `convert_doc.py:73-84 detect_doc_kind()`가 OLE2 매직만 통과시키고
`kind != "ole2"`면 Word에 보내보지도 않고 `unsupported`로 떨군다(`convert_doc.py:116-124`).
**Word COM은 RTF를 정상적으로 연다.** `.docx`로 SaveAs2 하는 데 아무 장애가 없다.
`{\rtf1\ansi\kis94` 는 한글 워드프로세서 계열 산출물이라 인코딩 확인은 필요하지만,
**5건 모두 ATA/BTA 국문**이고 ATA/BTA는 V4 도달률이 5.6%뿐이라 **회수 가치가 크다.**

> **이건 이 보고서에서 가장 싼 recall 회복이다** — OCR 인프라도, 신규 의존성도, 승인도 필요 없다.
> `detect_doc_kind`의 허용 목록에 `rtf`를 추가하고(zip은 `.docx` 오분류이므로 별도 경로)
> 재실행하면 끝이다. 5건 = ATA/BTA ok 213건의 2.3%.

### 4.2 그 외 회수 가능 항목 (OCR 불요)

- `4394faf90bdd0189` (MOU 국문 .docx, `docx_extract_failed`): zip 정상, `word/document.xml` 존재.
  python-docx가 `customXML/item2.xml` 관계 참조 깨짐으로 실패. **`word/document.xml` 직접 파싱** 또는
  **Word COM 라운드트립**(이미 있는 인프라)으로 복구 가능. 1건.
- `2be4db09b88e1f78` (.xlsx, `별첨 2.1(5) 양수도 대상지적재산권 (국내외상표)`, 6.8MB):
  **별첨 파일**이다. §3의 별지 문제와 직결되며, xlsx는 zip+XML이라 **순수 표준 라이브러리로 읽을 수 있다.**
  다만 표 형태 별지를 본문 텍스트와 같은 축으로 색인할지는 설계 판단이 필요하다.
- `46633979c844ba83` (.eml, JVA 영문 683KB): `email` 표준 라이브러리로 본문·첨부 추출 가능.
  다만 계약서 본문인지 메일 스레드인지 확인 필요.

---

## 5. 로컬 OCR 실현 가능성 — **가능. 신규 의존성 0.**

### 5.1 이 PC에 실제로 있는 것 / 없는 것 (실측)

| 항목 | 상태 |
|---|---|
| `tesseract` (PATH) | **없음** |
| `Tesseract-OCR` (Program Files / (x86) / LocalAppData) | **없음** |
| `kor.traineddata` | 없음 (tesseract 자체가 없음) |
| `requirements.txt` | `python-docx`, `pdfminer.six`, `PyYAML` — **OCR/이미지 바인딩 0** |
| Python | 3.14.6 |
| `PIL` / `numpy` / `cv2` / `pypdfium2` / `fitz` / `pytesseract` / `pdf2image` / `easyocr` / `paddleocr` | **전부 미설치** |
| `win32com` (pywin32) | **설치됨** |
| Microsoft Word COM | **사용 가능 (버전 16.0)** |
| **`Windows.Media.Ocr.OcrEngine`** | **사용 가능** |
| **OCR 한국어 인식기** | **설치돼 있음 — `AvailableRecognizerLanguages` = `en-US`, `ko`** |
| `Windows.Data.Pdf.PdfDocument` (PDF 래스터라이저) | **사용 가능 (OS 내장)** |

즉 **Windows가 PDF 렌더러와 한국어 OCR 엔진을 둘 다 이미 갖고 있다.** tesseract를 깔 이유가 없다.
파이프라인 전체가 OS 내장 API로 닫힌다:

```
PDF ─ Windows.Data.Pdf.PdfDocument.RenderToStreamAsync ─▶ 비트맵
    ─ Windows.Graphics.Imaging.BitmapDecoder ─▶ SoftwareBitmap
    ─ Windows.Media.Ocr.OcrEngine(ko).RecognizeAsync ─▶ 텍스트
```
Python에서는 WinRT를 직접 못 부르므로, **이미 이 저장소에 있는 패턴**
(`convert_doc.py` → `convert_doc_worker.ps1` PowerShell 워커 + JSON job/result)을 그대로 재사용하면 된다.
설계 부담이 거의 없다.

### 5.2 실제 코퍼스로 PoC 실행 (추정 아님 — 실행 결과)

**대상 1** — `f7f872b83577f7a2` / MOU 국문 / DCTDecode 6쪽
`contract_docs/09-1_MOU_양해각서_국문/[3. 체결본] 양해각서(MOU)_양사 날인본_KM(35534.v1).pdf`
렌더 배율 2배(3174×4486px), 엔진 `ko`. **1쪽 원문 그대로:**

> 2. 체결본 양 각 서 본 양해각서(“본 양해각서")는 다음 당사자들 사이에 2020년 9월 22일(“본 양해각서
> 체결일”)에 체결되었다. 1. 서울특별시 영등포구 의사당대로 3(여의도동)에 주소를 두고 있는 현대개피탈 주
> 식회사(“매도인") 경기도 성남시 분당구 판교역로 152, 13층(백현동, 알파돔타워)에 주소를 두고 있는
> 주식회사 카카오모빌리티(“매수인") (매도인 및 매수인을 개별적으로 “당사자”, 총칭하여 “당사자들"이라 함)
> 2. 3. 매도인은 할부금융업, 시설대여법 및 신기술사업금융업을 주된 사업으로 영위하는 회사로서 그 일환으로
> ,딜카, 브랜드의 온라인 자동차대여 예약 및 결제 플랫폼 사 업(이하 “대상사업")을 영위하고 있다. …
> 당사자들은 본건 거래를 위한 구속력 있는 최종계약(“최종계약”)을 체결하기에 앞 서, 대상사업의 실사,
> 최종계약의 체결 및 그에 따른 제반 절차를 명확히 하기 위 하여 다음과 같이 합의하였다.

**대상 2** — `a0eb1e6dc138e918` / SPA 국문 / CCITTFax 흑백 13쪽
`contract_docs/01-1_SPA_국문/Crema_학산(13)_SPA_체결본_20240327.pdf` **1~2쪽 발췌:**

> …본 계약 체결일 현재 매도인들은 대상회사 발행의 기명식 보통주식(1주당 액 면가 금 10,000원) 합계
> 14,880주(대상회사 발행주식총수의 37.2%)를, 매수인 은 대상회사 발행의 기명식 보통주식
> 14,840주(대상회사 발행주식총수의 37.1%)를 각 보유하고 있다. … 대상주식에 대한 매매대금은 총 금
> 이백삼십사억(23,400,000,000)원(주당 금 사백오십 만(4,500,000)원)으로 한다. …
> **제3조 (본건 거래의 종결)** … **제4조 (거래종결의 선행조건)** … **제5조 (진술 및 보장)** …
> **제6조 (손해배상)** (1) 당사자 일방(이하 “배상의무자”)은 배상의무자의 진술 및 보장이 사실과 다르거
> 나 정확하지 않은 경우 …

### 5.3 품질 평가 (실측 기반)

**잘 되는 것:**
- 한국어 본문 글자 정확도 체감 **95%+**. 흑백 CCITTFax 스캔이 컬러 JPEG 스캔보다 **오히려 더 깨끗**했다.
- **조항 제목이 정확하다** — `제3조 (본건 거래의 종결)`, `제5조 (진술 및 보장)`, `제6조 (손해배상)`.
  → `clause_map`·term_dict 매칭·family 분류에 바로 쓸 수 있는 수준.
- **숫자가 정확하다** — `14,880주`, `37.2%`, `23,400,000,000원`, `4,500,000원`, `2020년 9월 22일`.
  → PAY(대금)·REM(손해배상 상한) 같은 수치 추출에 유효.
- 회사명·주소 등 고유명사도 대체로 정확.

**깨지는 것 (반드시 알고 써야 함):**
1. **번호 목록의 읽기 순서가 무너진다.** `2. 2. 3.` / `(1) (2) (3)` 처럼 **항 번호가 본문에서 떨어져
   앞으로 몰린다.** → **항 번호와 본문의 대응이 신뢰 불가.** "제6조 제(2)항" 같은 **세부 항 단위 인용은 위험**하다.
   조 단위 제목은 살아남지만 항 단위는 아니다.
2. **인용부호·따옴표 손상** — `'딜카'` → `,딜카,`, `("실사")` → `(,로 사")`. verbatim 인용 시 원문 그대로가 아니다.
3. **한글 오인식 산발** — `현대캐피탈`→`현대개피탈`, `부채`→`부재`, `임직원`→`임찍원`,
   `별첨 A`→`별점 A`, `시설대여업`→`시설대여법`, `협상기간`→`협상기고`.
   → **`부채`→`부재` 류는 특히 위험하다. 의미가 반대로 뒤집힌다.**
4. **중복 삽입** — `매도인들로부터으로부터`.
5. 수기 기입란·공란은 `[3 ]월 [호?]일`처럼 노이즈가 된다.

**종합 판정:**
> **검색(recall) 목적으로는 충분히 좋다. verbatim 인용과 부재 판정의 근거로는 부족하다.**
> CLAUDE.md 답변 원칙 1(verbatim 병기)·4(부재 증명 신중히)와 정면으로 부딪히므로,
> **§6의 출처 표기 설계가 OCR 도입의 전제 조건이다.** 표기 없이 넣으면 안 된다.

### 5.4 런타임 비용 (실측 기반)

| 항목 | 실측/환산 |
|---|---|
| 처리 속도 | **1.66 ~ 1.79 초/쪽** (렌더 2배율 + ko OCR, 단일 스레드) |
| 대상 페이지 | **1,931쪽** (PDF 48건, pdfminer 실측) + jpg 34쪽 = **약 1,965쪽** |
| **예상 총 소요** | **약 55 ~ 60분, 단일 스레드 1회** |
| 병렬화 | 문서 단위 병렬 가능. 4워커면 15분 내외 |
| 비용 | **0원. 네트워크 호출 0. 유료 API 0** (답변 원칙 9 저촉 없음) |
| 재실행 | 원본 SHA-256 기준 manifest로 증분 처리(= convert_doc과 동일 패턴) |

**1시간이면 코퍼스 사각지대의 대부분이 사라진다.** 비용 대비 효과가 이 보고서의 어떤 항목보다 크다.

### 5.5 소유자 승인이 필요한 것 / 필요 없는 것

**승인 불필요 (신규 의존성 0, 비용 0):**
- Windows 내장 OCR 사용 자체. `requirements.txt` 변경 없음. 설치 없음. 네트워크 없음.
- 로컬 파일만 읽고 로컬에만 쓴다. 외부 전송 없음(계약서 기밀성 측면에서도 클라우드 OCR 대비 결정적 장점).

**소유자 승인이 필요한 것:**
1. **[필수] 스키마 변경 승인** — `files.extraction_method` / `ocr_confidence` 등 신규 컬럼(§6).
   DB 단일 writer 원칙이 있으므로 마이그레이션 시점 조율 필요.
2. **[필수] 정책 결정 — OCR 텍스트를 부재 판정에 쓸 것인가.**
   본 보고서 권고는 **"쓰지 않는다"**(§6.3). 이건 정책이라 소유자가 정해야 한다.
3. **[필수] 정책 결정 — OCR 텍스트를 V4 추출(유료 API 경로) 입력으로 넣을 것인가.**
   넣으면 API 비용이 발생하고, §5.3의 항 번호 붕괴가 item 좌표를 오염시킬 수 있다.
   **권고: 1차는 검색(FTS) 전용으로만 투입하고, V4 추출 투입은 별도 파일럿 후 결정.**
4. **[선택] PowerShell 워커 신설 승인** — `ocr_worker.ps1`. 기존 `convert_doc_worker.ps1`과 동형이라 위험 낮음.
5. **[선택] 품질 향상용 선택적 의존성** — 렌더 배율 상향/전처리로 §5.3의 오인식을 줄이려면
   `pypdfium2` 같은 라이브러리가 도움될 수 있으나 **필수는 아니다.** 기본 방침은 **무설치 유지.**

**만약 소유자가 "Windows 내장 OCR도 쓰지 말라"고 한다면** — 그때 비로소 tesseract가 대안이며,
그 경우 필요한 것은: Tesseract-OCR Windows 설치(UB-Mannheim 빌드), `kor.traineddata` 언어팩,
그리고 PDF→이미지 래스터라이저(`pypdfium2` 또는 poppler) + `pytesseract` + `Pillow`.
즉 **신규 의존성 3~4개 + 외부 바이너리 설치**가 필요하다. 내장 OCR이 쓸 수 있는 한 이 경로를 택할 이유가 없다.

---

## 6. 출처(provenance) 설계 — OCR 텍스트가 깨끗한 추출로 위장하지 않게

이 프로젝트의 일관된 원칙은 **불확실성을 숨기지 않고 표면화하는 것**이다
(`status`, `confidence`, `is_draft=null`, coverage `reasons`, "미평가 ≠ present=false").
OCR 텍스트는 §5.3에서 확인했듯 **본문 검색에는 쓸 만하고 verbatim·부재 판정에는 부적합**하므로,
**그 차이가 모든 소비 지점에서 보이도록** 표시해야 한다.

### 6.1 스키마 (제안 — 본 보고서는 설계까지, 구현 없음)

**`files` 테이블 신규 컬럼:**

| 컬럼 | 값 | 의미 |
|---|---|---|
| `extraction_method` | `native` \| `converted_docx` \| `ocr` \| `ocr_mixed` | 텍스트가 어떻게 나왔나. 기존 행은 `native`/`converted_docx`로 백필 |
| `extraction_engine` | 예: `Windows.Media.Ocr ko / Windows.Data.Pdf` | 엔진·버전 |
| `ocr_lang` | `ko` \| `en-US` \| `ko+en-US` | 사용 인식기 |
| `ocr_mean_confidence` | REAL 0~1 | 페이지 평균 신뢰도 (엔진 line/word 신뢰도 집계) |
| `ocr_page_count` / `ocr_low_conf_pages` | INTEGER | 전체 쪽수 / 임계 미만 쪽수 |
| `ocr_at` | TEXT | 실행 시각 |

**`status` 값은 건드리지 않는다.** OCR 성공 문서는 `status='ok'`가 되지만
`extraction_method='ocr'`로 구별된다. `status`에 `ocr`을 섞으면 기존 모든 질의의 의미가 바뀐다.
다만 **`status='ok'`를 "깨끗한 텍스트"의 동의어로 쓰던 코드가 있는지 점검이 필요**하다.

**txt 캐시:** 헤더 첫 줄에 기계 판독 가능한 마커를 넣는다 —
`[!OCR] engine=Windows.Media.Ocr/ko conf=0.87 pages=13 low_conf_pages=2`
`open_text.py`·`read_contract.py`가 이 줄을 읽어 **본문을 보여줄 때마다 경고를 함께 출력**한다.
¶ 마커는 유지하되, **OCR 문서의 ¶ 좌표는 항 번호 붕괴(§5.3-1) 때문에 조 단위까지만 신뢰**한다고 명시한다.

**`ocr_page` 보조 테이블 (권장):** `(file_key, page_no, confidence, char_count, para_start, para_end)`.
쪽 단위 신뢰도를 남겨야 "이 인용이 나온 쪽이 저신뢰였나"를 사후에 답할 수 있다.
저신뢰 쪽만 골라 재렌더(배율 상향)로 재처리하는 증분 개선도 여기서 나온다.

### 6.2 검색 경로 (`search_contracts.py` / `v4_search.py` / webapp)

1. JSON 결과의 각 항목에 `extraction_method`와 `ocr_mean_confidence`를 **항상 포함**한다.
2. `why` / `score_breakdown`에 `ocr_derived: true` 플래그를 넣어, 에이전트가 스니펫을 인용할 때
   OCR 유래임을 인지하게 한다(CLAUDE.md 도구 지침이 `why`를 먼저 읽으라고 이미 규정).
3. UI/텍스트 출력에 **`[OCR]` 배지**를 붙인다. `is_draft` 표시와 동일한 취급.
4. **랭킹은 낮추지 않는다.** OCR 문서를 강등하면 recall 천장을 올린 의미가 사라진다.
   대신 **동점일 때 native를 앞세우는 tie-break** 정도만 둔다.
5. `--exclude-ocr` / `--only-ocr` 필터를 추가해, 정밀도가 중요한 질의에서 소유자가 배제할 수 있게 한다.

### 6.3 부재 판정 (`search_clause_absence`) — **가장 중요한 방어선**

> **OCR 유래 문서는 `confirmed_absent`를 절대 반환하지 않는다. 무조건 `needs_review`로 강등한다.
> 사유 코드: `ocr_derived_text`.**

근거: §5.3에서 확인했듯 OCR은 글자를 **틀리게** 읽는다(`부채`→`부재`). 키워드가 안 잡히는 것이
"원문에 없다"인지 "OCR이 틀렸다"인지 구분할 방법이 없다. 이는 `V4_RW_COVERAGE_DEFECT_20260727.md`가
지적한 것과 **정확히 같은 구조의 false absence 함정**이다 — 그때는 추출 누락이 부재로 둔갑했고,
여기서는 OCR 오인식이 부재로 둔갑한다. **같은 실수를 반복하지 않는다.**

CLAUDE.md 답변 원칙 4("키워드 미검출만으로 부재를 단정하지 마라")의 직접적 연장이다.

### 6.4 V4 추출 / coverage

1. `v4_document_coverage`·`v4_source_coverage`의 `extractor_version`에 OCR 사실을 남기고,
   **`body_status`는 최대 `partial`까지만 부여한다. OCR 문서에 `complete`를 주지 않는다.**
   (`V4_RW_COVERAGE_DEFECT` 권고 3의 "일괄 complete 도장 폐지"와 같은 취지.)
2. `reason`에 `ocr_source`를 기록해, 나중에 "complete인데 왜 얇지?"를 추적 가능하게 한다.
3. `v4_clause_item`에 `source_reliability` (`native` \| `ocr`) 를 두어, Gate B 정밀도 측정 시
   **OCR 유래 item을 분리 집계**한다. 섞으면 Gate 지표가 오염돼 원인 규명이 불가능해진다.
4. **verbatim 필드에 OCR 텍스트를 그대로 넣지 않는다.** 넣어야 한다면 `verbatim_is_ocr=true`를 병기하고,
   답변 시 "OCR 추출 원문이므로 오탈자 가능"을 반드시 표시한다.

### 6.5 에이전트 답변 규칙 (CLAUDE.md 추가 제안)

> **11. OCR 유래 문서 고지.** `extraction_method='ocr'` 문서를 인용할 때는 `[file_key, OCR]`로 표시하고,
> verbatim 인용에는 "OCR 추출본 — 오탈자 가능" 주석을 붙인다. 항·호 단위 번호는 인용하지 않고
> 조 단위까지만 인용한다. **OCR 문서만을 근거로 조항 부재를 단정하지 않는다.**

### 6.6 §1.3 함정에 대한 방어

`content_hash`가 "추출 텍스트의 해시"이므로, **OCR로 텍스트가 생기는 순간 90건의 동일 해시
`e3b0c44298fc1c14`가 각기 다른 값으로 갈라진다.** 이때 `dup_group` 재계산이 필요하다.
더 중요한 건, **OCR 텍스트는 같은 원본이라도 실행마다 미세하게 달라질 수 있어
`content_hash` 기반 중복 판정이 원리적으로 불안정**하다는 점이다.
→ OCR 문서의 중복 판정은 `content_hash`가 아니라 **원본 파일 바이트의 SHA-256**(convert_doc이 이미 쓰는 방식)을
별도 컬럼 `source_sha256`으로 두고 그걸로 해야 한다.

---

## 7. 권고 (우선순위 순)

**즉시 — OCR 인프라 없이, 승인 없이 가능:**
1. **RTF 5건 회수.** `convert_doc.py detect_doc_kind` 허용 목록에 `rtf` 추가 → Word COM은 이미 RTF를 연다.
   **ATA/BTA 국문 5건**, V4 도달률 5.6%인 유형이라 회수 가치 큼. 가장 싼 recall 회복.
2. **깨진 `.docx` 1건 회수** (`4394faf90bdd0189`). `word/document.xml` 직접 파싱 또는 Word COM 라운드트립.
3. **`content_hash` 함정 방어.** 추출 실패 문서 90건이 동일 해시를 공유하는 사실을 중복 판정 로직이
   알고 있는지 점검. 모르면 지금도 오판이 나고 있을 수 있다.

**단기 — 스키마 승인 후:**
4. **OCR 파이프라인 구축.** Windows 내장 `Windows.Data.Pdf` + `Windows.Media.Ocr(ko)`,
   `convert_doc.py`/`convert_doc_worker.ps1`과 동형의 `ocr_docs.py` + `ocr_worker.ps1` + 증분 manifest.
   **신규 의존성 0, 비용 0, 예상 1시간.** 단, **§6 출처 표기를 함께 넣지 않으면 착수하지 말 것.**
5. **투입 순서는 SHA → 주식교환 → ATA/BTA → SSA/CB/BW → SPA.**
   SHA 10건(417쪽)이 최우선 — V4 도달률 2.1%로 확장 예정 축인데 영구 도달 불가이고,
   2025년 최신 체결본이 포함돼 있다. SPA는 도달률 99.1%라 최후순위.

**별도 축 — OCR로 해결 안 됨:**
6. **별지 502건은 수집 문제다.** 소유자에게 148개 문서의 누락 별지 목록을 제시하고 원본 확보를 요청한다.
   `색인 업데이트 설명서.md` §3.2가 이미 요구하는 절차가 지켜지지 않은 결과다.
   OCR·재추출에 아무리 투자해도 이 502건은 회수되지 않는다.
7. `annex_status='not_evaluated'`(RW 72 등)를 `no_annex`(평가 후 별지 없음)와 **혼동하지 않도록**
   부재 판정 경로에서 분리한다. §3.3.

---

## 8. 검증한 것 / 검증하지 못한 것

**검증함 (실측):**
- `files` 전수 status·ctype·lang·ext·error_reason 분포 (읽기 전용 조회)
- 48개 PDF **전부** 원본 바이트 열어 암호화·이미지 레이어·폰트·필터·Producer 확인
- 90건 non-ok의 `dup_group`/`content_hash` 형제 탐색 → OK 형제 0건, 그리고 동일 해시가 **빈 문자열 해시**임을 확인
- `v4_source_coverage` 5,160행 전수 — `missing` 502행이 **전부 `storage_file_key IS NULL`**,
  non-ok 파일을 가리키는 행 **0건**, dangling 참조 **0건**
- `converted/manifest.json` 562항목 × 디스크 `.doc` 561개 × `files` 502행 3자 대조,
  미색인 60건이 **60/60 바이트 중복**임을 SHA-256으로 확인
- 잔여 5건의 파일 매직을 직접 읽어 RTF 확인
- `Windows.Media.Ocr.OcrEngine.AvailableRecognizerLanguages` = `en-US`, `ko` (실행 확인)
- **실제 코퍼스 스캔 PDF 2건에 OCR 실행** — 컬러 JPEG 스캔, 흑백 CCITTFax 스캔 각 1건, 각 3쪽. 속도 실측.
- pdfminer로 48건 정확한 페이지 수 = 1,931쪽

**검증하지 못함 (한계 — 정직하게 밝힘):**
- **OCR 정확도를 정량 측정하지 않았다.** 6쪽(2문서×3쪽)을 육안 평가했을 뿐 CER/WER를 재지 않았다.
  "95%+"는 체감치다. **정량화하려면 스캔본과 동일 계약의 native 텍스트본 쌍이 필요한데, 코퍼스에 그런 쌍이 없다**
  (§1.3에서 확인한 대로 스캔본은 전부 OK 형제가 없다). 소유자가 스캔본 1~2건을 수동 전사해주면 측정 가능하다.
- **영문 스캔 19건(619쪽)에는 OCR을 돌려보지 않았다.** `en-US` 인식기가 있으므로 되겠지만 품질 미확인.
  영문 CCITTFax/JBIG2 문서가 다수라 별도 확인 권장.
- **48건 전체 OCR을 완주하지 않았다.** 6쪽 표본 속도를 선형 외삽했다. 대용량 문서
  (`f49a9e2cc2286dbd` 107쪽/이미지 4,065개, `9029aea1e39996c5` 이미지 597개)에서
  렌더 메모리·시간이 비선형으로 늘 수 있다.
- **RTF 5건의 실제 변환은 시도하지 않았다.** 매직 확인까지만 했다(변환은 DB/파일 쓰기를 수반하므로
  본 세션의 읽기 전용 제약 밖). Word COM이 RTF를 여는 것은 일반적 사실이나 이 5개 파일로 확인하진 않았다.
- **`.eml` 1건, `.xlsx` 1건의 내용은 열어보지 않았다.** 계약 본문인지 부속자료인지 미확인.
- `annex_status='not_evaluated'`가 왜 남았는지(추출 미도달인지 명시적 보류인지)는 추적하지 않았다.

---

## 9. 재현 방법

```bash
# 저장소 루트에서. 반드시 읽기 전용 URI.
python -c "import sqlite3; con=sqlite3.connect('file:cs_index/catalog.sqlite?mode=ro',uri=True); ..."

# ① 사각지대 전수
SELECT status, ctype, lang, ext, COUNT(*) FROM files WHERE status<>'ok' GROUP BY 1,2,3,4;
# ② 중복 여부 (content_hash 함정 주의: 실패 문서는 전부 e3b0c44298fc1c14 = 빈 문자열 해시)
SELECT f2.file_key FROM files f1 JOIN files f2 ON f1.dup_group=f2.dup_group
  WHERE f1.status<>'ok' AND f2.status='ok';
# ③ 별지 missing의 정체
SELECT COUNT(*) FROM v4_source_coverage WHERE status='missing' AND storage_file_key IS NOT NULL;  -- 0
# ④ V4 도달률 대비 사각지대
SELECT ctype, SUM(status='ok'), SUM(status<>'ok') FROM files GROUP BY 1;
```

- PDF 실패 원인 판정: 원본 바이트에서 `/Encrypt`, `/Subtype/Image`, `/Type/Font`, `/DCTDecode`,
  `/CCITTFaxDecode`, `/JBIG2Decode`, `/Producer` 카운트.
- `.doc` 감사: `cs_index/converted/manifest.json` × `contract_docs/**/*.doc` × `files WHERE ext='.doc'` 3자 대조.
  미색인분은 `source_sha256` 일치로 중복 여부 확인.
- OCR PoC: PowerShell 5.1 + `System.Runtime.WindowsRuntime`.
  `IAsyncOperation<T>`는 `AsTask` 제네릭, `IAsyncAction`(=`RenderToStreamAsync`)은 **비제네릭 `AsTask`** 로
  await해야 한다(제네릭으로 부르면 `System.__ComObject cannot be converted` 오류).
  PowerShell에서 `[string]$Pdf` 파라미터 변수에 객체를 재대입하면 **문자열로 강제 변환**되므로 변수명을 분리할 것.

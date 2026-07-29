#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""거래 메타데이터(연도·규모구간·준거법·관할/중재·업종) 로컬 파생 — 읽기 전용 dry-run.

배경: 2026-07-29 리뷰 제안("거래 메타데이터 확장")의 타당성을 실측하기 위한 도구다.
DB에 쓰지 않는다. `--report`로 "무엇을 채울 수 있는가"를 근거와 함께 JSON으로 내보내고,
소유자 검토 후 조율자가 마이그레이션을 수행한다.

## 근거·신뢰도 규율 (classify_version.py와 동일한 형태)
모든 파생값은 ``{"value", "confidence", "basis"}`` 3종 세트다.
- ``value``    — 파생된 값. **모르면 None**이다. 절대 추측으로 채우지 않는다.
- ``confidence`` — high/med/low 또는 None(미평가). ``classify_version.CONFIDENCE_LEVELS``와
  같은 어휘를 쓴다.
- ``basis``    — 어떤 규칙이 발화했고(rule), 어떤 토큰/문구가 걸렸고(matched),
  원문 어디인지(para, verbatim), 무엇과 상충하는지(conflicts).

## 이 도구가 지키는 판정 규율 (실측으로 필요성이 확인된 것들)
1. **목차(TOC) 앵커 배제** — "10.10 준거법 및 분쟁해결 19"처럼 페이지 번호가 붙은
   목차 줄이 본문 조항보다 먼저 나온다. 첫 매치를 그대로 쓰면 조항을 못 읽는다.
2. **공란·괄호 선택지 → unknown** — "the internal laws of ___", "[Hong Kong; the
   United Kingdom]"는 미확정이다. 값으로 승격하지 않는다.
3. **준거법 ≠ 중재지 ≠ 관할법원** — 세 값을 별도 필드로 낸다. 절대 합치지 않는다.
   (실측: 준거법이 Korea인데 중재지가 Singapore인 문서가 다수)
4. **중재는 '언급'과 '합의'를 구분** — 정의조항의 "중재절차"는 중재합의가 아니다.
5. **체결일 ≠ 작성일 ≠ 파일 수정일** — 연도는 출처를 basis에 명시하고, 출처마다
   신뢰도가 다르다. 파일 mtime은 전량 재색인 시각이라 신호가 아니다(사용 금지).
6. **대금은 사람이 검수한 v3 값만 사용** — 별도 계약 참조금액·비구속 MOU 제안·
   공란 초안을 자동으로 구간화하면 적극적으로 틀린다.
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from classify_version import CONFIDENCE_LEVELS, normalize_confidence  # 어휘 공유

DERIVER_VERSION = "deal_meta_v1_20260729"

# 축 이름 — 저장 설계(§ 리포트)와 CLI 필터 이름의 단일 출처.
AXES = ("deal_year", "size_band", "governing_law", "forum", "industry")


# --------------------------------------------------------------------------- #
# 공통 — 파생 결과 3종 세트
# --------------------------------------------------------------------------- #
def detail(value, confidence, **basis) -> dict:
    """{value, confidence, basis}. 빈 basis 항목은 기록하지 않는다(추측 여지 제거)."""
    clean = {k: v for k, v in basis.items() if v not in (None, [], {}, "")}
    clean.setdefault("deriver", DERIVER_VERSION)
    level = normalize_confidence(confidence)
    return {"value": value, "confidence": level, "basis": clean}


def unknown(rule: str, **basis) -> dict:
    """'모른다'를 1급 값으로 표현한다 — 필터에서 조용히 사라지면 안 되는 상태."""
    return detail(None, None, rule=rule, **basis)


def is_unknown(result) -> bool:
    return not isinstance(result, dict) or result.get("value") is None


# --------------------------------------------------------------------------- #
# 원문 로딩 — [¶n]\t본문 캐시
# --------------------------------------------------------------------------- #
PARA_RE = re.compile(r"^\[¶(\d+)\]\t(.*)$")
HEADFOOT_RE = re.compile(r"^\[(?:머리글|바닥글)\]")


def load_paras(txt_dir: Path, file_key: str):
    """[(para_no, text), ...]. 캐시가 없으면 None(= 본문 검색 불가 문서)."""
    path = Path(txt_dir) / f"{file_key}.txt"
    if not path.is_file():
        return None
    out = []
    with io.open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            m = PARA_RE.match(line.rstrip("\n"))
            if m:
                out.append((int(m.group(1)), m.group(2)))
    return out or None


def split_body(paras):
    """머리글/바닥글 문단과 본문 문단을 나눈다. 머리글의 날짜는 '작성일'이지 체결일이 아니다."""
    body, headfoot = [], []
    for no, text in paras:
        (headfoot if HEADFOOT_RE.match(text) else body).append((no, text))
    return body, headfoot


# --------------------------------------------------------------------------- #
# 목차 판정 — 앵커 선택의 1차 관문
# --------------------------------------------------------------------------- #
TOC_TRAILING_PAGE = re.compile(r"\s\d{1,3}\s*$")
TOC_MARKERS = ("목 차", "목차", "table of contents")


def looks_like_toc(text: str) -> bool:
    """목차 줄인가. 표제 뒤에 페이지 번호가 붙거나 별지/별첨 나열이 이어진다."""
    if TOC_TRAILING_PAGE.search(text):
        return True
    if text.count("별지") + text.count("별첨") >= 2:
        return True
    return False


# --------------------------------------------------------------------------- #
# 공란·미확정 표시 — 값으로 승격하면 안 되는 상태
# --------------------------------------------------------------------------- #
PLACEHOLDER = re.compile(
    r"\[\s*(?:\*|●|◯|_+|[Xx]{2,}|date|month|day|insert|tbd|미정|공란)\s*\]"
    r"|_{3,}"
    r"|laws\s+of\s+(?:the\s+)?(?=without|,|\.)"          # "laws of  without ..." = 공란
    r"|법\s*률?\s*을?\s*준거법으로\s*한다\s*$"
)
BRACKET_OPTIONS = re.compile(r"\[[^\[\]]{2,60}(?:;|/|또는|or)\s*[^\[\]]{2,60}\]")


def placeholder_hit(text: str):
    m = PLACEHOLDER.search(text)
    return m.group(0).strip() if m else None


def bracket_options_hit(text: str):
    m = BRACKET_OPTIONS.search(text)
    return m.group(0).strip() if m else None


# --------------------------------------------------------------------------- #
# 축 1 — 거래 연도
# --------------------------------------------------------------------------- #
# 출처마다 사실이 다르다. 이 표가 곧 신뢰도 근거다.
#   체결본 서명란/전문의 완전한 날짜  → 체결일(high)
#   초안/mark-up 전문의 완전한 날짜   → 작성일 또는 예정 체결일(med)
#   파일명 YYYYMMDD                  → 그 버전의 일자(med)
#   파일명 YYMMDD                    → 그 버전의 일자(low, 6자리는 버전번호와 혼동)
#   머리글/바닥글 날짜               → 수정안 배포일(low)
#   전문 "2024. [*]. [*]." (연도만)  → 작성 연도(low, 미체결)
#   파일 mtime                       → 사용 금지(전량 재색인 시각)
YEAR_MIN, YEAR_MAX = 1990, 2030

DATE_KO = re.compile(r"(19[89]\d|20[0-3]\d)\s*[.년]\s*(\d{1,2})\s*[.월]\s*(\d{1,2})\s*[.일]?")
DATE_KO_YEAR_ONLY = re.compile(
    r"(19[89]\d|20[0-3]\d)\s*[.년]\s*(?:\[[^\]]{0,6}\]|_{1,6}|●|\s)\s*[.월]"
)
_MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December")
DATE_EN = re.compile(rf"(?:{_MONTHS})\s+\d{{1,2}},?\s+(19[89]\d|20[0-3]\d)", re.I)
DATE_EN_ORD = re.compile(r"day\s+of\s+\w+,?\s*(19[89]\d|20[0-3]\d)", re.I)

FILENAME_YMD = re.compile(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)")
FILENAME_YYMMDD = re.compile(r"(?<!\d)(\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)")

SIGNATURE_MARKERS = (
    "이를 증명하기 위하여", "본 계약을 증명하기", "이 계약의 체결을 증명",
    "위 계약을 증명", "기명날인", "서명날인",
    "IN WITNESS WHEREOF", "as of the date first",
)
EXECUTED_ROLES = {"execution"}

# 전문에서 '체결'을 말하는 문장 — 이 문장에 붙은 날짜만 계약일로 쓴다.
# 실측 근거: 전문 최대연도를 그냥 쓰면 기준일("기준일은 2023년 12월 31일"),
# 확약 기한("2017년 12월 31일까지"), 선행 계약 체결일("2014년 11월 26일 체결하였다")을
# 계약 연도로 잘못 집는다. 두 건을 원문 대조해 실제로 확인했다.
EXECUTION_PHRASES_KO = ("체결되었다", "체결된다", "체결한다", "체결하였다", "체결일",
                        "체결하고", "다음과 같이 계약을 체결", "본 계약을 체결")
EXECUTION_PHRASES_EN = ("entered into as of", "entered into on", "dated as of",
                        "made as of", "is made on", "is entered into",
                        "made and entered into")
# 계약일이 아닌 날짜를 끌어오는 표현 — 같은 문장에 있으면 채택하지 않는다.
DATE_DISTRACTORS = ("기준일", "까지", "이전에", "이후에", "만료", "존속기간",
                    "as of the Reference", "Reference Date")
# 월·일이 [ ]로 비어 있어도 연도는 읽을 수 있다("2024년 [4]월 [26]일").
YEAR_IN_SENTENCE = re.compile(r"(19[89]\d|20[0-3]\d)\s*[.년]")


def _years(text: str):
    found = [int(m.group(1)) for m in DATE_KO.finditer(text)]
    found += [int(m.group(1)) for m in DATE_EN.finditer(text)]
    found += [int(m.group(1)) for m in DATE_EN_ORD.finditer(text)]
    return [y for y in found if YEAR_MIN <= y <= YEAR_MAX]


def _first_date_text(text: str):
    for pattern in (DATE_KO, DATE_EN, DATE_EN_ORD):
        m = pattern.search(text)
        if m:
            return m.group(0).strip()
    return None


def _execution_sentence_year(text: str):
    """'체결' 서술이 있는 문장에서만 연도를 읽는다. (연도, 문장, 완전한날짜여부) 또는 None."""
    for sentence in _sentences(text):
        low = sentence.lower()
        if not (any(p in sentence for p in EXECUTION_PHRASES_KO)
                or any(p in low for p in EXECUTION_PHRASES_EN)):
            continue
        if any((d in sentence) if not d.isascii() else (d.lower() in low)
               for d in DATE_DISTRACTORS):
            continue                       # 기준일·기한이 섞인 문장은 쓰지 않는다
        full = _years(sentence)
        if full:
            return max(full), sentence, True
        m = YEAR_IN_SENTENCE.search(sentence)
        if m:
            return int(m.group(1)), sentence, False   # 월·일이 [ ]로 공란
    return None


def derive_deal_year(filename: str, paras, version_role=None) -> dict:
    """연도 파생. **어떤 날짜인지**(체결일/작성일/버전일자)를 basis.date_kind에 남긴다.

    계약 연도로 채택하는 것은 '체결'을 말하는 문장에 붙은 날짜뿐이다. 전문에 있는
    임의의 연도(기준일·확약 기한·선행 계약일)를 계약 연도로 쓰지 않는다."""
    filename = filename or ""
    executed = version_role in EXECUTED_ROLES

    if paras:
        body, headfoot = split_body(paras)

        # (1) 서명란 근처의 체결 문장 — 체결본이면 체결일
        for index, (no, text) in enumerate(body):
            if any(marker in text for marker in SIGNATURE_MARKERS):
                window = " ".join(t for _, t in body[index:index + 12])
                hit = _execution_sentence_year(window) or (
                    (max(_years(window)), window, True) if _years(window) else None)
                if hit:
                    year, sentence, complete = hit
                    level = "high" if (executed and complete) else "med"
                    return detail(
                        year, level,
                        rule="signature_block_date",
                        date_kind="체결일" if executed else "체결예정일(미체결본)",
                        para=no, matched=_first_date_text(sentence),
                        verbatim=sentence[:180],
                        source="body", version_role=version_role,
                        note=None if complete else "월·일이 공란이다 — 연도만 확인됨",
                    )
                break

        # (2) 전문의 '체결' 문장에 붙은 날짜
        head_paras = body[:40]
        head = " ".join(t for _, t in head_paras)
        hit = _execution_sentence_year(head)
        if hit:
            year, sentence, complete = hit
            if executed:
                level = "high" if complete else "med"
                kind = "체결일"
            else:
                level = "med" if complete else "low"
                kind = "작성일/체결예정일"
            return detail(
                year, level,
                rule="preamble_execution_sentence",
                date_kind=kind,
                para=head_paras[0][0] if head_paras else None,
                matched=_first_date_text(sentence), verbatim=sentence[:180],
                source="body", version_role=version_role,
                note=None if complete else "월·일이 공란인 미체결 문서다",
            )

        # (3) 전문에 연도만 있고 월·일이 공란 → 미체결 초안의 작성 연도
        m = DATE_KO_YEAR_ONLY.search(head)
        if m:
            return detail(
                int(m.group(1)), "low",
                rule="preamble_year_only_blank_date",
                date_kind="작성 연도(체결일 공란)", matched=m.group(0).strip(),
                source="body", version_role=version_role,
                note="월·일이 공란인 미체결 문서다 — 체결 연도로 단정할 수 없다",
            )

    # (4) 파일명 YYYYMMDD
    m = FILENAME_YMD.search(filename)
    if m:
        year = int(m.group(1))
        if YEAR_MIN <= year <= YEAR_MAX:
            return detail(
                year, "med" if executed else "low",
                rule="filename_full_date",
                date_kind="체결일(파일명)" if executed else "버전 일자(파일명)",
                matched=m.group(0), source="filename", version_role=version_role,
            )

    # (5) 머리글/바닥글 날짜 — 수정안 배포일
    if paras:
        _body, headfoot = split_body(paras)
        hf = " ".join(t for _, t in headfoot)
        years = _years(hf)
        if years:
            return detail(
                max(years), "low",
                rule="headerfooter_date",
                date_kind="문서 배포·수정일(머리글/바닥글)",
                matched=_first_date_text(hf), source="body_headerfooter",
                version_role=version_role,
                note="머리글의 날짜는 그 판본의 배포일이지 체결일이 아니다",
            )

    # (6) 파일명 YYMMDD — 버전번호와 구별 불가
    m = FILENAME_YYMMDD.search(filename)
    if m:
        return detail(
            2000 + int(m.group(1)), "low",
            rule="filename_yymmdd",
            date_kind="버전 일자 추정(6자리)", matched=m.group(0), source="filename",
            note="6자리는 버전번호·문서번호와 구별되지 않는다",
        )

    return unknown("no_date_signal",
                   note="파일명·본문 어디에도 판독 가능한 날짜가 없다",
                   source="none")


# --------------------------------------------------------------------------- #
# 축 2 — 거래 규모 구간
# --------------------------------------------------------------------------- #
# 원(KRW) 기준. 통화가 다르면 환산이 필요한데 환산에는 거래일 환율이 필요하고,
# 거래일(=연도)의 신뢰도가 낮으므로 **환산하지 않고 unknown**으로 둔다.
SIZE_BANDS = (
    ("소형", 0, 10_000_000_000),                      # 100억 미만
    ("중형", 10_000_000_000, 100_000_000_000),        # 100억 ~ 1,000억
    ("대형", 100_000_000_000, 1_000_000_000_000),     # 1,000억 ~ 1조
    ("초대형", 1_000_000_000_000, None),              # 1조 이상
)
BAND_NAMES = tuple(name for name, _lo, _hi in SIZE_BANDS)

# 대금이 '이 계약의 확정 대가'가 아닐 수 있는 유형 — 구간화 금지.
NON_BINDING_CTYPES = {"MOU"}


def band_for(amount_krw) -> str:
    for name, low, high in SIZE_BANDS:
        if amount_krw >= low and (high is None or amount_krw < high):
            return name
    return SIZE_BANDS[-1][0]


def derive_size_band(consideration, *, ctype=None, is_draft=None,
                     meta_schema_version=None) -> dict:
    """사람이 검수한 v3 대금만 구간화한다.

    v2 메타(consideration_json이 후보 문단 목록)는 정규화된 금액이 아니다 — 구간화 불가.
    비구속 MOU·초안·저신뢰·비원화는 **값 없음**으로 둔다. 참조금액(별도 계약의 투자금)이
    구간으로 승격되면 검색이 조용히 틀리기 때문이다."""
    if meta_schema_version is not None and int(meta_schema_version) < 3:
        return unknown("meta_schema_v2_not_normalized",
                       note="v2 대금은 후보 문단 목록이라 정규화 금액이 없다",
                       meta_schema_version=meta_schema_version)
    if not isinstance(consideration, dict):
        return unknown("no_consideration_section")
    if consideration.get("evaluated") is not True:
        return unknown("consideration_not_evaluated",
                       note="대금 섹션이 미평가다 — 부재와 혼동하지 마라")

    amount = consideration.get("amount_value")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return unknown("amount_value_null_after_review",
                       note="사람 검수 결과 이 계약 자체의 확정 대금이 없다"
                            "(공란·별도계약 참조금액·총액 미확정)",
                       amount_verbatim=(consideration.get("amount_verbatim") or "")[:120] or None)

    currency = (consideration.get("currency") or "").upper() or None
    if currency and currency != "KRW":
        return unknown("non_krw_requires_fx",
                       note="환산에는 거래일 환율이 필요하고 거래일 신뢰도가 낮다",
                       currency=currency, amount_value=amount)
    if ctype in NON_BINDING_CTYPES:
        return unknown("non_binding_instrument",
                       note="MOU·텀시트의 금액은 비구속 제안일 수 있다",
                       ctype=ctype, amount_value=amount)
    if is_draft == 1:
        return unknown("draft_amount_not_final",
                       note="초안의 금액은 확정 대가가 아니다",
                       amount_value=amount)

    level = normalize_confidence(consideration.get("confidence")) or "low"
    if level == "low":
        return unknown("amount_confidence_low",
                       note="추출 신뢰도가 낮은 금액은 구간화하지 않는다",
                       amount_value=amount)

    return detail(
        band_for(amount), level,
        rule="v3_curated_amount",
        amount_value=amount, currency=currency or "KRW",
        para=consideration.get("loc_start"),
        matched=(consideration.get("amount_verbatim") or "")[:160] or None,
        source="doc_meta_v3", reviewed="human_approved_60",
    )


# --------------------------------------------------------------------------- #
# 축 3 — 준거법
# --------------------------------------------------------------------------- #
GOV_ANCHORS = ("준거법", "governing law", "shall be governed by",
               "governed by and construed")
# 조항이 실제로 준거법을 '정하는' 문장인지 확인하는 서술어.
GOV_OPERATIVE_KO = ("준거법은", "준거법으로", "에 따라 규율", "법률로 한다", "법에 의한다",
                    "법률에 따라 해석", "법에 따라 해석")
GOV_OPERATIVE_EN = ("shall be governed", "is governed by", "governed by and construed",
                    "construed in accordance with the law")

JURISDICTIONS = {
    "대한민국": ("대한민국법", "대한민국 법", "대한민국의 법", "한국법", "한국의 법",
              "republic of korea", "korean law", "laws of korea", "law of korea"),
    "Delaware": ("delaware", "델라웨어"),
    "New York": ("new york", "뉴욕"),
    "England": ("english law", "laws of england", "law of england", "영국법",
                "england and wales"),
    "Singapore": ("laws of singapore", "singapore law", "싱가포르법",
                  "internal laws of singapore"),
    "Japan": ("laws of japan", "law of japan", "일본법"),
    "Hong Kong": ("laws of hong kong", "hong kong law", "홍콩법"),
    "China": ("people's republic of china", "중화인민공화국법", "중국법"),
    "Indonesia": ("indonesian law", "laws of indonesia", "인도네시아법"),
    "Cayman": ("cayman islands", "케이만", "케이맨"),
}

SENTENCE_SPLIT = re.compile(r"(?<=[.。])\s+|(?<=한다\.)\s*|(?<=있다\.)\s*")


def _sentences(text: str):
    parts = [s.strip() for s in SENTENCE_SPLIT.split(text) if s and s.strip()]
    return parts or [text]


def _named_jurisdictions(text: str):
    low = text.lower()
    hits = []
    for name, tokens in JURISDICTIONS.items():
        matched = [t for t in tokens if (t in low if t.isascii() else t in text)]
        if matched:
            hits.append((name, matched))
    return hits


def find_clause(paras, anchors, *, operative=(), fwd=3):
    """조항 앵커를 **모두** 모아 목차·공개목록을 걸러내고 서술어가 있는 것을 고른다.

    반환: (para_no, window_text, basis_note) 또는 None."""
    if not paras:
        return None
    body, _headfoot = split_body(paras)
    candidates = []
    for index, (no, text) in enumerate(body):
        low = text.lower()
        if not any((a in low) if a.isascii() else (a in text) for a in anchors):
            continue
        before = " ".join(t for _, t in body[max(0, index - 2):index])
        if "공개목록" in before or "사건번호" in before:
            continue                                  # 진행중 소송 공개목록
        window = " ".join(t for _, t in body[index:index + fwd + 1])
        toc = looks_like_toc(text)
        low_window = window.lower()
        has_op = any((o in low_window) if o.isascii() else (o in window)
                     for o in operative) if operative else True
        candidates.append((no, window, toc, has_op, index))
    if not candidates:
        return None
    # 목차가 아니고 서술어가 있는 것 → 목차가 아닌 것 → 남은 것 순
    for want_toc, want_op in ((False, True), (False, False), (True, True), (True, False)):
        for no, window, toc, has_op, _index in candidates:
            if toc == want_toc and has_op == want_op:
                note = None
                if toc:
                    note = "목차 줄만 발견됨 — 본문 조항을 특정하지 못했다"
                elif not has_op:
                    note = "표제만 있고 준거를 정하는 서술어가 없다"
                return no, window, note
    return None


def derive_governing_law(paras) -> dict:
    if not paras:
        return unknown("no_text_cache", note="본문 검색 불가 문서(스캔 PDF 등)")
    found = find_clause(paras, GOV_ANCHORS,
                        operative=GOV_OPERATIVE_KO + GOV_OPERATIVE_EN)
    if not found:
        return unknown("no_governing_law_clause_found",
                       note="준거법 조항 앵커를 찾지 못했다 — 부재가 아니라 미탐지다")
    para_no, window, note = found
    if note:
        return unknown("clause_not_localized", para=para_no, note=note,
                       matched=window[:160])

    ph = placeholder_hit(window)
    if ph:
        return unknown("placeholder_in_clause", para=para_no, matched=ph,
                       note="준거법이 공란인 양식·초안이다", verbatim=window[:160])
    bo = bracket_options_hit(window)
    if bo:
        return unknown("unresolved_bracket_options", para=para_no, matched=bo,
                       note="괄호 선택지가 확정되지 않았다", verbatim=window[:160])

    # 준거법을 '정하는 문장' 안에서만 관할지 이름을 읽는다.
    # (창 전체에서 읽으면 중재지·설립준거지·자회사 소재지를 준거법으로 오인한다.
    #  실측 예: 준거법 Indonesia인데 중재지가 Singapore인 계약을 Singapore로 오판했다.)
    operative_sentences = [
        s for s in _sentences(window)
        if any((o in s.lower()) if o.isascii() else (o in s)
               for o in GOV_OPERATIVE_KO + GOV_OPERATIVE_EN)
    ]
    scope_sentences = operative_sentences or [window]
    # 관할지 이름이 실제로 나온 문장만 증거로 삼는다 — 증거는 주장을 보여야 한다.
    named_sentences = [(s, _named_jurisdictions(s)) for s in scope_sentences]
    named_sentences = [(s, hits) for s, hits in named_sentences if hits]
    hits = sorted({n for _s, sentence_hits in named_sentences for n, _m in sentence_hits})
    evidence = named_sentences[0][0] if named_sentences else scope_sentences[0]
    window_hits = {n for n, _ in _named_jurisdictions(window)}
    other = sorted(window_hits - set(hits))

    if not hits:
        return unknown("jurisdiction_not_named", para=para_no,
                       note="준거법 조항은 있으나 관할지 이름을 판독하지 못했다",
                       verbatim=evidence[:200],
                       conflicts=other or None)
    if len(hits) > 1:
        return unknown("multiple_jurisdictions_in_operative_sentence",
                       para=para_no,
                       candidates=hits,
                       note="준거를 정하는 문장에 복수 관할지가 있다 — 사람 확인 필요",
                       verbatim=evidence[:220])
    matched = [m for _s, sentence_hits in named_sentences
               for n, ms in sentence_hits if n == hits[0] for m in ms]
    return detail(
        hits[0], "med" if operative_sentences else "low",
        rule="governing_law_clause",
        para=para_no, matched=sorted(set(matched)), verbatim=evidence[:220],
        source="body",
        conflicts=other or None,
        note=None if operative_sentences else
             "서술어 문장을 특정하지 못해 조항 창 전체에서 읽었다",
    )


# --------------------------------------------------------------------------- #
# 축 4 — 분쟁해결(관할법원 / 중재) — 준거법과 절대 합치지 않는다
# --------------------------------------------------------------------------- #
FORUM_ANCHORS = ("관할법원", "관할 법원", "전속적 관할", "전속관할", "합의관할",
                 "재판관할", "분쟁의 해결", "분쟁해결", "exclusive jurisdiction",
                 "submit to the jurisdiction", "dispute resolution")
FORUM_OPERATIVE = ("관할법원으로", "전속적 관할", "전속관할", "관할로 한다",
                   "exclusive jurisdiction", "submit to the")
COURT_RE = re.compile(r"((?:서울중앙|서울|부산|대구|인천|광주|대전|수원|의정부|춘천|청주|"
                      r"전주|제주|울산|창원)지방법원)")
# 지명만 잡는다. 뒤따르는 절("and to the jurisdiction ...", "shall have ...")까지
# 삼키면 값이 쓰레기가 된다(실측: "Delaware and to the jurisd").
COURT_EN = re.compile(
    r"courts?\s+of\s+(?:the\s+)?([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,2})"
    r"(?=\s*(?:,|\.|;|\)|shall|and\b|located|sitting|having|$))")

ARB_ANCHORS = ("중재", "arbitration")
ARB_BINDING_KO = ("최종적으로 해결", "중재로 해결", "중재에 의하여", "중재에 의해",
                  "중재로써", "중재를 통하여", "중재에 의하여 최종적으로")
ARB_BINDING_EN = ("shall be finally settled", "resolved by arbitration",
                  "referred to arbitration", "settled by arbitration",
                  "submitted to arbitration")
ARB_INSTITUTIONS = {
    "KCAB": ("대한상사중재원", "kcab", "korean commercial arbitration"),
    "ICC": ("international chamber of commerce", "icc rules", " icc "),
    "SIAC": ("siac", "singapore international arbitration"),
    "HKIAC": ("hkiac", "hong kong international arbitration"),
    "LCIA": ("lcia",),
    "UNCITRAL": ("uncitral",),
}
SEAT_RE = re.compile(
    r"seat\s+of\s+(?:the\s+)?arbitration\s+(?:shall\s+be\s+)?(?:in\s+)?"
    r"([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,2})"
    r"(?=\s*(?:,|\.|;|\)|and\b|shall|$))"
    r"|중재지(?:는|를|은)?\s*([가-힣]{2,10}|[A-Z][A-Za-z]{2,15})")


def derive_forum(paras) -> dict:
    """분쟁해결 축. 반환 dict의 하위 키는 **각각 독립된 사실**이다.

    - ``forum_type``      — court / arbitration / both / None
    - ``forum_court``     — 전속관할 법원 이름
    - ``arbitration``     — 중재 '합의'가 있는가 (단순 언급은 제외)
    - ``arbitration_institution`` / ``arbitration_seat``
    준거법과 합치지 않는다. 중재지를 준거법으로 쓰는 것이 이 축의 대표적 오류다."""
    out = {
        "forum_type": unknown("not_evaluated"),
        "forum_court": unknown("not_evaluated"),
        "arbitration": unknown("not_evaluated"),
        "arbitration_institution": unknown("not_evaluated"),
        "arbitration_seat": unknown("not_evaluated"),
    }
    if not paras:
        note = unknown("no_text_cache", note="본문 검색 불가 문서")
        return {k: dict(note) for k in out}

    court_value = None
    found = find_clause(paras, FORUM_ANCHORS, operative=FORUM_OPERATIVE)
    if not found:
        out["forum_court"] = unknown("no_forum_clause_found",
                                     note="관할 조항 앵커 미탐지 — 부재가 아니다")
    else:
        para_no, window, note = found
        if note:
            out["forum_court"] = unknown("clause_not_localized", para=para_no, note=note)
        else:
            ph = placeholder_hit(window)
            courts = sorted(set(COURT_RE.findall(window)))
            en_courts = [c.strip() for c in COURT_EN.findall(window)]
            if ph and not courts:
                out["forum_court"] = unknown("placeholder_in_clause", para=para_no,
                                             matched=ph, verbatim=window[:150])
            elif len(courts) == 1:
                court_value = courts[0]
                out["forum_court"] = detail(courts[0], "med", rule="forum_clause_named_court",
                                            para=para_no, matched=courts[0],
                                            verbatim=window[:180], source="body")
            elif len(courts) > 1:
                out["forum_court"] = unknown("multiple_courts_named", para=para_no,
                                             candidates=courts, verbatim=window[:180])
            elif en_courts:
                court_value = en_courts[0]
                out["forum_court"] = detail(en_courts[0], "low",
                                            rule="forum_clause_en_courts_of",
                                            para=para_no, matched=en_courts[0],
                                            verbatim=window[:180], source="body",
                                            note="영문 'courts of X'는 관할지 표기가 느슨하다")
            else:
                out["forum_court"] = unknown("forum_clause_no_court_named",
                                             para=para_no, verbatim=window[:180])

    # ---- 중재: '언급'과 '합의'를 구분한다 --------------------------------
    arb_found = find_clause(paras, ARB_ANCHORS,
                            operative=ARB_BINDING_KO + ARB_BINDING_EN, fwd=3)
    arb_value = False
    if not arb_found:
        # 앵커 자체가 없으면 중재 조항 없음(단, 미탐지 가능성은 basis에 남긴다)
        out["arbitration"] = detail(False, "low", rule="no_arbitration_anchor",
                                    note="'중재'/'arbitration' 토큰이 없다")
        out["arbitration_institution"] = unknown("no_arbitration_clause")
        out["arbitration_seat"] = unknown("no_arbitration_clause")
    else:
        para_no, window, note = arb_found
        low = window.lower()
        binding = any(k in window for k in ARB_BINDING_KO) or \
                  any(k in low for k in ARB_BINDING_EN)
        if not binding:
            out["arbitration"] = detail(
                False, "low", rule="arbitration_mentioned_without_agreement",
                para=para_no, verbatim=window[:180],
                note="정의조항의 '중재절차' 언급 등 — 중재합의가 아니다")
            out["arbitration_institution"] = unknown("no_arbitration_agreement")
            out["arbitration_seat"] = unknown("no_arbitration_agreement")
        else:
            arb_value = True
            out["arbitration"] = detail(True, "med", rule="arbitration_agreement",
                                        para=para_no, verbatim=window[:200],
                                        source="body")
            insts = [k for k, toks in ARB_INSTITUTIONS.items()
                     if any((t in low) if t.isascii() else (t in window) for t in toks)]
            if len(insts) == 1:
                out["arbitration_institution"] = detail(
                    insts[0], "med", rule="arbitration_institution_named",
                    para=para_no, matched=insts[0], verbatim=window[:180])
            elif len(insts) > 1:
                out["arbitration_institution"] = unknown(
                    "multiple_institutions_named", para=para_no, candidates=insts)
            else:
                out["arbitration_institution"] = unknown(
                    "institution_not_named", para=para_no,
                    note="중재합의는 있으나 중재기관을 판독하지 못했다")
            m = SEAT_RE.search(window)
            if m:
                seat = (m.group(1) or m.group(2) or "").strip()
                out["arbitration_seat"] = detail(
                    seat, "low", rule="arbitration_seat_phrase",
                    para=para_no, matched=m.group(0)[:80],
                    note="중재지는 준거법이 아니다 — 별도 사실로만 쓴다")
            else:
                out["arbitration_seat"] = unknown("seat_not_stated", para=para_no)

    if court_value and arb_value:
        out["forum_type"] = unknown(
            "court_and_arbitration_both_present",
            note="법원 관할과 중재합의가 함께 읽힌다 — 어느 쪽이 주된 절차인지 "
                 "사람 확인 필요(단계적 분쟁해결 조항일 수 있다)")
    elif arb_value:
        out["forum_type"] = detail("arbitration", "med", rule="arbitration_only")
    elif court_value:
        out["forum_type"] = detail("court", "med", rule="court_forum_only")
    else:
        out["forum_type"] = unknown("forum_not_determined")
    return out


# --------------------------------------------------------------------------- #
# 축 5 — 업종
# --------------------------------------------------------------------------- #
# 실측 결과 로컬 파생 불가로 판정했다. 이 함수는 값을 만들지 않고 **왜 못 만드는지**를
# 돌려준다. 근거: 사업 서술 어휘는 대상회사 업종이 아니라 진술보장 보일러플레이트에서
# 나온다("제조물책임", "지식재산권" 등). 실측에서 코퍼스 1,395건이 하나 이상의 업종
# 힌트에 걸렸고 그 중 777건이 2개 이상에 동시에 걸렸다 — 판별력이 없다.
BOILERPLATE_INDUSTRY_TRAPS = (
    "제조물책임", "제조물 책임", "product liability",
    "생산물배상책임", "지식재산권", "소프트웨어 라이선스",
)


def derive_industry(paras) -> dict:
    if not paras:
        return unknown("no_text_cache")
    body, _ = split_body(paras)
    text = " ".join(t for _, t in body)
    traps = [t for t in BOILERPLATE_INDUSTRY_TRAPS if t in text]
    return unknown(
        "not_locally_derivable",
        note="업종은 대상회사의 사실이지 계약서 문구의 사실이 아니다. 사업 서술 어휘는 "
             "진술보장 보일러플레이트에서 나와 판별력이 없다. 외부 기업정보(사업자번호·"
             "표준산업분류) 결합 또는 문서별 정독이 필요하다.",
        boilerplate_traps=traps[:4] or None,
        source="none",
    )


# --------------------------------------------------------------------------- #
# 문서 1건 파생
# --------------------------------------------------------------------------- #
def derive_document(row, txt_dir: Path) -> dict:
    """row: sqlite3.Row (files JOIN doc_meta). DB에 쓰지 않는다."""
    file_key = row["file_key"]
    paras = load_paras(txt_dir, file_key)
    consideration = None
    raw = row["consideration_json"] if "consideration_json" in row.keys() else None
    if raw:
        try:
            consideration = json.loads(raw)
        except (TypeError, ValueError):
            consideration = None

    forum = derive_forum(paras)
    result = {
        "file_key": file_key,
        "ctype": row["ctype"],
        "lang": row["lang"],
        "status": row["status"],
        "version_role": row["version_role"] if "version_role" in row.keys() else None,
        "text_cache": bool(paras),
        "deal_year": derive_deal_year(row["filename"], paras,
                                      row["version_role"] if "version_role" in row.keys() else None),
        "size_band": derive_size_band(
            consideration,
            ctype=row["ctype"],
            is_draft=row["is_draft"] if "is_draft" in row.keys() else None,
            meta_schema_version=row["meta_schema_version"]
            if "meta_schema_version" in row.keys() else None,
        ),
        "governing_law": derive_governing_law(paras),
        "industry": derive_industry(paras),
    }
    result.update(forum)
    return result


FIELDS = ("deal_year", "size_band", "governing_law", "forum_type", "forum_court",
          "arbitration", "arbitration_institution", "arbitration_seat", "industry")


# --------------------------------------------------------------------------- #
# 코퍼스 집계
# --------------------------------------------------------------------------- #
def summarize(records) -> dict:
    """축별 커버리지: 값이 있는 비율, 신뢰도 분포, unknown 사유 분포."""
    total = len(records)
    summary = {}
    for field in FIELDS:
        populated = 0
        by_conf = collections.Counter()
        by_value = collections.Counter()
        by_reason = collections.Counter()
        for record in records:
            item = record.get(field) or {}
            if is_unknown(item):
                by_reason[item.get("basis", {}).get("rule", "unspecified")] += 1
            else:
                populated += 1
                by_conf[item.get("confidence") or "unrated"] += 1
                by_value[str(item.get("value"))] += 1
        summary[field] = {
            "documents": total,
            "populated": populated,
            "coverage_pct": round(100.0 * populated / total, 1) if total else 0.0,
            "high_or_med": by_conf["high"] + by_conf["med"],
            "high_or_med_pct": round(100.0 * (by_conf["high"] + by_conf["med"]) / total, 1)
            if total else 0.0,
            "by_confidence": dict(by_conf),
            "top_values": dict(by_value.most_common(12)),
            "unknown_reasons": dict(by_reason.most_common(12)),
        }
    return summary


def build_report(out: Path, limit=None) -> dict:
    db = (Path(out) / "catalog.sqlite").resolve()
    if not db.is_file():
        raise FileNotFoundError(f"catalog.sqlite not found: {db}")
    txt_dir = Path(out) / "txt"
    sql = """
        SELECT f.file_key, f.filename, f.ctype, f.lang, f.status, f.is_draft,
               f.version_role,
               d.consideration_json, d.meta_schema_version
          FROM files f
          LEFT JOIN doc_meta d ON d.file_key = f.file_key
         WHERE COALESCE(f.status,'') != 'missing'
         ORDER BY f.file_key
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    records = []
    with closing(sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        for row in conn.execute(sql):
            records.append(derive_document(row, txt_dir))
    return {
        "deriver_version": DERIVER_VERSION,
        "database": str(db),
        "documents": len(records),
        "writes_performed": 0,
        "note": "읽기 전용 dry-run이다. DB 반영은 소유자 검토 후 조율자가 수행한다.",
        "summary": summarize(records),
        "records": records,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("cs_index"))
    parser.add_argument("--report", type=Path,
                        help="레코드 포함 전체 리포트 JSON 경로")
    parser.add_argument("--summary-only", action="store_true",
                        help="stdout에는 축별 커버리지 요약만 출력")
    parser.add_argument("--limit", type=int, help="상위 N건만(디버그)")
    parser.add_argument("--file-key", help="1건만 파생해 근거를 출력")
    args = parser.parse_args(argv)

    if args.file_key:
        db = (args.out / "catalog.sqlite").resolve()
        with closing(sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT f.file_key, f.filename, f.ctype, f.lang, f.status, f.is_draft,"
                " f.version_role, d.consideration_json, d.meta_schema_version"
                " FROM files f LEFT JOIN doc_meta d ON d.file_key=f.file_key"
                " WHERE f.file_key=?", (args.file_key,)).fetchone()
        if row is None:
            print(json.dumps({"error": "file_key not found"}, ensure_ascii=False))
            return 1
        print(json.dumps(derive_document(row, args.out / "txt"),
                         ensure_ascii=False, indent=1))
        return 0

    report = build_report(args.out, limit=args.limit)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    payload = {k: v for k, v in report.items() if k != "records"}
    print(json.dumps(payload, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

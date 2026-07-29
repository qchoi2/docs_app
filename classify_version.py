#!/usr/bin/env python3
"""Contract version-role classification (체결본/초안/mark-up + 당사자).

계약서는 같은 거래(project)에 대해 여러 버전(체결본·매수인/매도인 초안·mark-up)이
존재한다. 이 도구는 파일명에서 version_role을 분류해 `files.version_role`에 저장하고
(검색 버전 필터의 기반), 재추출·정독 우선순위를 project 단위로 dedup(체결본 우선,
최종적으로는 전 버전 정독)하여 산출한다.

version_role 값:
  execution        체결본/최종본 (execution·signed·최종본·final·definitive)
  buyer_draft      매수인 초안
  seller_draft     매도인 초안
  buyer_markup     매수인 mark-up (mark-up·redline·수정·코멘트)
  seller_markup    매도인 mark-up
  draft_unknown    당사자 미상 초안
  markup_unknown   당사자 미상 mark-up
  buyer_ver / seller_ver  당사자만 식별, 단계 미상
  unknown          판별 불가

검색 표시용 한글 라벨은 VERSION_LABELS 참조.

**분류는 파일명 휴리스틱이다.** 본문을 읽지 않으므로 파일명에 표식이 없는
체결본은 unknown으로 남는다. 따라서 모든 분류는 근거(version_basis)와
신뢰도(version_confidence: high/med/low)를 함께 기록하고, 검색의 --version
필터는 제외 모집단을 반드시 고지한다(build_version_filter_notice).
저장 형태는 files.source_signals(분류 단서 JSON) / doc_meta.confidence
(low·med·high) 선례를 따른다.

Usage:
  python classify_version.py --out cs_index --apply          # DB에 version_role/basis/confidence 부여(백업)
  python classify_version.py --out cs_index --dry-run        # 쓰기 없이 분포만 확인(mode=ro)
  python classify_version.py --out cs_index --priority OUT.json  # 재추출 우선순위(체결본 우선 dedup)
"""
import argparse
import collections
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

VERSION_LABELS = {
    "execution": "체결본",
    "bidding": "입찰제출본(매수인)",
    "buyer_draft": "매수인 초안",
    "seller_draft": "매도인 초안",
    "buyer_markup": "매수인 mark-up",
    "seller_markup": "매도인 mark-up",
    "draft_unknown": "초안(당사자 미상)",
    "markup_unknown": "mark-up(당사자 미상)",
    "buyer_ver": "매수인측 버전",
    "seller_ver": "매도인측 버전",
    "unknown": "버전 미상",
}

def _normalize_version_token(value: str) -> str:
    """검색 버전 필터 매칭용 정규화: 공백 축약 + casefold."""
    return " ".join(str(value or "").split()).casefold()


def build_version_lookup() -> dict:
    """정규화된 role key / 한글 라벨(공백 포함·미포함) → canonical role key 역인덱스.

    검색 도구의 --version 필터가 role key("buyer_draft")와 한글 라벨("매수인 초안"),
    공백 없는 변형("매수인초안")을 모두 받도록 한다. VERSION_LABELS를 단일 출처로 사용."""
    lookup: dict = {}
    for role, label in VERSION_LABELS.items():
        lookup[_normalize_version_token(role)] = role
        lookup[_normalize_version_token(label)] = role
        lookup["".join(str(label).split()).casefold()] = role  # 공백 제거 변형
    return lookup


def version_label(role) -> str:
    """role key → 한글 표시 라벨. 미분류(None/빈값)는 None, 미지의 값은 원문 유지."""
    if role in (None, ""):
        return None
    return VERSION_LABELS.get(role, role)


def resolve_version_filter(value) -> list:
    """--version 값(콤마 구분 가능)을 canonical role key 리스트로 파싱한다.

    role key 또는 한글 라벨(공백 유무 무관)을 받아 정규화한다. 알 수 없는 값은
    유효 옵션 목록과 함께 ValueError를 던진다. None/빈 입력은 None(필터 없음)."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        tokens = [str(item) for item in value]
    else:
        tokens = str(value).split(",")
    lookup = build_version_lookup()
    roles: list = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        role = lookup.get(_normalize_version_token(token))
        if role is None:
            valid_keys = ", ".join(VERSION_LABELS.keys())
            valid_labels = ", ".join(VERSION_LABELS.values())
            raise ValueError(
                f"Unknown version '{token}'. "
                f"Valid role keys: {valid_keys}. Valid labels: {valid_labels}."
            )
        if role not in roles:
            roles.append(role)
    return roles or None


# 정독 우선순위: 낮을수록 먼저. 체결본이 최우선, 그 다음 초안, mark-up/bidding 순.
VERSION_RANK = {
    "execution": 0,
    "seller_draft": 2, "buyer_draft": 2, "draft_unknown": 2,
    "seller_markup": 3, "buyer_markup": 3, "markup_unknown": 3, "bidding": 3,
    "buyer_ver": 4, "seller_ver": 4,
    "unknown": 5,
}

# --------------------------------------------------------------------------- #
# 파일명 토큰 — 강한 토큰(단독으로 단정 가능)과 약한 토큰(다른 뜻일 수 있음)을
# 구분한다. 이 구분이 곧 version_confidence의 근거다.
# --------------------------------------------------------------------------- #
_EXEC_STRONG = ("체결", "execution", "signed", "signing", "exec_", "_exec",
                "최종본", "definitive")
# "final"/"fnl"은 "final draft"처럼 초안에도 붙는다 → 단독이면 med, 초안/markup
# 토큰과 함께 나오면 low.
_EXEC_WEAK = ("final", "fnl")
_EXEC = _EXEC_STRONG + _EXEC_WEAK
_BIDDING_STRONG = ("bidding",)
_BIDDING_WEAK = ("제출본",)          # 입찰 외 제출본일 수 있다
_BIDDING = _BIDDING_STRONG + _BIDDING_WEAK
# mark-up 라운드: 초안 작성측의 상대방이 수정.
_MARKUP_EXPLICIT = ("markup", "mark-up", "mark up", "redline", "수정",
                    "코멘트", "comment")
# "1st/2nd/3rd"(라운드 표기)만으로 mark-up이라 보는 것은 약한 추정이다
# ("1st draft"도 이 토큰에 걸린다) → 단독이면 low.
_MARKUP_ROUND = ("1st", "2nd", "3rd")
_MARKUP = _MARKUP_EXPLICIT + _MARKUP_ROUND
_DRAFT_EXPLICIT = ("draft", "초안")
_DRAFT_WEAK = ("_v1", "내부", "안)")
_DRAFT = _DRAFT_EXPLICIT + _DRAFT_WEAK
_PARTY_TOKENS = {"buyer": ("buyer", "매수인"), "seller": ("seller", "매도인")}

CONFIDENCE_LEVELS = ("high", "med", "low")   # v4_clause_item.confidence와 동일 어휘
_CONFIDENCE_ORDER = {"high": 0, "med": 1, "low": 2}


def normalize_confidence(value):
    """DB/JSON에서 온 confidence를 정규화한다. 미기록·미지의 값은 None."""
    token = str(value or "").strip().lower()
    return token if token in CONFIDENCE_LEVELS else None


def _downgrade(confidence: str, steps: int = 1) -> str:
    index = min(_CONFIDENCE_ORDER.get(confidence, 2) + steps, 2)
    return CONFIDENCE_LEVELS[index]


def _matched(text: str, tokens) -> list:
    return [token for token in tokens if token in text]


def _detail(role: str, confidence: str, **basis) -> dict:
    """role/confidence/basis 3종 세트. basis의 빈 값은 기록하지 않는다."""
    clean = {key: value for key, value in basis.items() if value not in (None, [], {}, "")}
    clean.setdefault("source", "filename")
    return {"role": role, "confidence": confidence, "basis": clean}


def classify_version_detail(filename: str) -> dict:
    """파일명 → {role, confidence, basis}.

    role 판정 순서·결과는 classify_version()과 동일하다(재분류로 분포가 바뀌지
    않는다). 추가되는 것은 어떤 토큰/규칙이 발화했는지(basis)와 그 규칙이 얼마나
    믿을 만한지(confidence)뿐이다."""
    s = (filename or "").lower()
    exec_strong = _matched(s, _EXEC_STRONG)
    exec_weak = _matched(s, _EXEC_WEAK)
    markup_explicit = _matched(s, _MARKUP_EXPLICIT)
    markup_round = _matched(s, _MARKUP_ROUND)
    draft_explicit = _matched(s, _DRAFT_EXPLICIT)
    draft_weak = _matched(s, _DRAFT_WEAK)
    stage_tokens = markup_explicit + markup_round + draft_explicit + draft_weak
    round_no = _markup_round(filename)

    if exec_strong or exec_weak:
        if exec_strong:
            confidence = "med" if stage_tokens else "high"
        else:
            confidence = "low" if stage_tokens else "med"
        return _detail(
            "execution", confidence,
            rule="execution_token",
            matched=exec_strong + exec_weak,
            token_strength="strong" if exec_strong else "weak",
            conflicts=stage_tokens,
        )
    bidding_strong = _matched(s, _BIDDING_STRONG)
    bidding_weak = _matched(s, _BIDDING_WEAK)
    if bidding_strong or bidding_weak:
        return _detail(
            "bidding", "high" if bidding_strong else "med",
            rule="bidding_token",
            matched=bidding_strong + bidding_weak,
            token_strength="strong" if bidding_strong else "weak",
        )

    party_hits = {name: _matched(s, tokens) for name, tokens in _PARTY_TOKENS.items()}
    named_parties = [name for name, hits in party_hits.items() if hits]
    party = named_parties[0] if named_parties else None   # buyer 우선(기존 동작)
    party_matched = [token for hits in party_hits.values() for token in hits]
    ambiguous_party = len(named_parties) > 1

    if markup_explicit or markup_round:
        stage, stage_matched = "markup", markup_explicit + markup_round
        stage_strength = "explicit" if markup_explicit else "round_ordinal"
    elif draft_explicit or draft_weak:
        stage, stage_matched = "draft", draft_explicit + draft_weak
        stage_strength = "explicit" if draft_explicit else "weak"
    else:
        stage, stage_matched, stage_strength = None, [], None

    if party and stage:
        confidence = "high" if stage_strength == "explicit" else "med"
        if ambiguous_party:
            confidence = _downgrade(confidence)
        return _detail(
            f"{party}_{stage}", confidence,
            rule="party_and_stage", matched=party_matched + stage_matched,
            party=party, party_matched=party_matched,
            stage=stage, stage_strength=stage_strength,
            round=round_no,
            conflicts=[name for name in named_parties if name != party],
        )
    if party:
        return _detail(
            f"{party}_ver", "low" if ambiguous_party else "med",
            rule="party_only", matched=party_matched, party=party,
            note="stage_not_stated_in_filename",
            conflicts=[name for name in named_parties if name != party],
        )
    if stage:
        return _detail(
            f"{stage}_unknown", "med" if stage_strength == "explicit" else "low",
            rule="stage_only", matched=stage_matched, stage=stage,
            stage_strength=stage_strength, round=round_no,
            note="party_not_stated_in_filename",
        )
    return _detail("unknown", "low", rule="no_signal", source="none",
                   note="no_version_token_in_filename")


def classify_version(filename: str) -> str:
    """파일명 → version_role 키(하위 호환 API). 근거·신뢰도는 classify_version_detail."""
    return classify_version_detail(filename)["role"]


def _markup_round(filename: str):
    """파일명의 mark-up 라운드 번호(1st/2nd/3rd → 1/2/3). 없으면 None."""
    m = re.search(r"(\d+)\s*(?:st|nd|rd|th)\b", (filename or "").lower())
    return int(m.group(1)) if m else None


def _resolve_markup_parties(details: dict, groups: dict) -> None:
    """당사자 미상 mark-up(markup_unknown)의 당사자를, 같은 거래(project)의 초안
    작성자와 라운드 패리티로 추론한다. 초안 작성자의 상대방이 1st mark-up을 하고,
    작성자 본인이 2nd mark-up(재수정)을 한다 → 홀수 라운드=상대방, 짝수=작성자.
    파일명에 당사자가 명시된 건 그대로 두고, 미상 + 라운드번호 있는 것만 보정한다.
    초안 작성자를 특정할 수 없는 거래는 markup_unknown으로 남긴다.

    이 경로는 파일명이 말하지 않은 것을 관행으로 메우는 **추론**이므로 결과는
    항상 confidence=low이고 basis에 추론 사실을 남긴다."""
    for members in groups.values():
        authors = set()
        for fk in members:
            role = details[fk]["role"]
            if role == "seller_draft":
                authors.add("seller")
            elif role == "buyer_draft":
                authors.add("buyer")
        if len(authors) != 1:
            continue                       # 초안 작성자 불명확 → 보정 안 함
        author = next(iter(authors))
        opponent = "buyer" if author == "seller" else "seller"
        for fk in members:
            detail = details[fk]
            round_no = detail["basis"].get("round")
            if detail["role"] == "markup_unknown" and round_no:
                who = opponent if round_no % 2 == 1 else author
                detail["role"] = f"{who}_markup"
                detail["confidence"] = "low"     # 파일명이 아니라 관행 추론
                detail["basis"] = {
                    **detail["basis"],
                    "source": "filename+round_parity",
                    "inference": {
                        "kind": "round_parity",
                        "draft_author": author,
                        "round": round_no,
                        "assigned_party": who,
                        "rule": "odd_round=counterparty, even_round=draft_author",
                    },
                }


# --------------------------------------------------------------------------- #
# 저장/조회 헬퍼 — files.version_basis(JSON) + files.version_confidence(TEXT).
# 아직 백필되지 않은 DB(컬럼 없음 / NULL)에서도 절대 죽지 않고, "확신 있는 답"으로
# 보이지도 않게 degrade하는 것이 이 계층의 계약이다.
# --------------------------------------------------------------------------- #
VERSION_META_COLUMNS = {"version_basis": "TEXT", "version_confidence": "TEXT"}
# 버전 귀속이 아예 없는 라벨.
UNATTRIBUTED_ROLES = {None, "", "unknown"}
# 요청한 role의 "부분 미상" 대응 라벨 — 필터에서 빠지지만 실제로는 그 버전일 수
# 있는 모집단(예: 매수인 초안을 물으면 draft_unknown·buyer_ver가 후보다).
VERSION_PARTIAL_MATCHES = {
    "buyer_draft": ("draft_unknown", "buyer_ver"),
    "seller_draft": ("draft_unknown", "seller_ver"),
    "buyer_markup": ("markup_unknown", "buyer_ver"),
    "seller_markup": ("markup_unknown", "seller_ver"),
    "buyer_ver": ("draft_unknown", "markup_unknown"),
    "seller_ver": ("draft_unknown", "markup_unknown"),
    "draft_unknown": ("buyer_ver", "seller_ver"),
    "markup_unknown": ("buyer_ver", "seller_ver"),
}
VERSION_CLASSIFICATION_BASIS = "filename_heuristic"


def has_version_meta(conn) -> bool:
    """files 테이블에 version_basis/version_confidence 컬럼이 있는가."""
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
    except sqlite3.Error:
        return False
    return set(VERSION_META_COLUMNS).issubset(cols)


def version_meta_select(conn, alias: str = "f") -> str:
    """SELECT 절 조각. 컬럼이 없는 DB에서는 NULL로 대체해 쿼리가 깨지지 않게 한다."""
    if has_version_meta(conn):
        prefix = f"{alias}." if alias else ""
        return (f"{prefix}version_basis AS version_basis, "
                f"{prefix}version_confidence AS version_confidence")
    return "NULL AS version_basis, NULL AS version_confidence"


def ensure_version_meta_columns(conn) -> list:
    """없는 컬럼만 추가하고 추가된 컬럼명을 돌려준다(가산적 마이그레이션)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
    added = []
    if "version_role" not in cols:
        conn.execute("ALTER TABLE files ADD COLUMN version_role TEXT")
        added.append("version_role")
    for name, ddl in VERSION_META_COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE files ADD COLUMN {name} {ddl}")
            added.append(name)
    return added


def row_value(row, name, default=None):
    """sqlite3.Row/dict에서 없는 컬럼을 KeyError 없이 읽는다."""
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(name, default)
    try:
        keys = row.keys()
    except AttributeError:
        return default
    return row[name] if name in keys else default


def decode_version_basis(raw):
    """version_basis(JSON 문자열) → dict. NULL/파손 값은 죽지 않고 degrade."""
    if raw in (None, ""):
        return None
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {"raw": str(raw), "rule": "unparsable_basis"}
    return value if isinstance(value, dict) else {"raw": str(raw)}


def version_review_required(role, confidence) -> bool:
    """이 버전 라벨을 '확인 필요'로 표시해야 하는가 (is_draft=null 취급과 동일 철학)."""
    if role in UNATTRIBUTED_ROLES:
        return True
    return normalize_confidence(confidence) in (None, "low")


def version_basis_summary(role, basis, confidence) -> str:
    """사람이 읽는 한 줄 근거. 근거가 없으면 없다고 말한다(추측 금지)."""
    level = normalize_confidence(confidence)
    basis = decode_version_basis(basis)
    if not basis:
        return "분류 근거 미기록 — 파일명 휴리스틱 결과만 있음 (classify_version.py --apply 전)"
    parts = []
    matched = basis.get("matched") or []
    if matched:
        parts.append("파일명 토큰 " + ", ".join(f"'{token}'" for token in matched))
    rule = basis.get("rule")
    if rule == "no_signal":
        parts.append("파일명에 버전 단서 없음")
    elif rule and not matched:
        parts.append(f"규칙 {rule}")
    inference = basis.get("inference")
    if isinstance(inference, dict) and inference.get("kind") == "round_parity":
        parts.append(
            "라운드 패리티 추론(초안 작성자 %s, %s라운드 → %s)"
            % (inference.get("draft_author"), inference.get("round"),
               inference.get("assigned_party"))
        )
    conflicts = basis.get("conflicts") or []
    if conflicts:
        parts.append("상충 토큰 " + ", ".join(str(token) for token in conflicts))
    if basis.get("note"):
        parts.append(str(basis["note"]))
    summary = " · ".join(parts) if parts else "근거 정보 없음"
    return f"{summary} (신뢰도 {level or '미기록'})"


def annotate_version_row(row) -> dict:
    """검색 결과 행에 version_label/basis/confidence/review 플래그를 붙인다.

    dict를 받아 같은 dict를 변형해 돌려준다. 컬럼이 없거나 NULL이어도 안전하다."""
    item = row if isinstance(row, dict) else dict(row)
    role = item.get("version_role")
    confidence = normalize_confidence(item.get("version_confidence"))
    basis = decode_version_basis(item.get("version_basis"))
    item["version_label"] = version_label(role)
    item["version_confidence"] = confidence
    item["version_basis"] = basis
    item["version_basis_summary"] = version_basis_summary(role, basis, confidence)
    item["version_review_required"] = version_review_required(role, confidence)
    return item


def build_version_filter_notice(requested, buckets, *, meta_available: bool = True,
                                review_candidates=None) -> dict:
    """--version 필터가 무엇을 걸러냈는지 고지하는 구조체.

    ``buckets``는 버전 필터를 **적용하기 전** 모집단의 (role, confidence, count)
    3튜플들이다. 반환 dict의 excluded_* 카운트는 서로 배타적이지 않다 —
    같은 문서가 excluded_unknown이면서 excluded_low_confidence일 수 있다.
    배타적인 총계는 excluded_total 하나뿐이다."""
    requested = list(requested or [])
    wanted = set(requested)
    partial_roles = set()
    for role in requested:
        partial_roles.update(VERSION_PARTIAL_MATCHES.get(role, ()))
    partial_roles -= wanted

    matched = matched_low = 0
    excluded_total = excluded_unknown = excluded_low = excluded_unrated = 0
    excluded_partial: dict = {}
    excluded_by_role: dict = {}
    buckets = list(buckets)
    # 신뢰도가 하나도 기록돼 있지 않으면 "백필 전"이다 — 저신뢰와 구분해 고지한다.
    any_rated = any(
        normalize_confidence(confidence) is not None
        for _role, confidence, _count in buckets
    )
    for role, confidence, count in buckets:
        count = int(count or 0)
        level = normalize_confidence(confidence)
        if role in wanted:
            matched += count
            if level in (None, "low"):
                matched_low += count
            continue
        excluded_total += count
        key = role if role not in (None, "") else "(미분류)"
        excluded_by_role[key] = excluded_by_role.get(key, 0) + count
        if role in UNATTRIBUTED_ROLES:
            excluded_unknown += count
        if role in partial_roles:
            excluded_partial[role] = excluded_partial.get(role, 0) + count
        if level == "low":
            excluded_low += count
        elif level is None:
            excluded_unrated += count

    warnings = []
    if excluded_unknown:
        warnings.append(f"version_filter_excluded_unknown:{excluded_unknown}")
    if excluded_partial:
        warnings.append(
            f"version_filter_excluded_partial:{sum(excluded_partial.values())}"
        )
    if excluded_low:
        warnings.append(f"version_filter_excluded_low_confidence:{excluded_low}")
    if matched_low:
        warnings.append(f"version_low_confidence_results:{matched_low}")
    backfilled = bool(meta_available) and (any_rated or not buckets)
    if not backfilled:
        warnings.append("version_classification_not_backfilled")

    labels = ", ".join(version_label(role) or role for role in requested)
    message = (
        f"버전 필터({labels})는 파일명 휴리스틱 분류 결과에 대한 필터다. "
        f"같은 조건에서 버전 때문에 제외된 문서 {excluded_total}건 중 "
        f"버전 미상 {excluded_unknown}건, 당사자·단계 부분 미상 "
        f"{sum(excluded_partial.values())}건, 저신뢰 분류 {excluded_low}건은 "
        "요청한 버전일 수 있다. 이 결과로 '해당 버전 전수'를 단정하지 마라."
    )
    if matched_low:
        message += f" 결과에 포함된 {matched_low}건도 분류 신뢰도가 낮아 확인이 필요하다."
    if not backfilled:
        message += (
            " 이 모집단에는 분류 근거·신뢰도가 기록돼 있지 않다"
            " (python classify_version.py --out <cs_index> --apply 필요)."
        )
    return {
        "requested": requested,
        "requested_labels": [version_label(role) or role for role in requested],
        "classification_basis": VERSION_CLASSIFICATION_BASIS,
        "classification_recorded": backfilled,
        "matched_documents": matched,
        "matched_low_confidence": matched_low,
        "excluded_total": excluded_total,
        "excluded_unknown": excluded_unknown,
        "excluded_partial": excluded_partial,
        "excluded_low_confidence": excluded_low,
        "excluded_unrated": excluded_unrated,
        "excluded_by_role": excluded_by_role,
        "review_candidates": list(review_candidates or []),
        "warning": message,
        "warnings": warnings,
    }


def classify_all(conn) -> dict:
    """DB 전체를 분류해 file_key → {role, confidence, basis}를 돌려준다(읽기 전용)."""
    details: dict = {}
    groups = collections.defaultdict(list)
    for fk, fn, path, ctype, lang in conn.execute(
        "SELECT file_key, filename, path, ctype, lang FROM files"
    ).fetchall():
        details[fk] = classify_version_detail(fn)
        groups[(ctype, lang, _project_key(path or ""))].append(fk)
    _resolve_markup_parties(details, groups)   # 라운드 패리티로 당사자 보정
    return details


def _distribution(details: dict) -> dict:
    counts: dict = {}
    by_confidence: dict = {}
    by_rule: dict = {}
    for detail in details.values():
        role, confidence = detail["role"], detail["confidence"]
        counts[role] = counts.get(role, 0) + 1
        by_confidence[confidence] = by_confidence.get(confidence, 0) + 1
        rule = detail["basis"].get("rule", "unknown_rule")
        by_rule[rule] = by_rule.get(rule, 0) + 1
    return {"counts": counts, "confidence": by_confidence, "rules": by_rule}


def dry_run(out: Path) -> dict:
    """쓰기 없이(mode=ro) 재분류 분포를 계산한다 — --apply 전 확인용."""
    db = (Path(out) / "catalog.sqlite").resolve()
    if not db.is_file():
        raise FileNotFoundError(f"catalog.sqlite not found: {db}")
    with closing(sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)) as conn:
        details = classify_all(conn)
        meta = has_version_meta(conn)
    report = _distribution(details)
    report["version_meta_columns_present"] = meta
    report["would_write"] = ["version_role", *VERSION_META_COLUMNS]
    return report


def apply_to_db(out: Path) -> dict:
    db = out / "catalog.sqlite"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = out / f".backups/catalog.pre_version_role_{stamp}.sqlite"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as s, closing(sqlite3.connect(backup)) as d:
        s.backup(d)
    with closing(sqlite3.connect(db)) as conn:
        added = ensure_version_meta_columns(conn)
        details = classify_all(conn)
        for fk, detail in details.items():
            conn.execute(
                "UPDATE files SET version_role=?, version_basis=?, "
                "version_confidence=? WHERE file_key=?",
                (
                    detail["role"],
                    json.dumps(detail["basis"], ensure_ascii=False, sort_keys=True),
                    detail["confidence"],
                    fk,
                ),
            )
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    report = _distribution(details)
    report.update({"backup": backup.name, "columns_added": added,
                   "integrity": integrity})
    return report


def _project_key(path: str) -> str:
    from review_v4_scope_sample import _project_key as pk
    return pk(path)


def build_priority(out: Path, manifest: Path) -> list:
    """재추출 대상을 거래(project)로 묶어 체결본 우선 대표를 뽑고, 나머지 버전은
    2차(최종 전부 정독) 큐로 둔다. 각 항목에 version_role·project·tier(1=체결본대표/
    1초안대표, 2=중복버전)를 붙인다."""
    db = out / "catalog.sqlite"
    man = json.loads(manifest.read_text(encoding="utf-8"))
    import collections
    groups = collections.defaultdict(list)
    with closing(sqlite3.connect(db)) as conn:
        for d in man:
            fk = d["file_key"]
            r = conn.execute(
                "SELECT path, filename, ctype, lang FROM files WHERE file_key=?", (fk,)
            ).fetchone()
            if not r:
                continue
            vr = classify_version(r[1])
            groups[(r[2], r[3], _project_key(r[0]))].append(
                {"file_key": fk, "ctype": r[2], "lang": r[3],
                 "version_role": vr, "rank": VERSION_RANK.get(vr, 5)}
            )
    out_rows = []
    for (ctype, lang, pk), members in groups.items():
        members.sort(key=lambda m: m["rank"])
        rep = members[0]
        for i, m in enumerate(members):
            m["project"] = pk
            m["reextract_tier"] = 1 if i == 0 else 2   # 1=대표(체결본 우선), 2=중복버전(2차)
            m["rep_is_execution"] = rep["version_role"] == "execution"
            out_rows.append(m)
    out_rows.sort(key=lambda m: (m["reextract_tier"], m["rank"]))
    return out_rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("cs_index"))
    p.add_argument("--apply", action="store_true",
                   help="files.version_role/version_basis/version_confidence 부여(백업 후)")
    p.add_argument("--dry-run", action="store_true",
                   help="쓰기 없이 재분류 분포만 출력(mode=ro)")
    p.add_argument("--priority", type=Path, help="재추출 우선순위 JSON 경로")
    p.add_argument("--manifest", type=Path, default=Path("cs_index/rw_reextraction_manifest.json"))
    args = p.parse_args(argv)
    if args.dry_run:
        print(json.dumps(dry_run(args.out), ensure_ascii=False, indent=1))
    if args.apply:
        res = apply_to_db(args.out)
        print(json.dumps(res, ensure_ascii=False, indent=1))
    if args.priority:
        rows = build_priority(args.out, args.manifest)
        args.priority.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        t1 = sum(1 for r in rows if r["reextract_tier"] == 1)
        print(json.dumps({"total": len(rows), "tier1_representatives": t1,
                          "tier2_duplicate_versions": len(rows) - t1,
                          "written": str(args.priority)}, ensure_ascii=False, indent=1))
    if not args.apply and not args.priority and not args.dry_run:
        p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

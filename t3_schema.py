"""Validation contract for precise T3 metadata (schema version 3).

Version 2 remains readable for the current corpus.  Version 3 is intentionally
stricter: every evaluated area has an explicit state, every present clause has
paragraph evidence, and normalized values are separated from verbatim text.
"""

from __future__ import annotations

from typing import Dict, List, Sequence


V3_SCHEMA_VERSION = 3
CONFIDENCE_VALUES = ("low", "med", "high")
DOCUMENT_STATUS_VALUES = ("contract", "not_contract", "insufficient_text")

COMMON_REQUIRED_TAGS = (
    "진술보장",
    "선행조건",
    "확약",
    "손해배상",
    "해제",
    "분쟁해결",
    "준거법",
    "비밀유지",
    "경업금지",
    "MAC",
    "earn-out",
)

TYPE_REQUIRED_TAGS = {
    "SPA": ("대금조정", "에스크로", "조세배상", "계약이전동의"),
    "SSA": ("대금조정", "에스크로", "조세배상"),
    "SHA": (
        "주식양도제한",
        "우선매수권",
        "동반매도참여권",
        "동반매도요구권",
        "풋옵션",
        "콜옵션",
        "이사지명권",
        "동의사항",
        "정보접근권",
        "배당정책",
        "교착해소",
    ),
    "MOU": ("구속력", "배타적협상"),
    "ATA/BTA": ("임직원승계", "승계자산부채", "계약이전동의"),
    "JVA": ("주식양도제한", "이사지명권", "동의사항", "교착해소", "출자의무"),
    "공동투자": ("주식양도제한", "이사지명권", "동의사항", "출자의무"),
    "CB인수": ("전환가액조정", "전환청구", "조기상환", "기한이익상실", "담보", "재무약정"),
    "BW인수": ("전환가액조정", "전환청구", "조기상환", "기한이익상실", "담보", "재무약정"),
    "EB인수": ("전환가액조정", "전환청구", "조기상환", "기한이익상실"),
    "분할합병": ("비율산정", "채권자보호", "주식매수청구권", "승계자산"),
    "주식교환": ("비율산정", "주식매수청구권"),
}

NUMERIC_NORMALIZED_FIELDS = {
    "cap_pct_of_price",
    "cap_amount",
    "basket_amount",
    "de_minimis_amount",
    "survival_months",
    "break_fee_amount",
}


class T3SchemaError(ValueError):
    pass


def required_clause_tags(ctype: str) -> List[str]:
    tags: List[str] = list(COMMON_REQUIRED_TAGS)
    specific: Sequence[str] = TYPE_REQUIRED_TAGS.get(ctype, ())
    if not specific:
        for prefix in ("CB", "BW", "EB"):
            if ctype.startswith(prefix):
                specific = TYPE_REQUIRED_TAGS.get(prefix + "인수", ())
                break
    for tag in specific:
        if tag not in tags:
            tags.append(tag)
    return tags


def _require_object(value: object, path: str) -> Dict[str, object]:
    if not isinstance(value, dict):
        raise T3SchemaError("%s must be an object" % path)
    return value


def _require_list(value: object, path: str) -> List[object]:
    if not isinstance(value, list):
        raise T3SchemaError("%s must be an array" % path)
    return value


def _confidence(value: object, path: str) -> None:
    if value not in CONFIDENCE_VALUES:
        raise T3SchemaError("%s must be low, med, or high" % path)


def _location(item: Dict[str, object], path: str, required: bool) -> None:
    start = item.get("loc_start")
    end = item.get("loc_end")
    if required and (start is None or end is None):
        raise T3SchemaError("%s requires loc_start and loc_end" % path)
    for key, value in (("loc_start", start), ("loc_end", end)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
            raise T3SchemaError("%s.%s must be a positive integer or null" % (path, key))
    if start is not None and end is not None and start > end:
        raise T3SchemaError("%s location range is reversed" % path)


def _evaluated_section(value: object, path: str) -> Dict[str, object]:
    section = _require_object(value, path)
    if not isinstance(section.get("evaluated"), bool):
        raise T3SchemaError("%s.evaluated must be boolean" % path)
    _confidence(section.get("confidence"), path + ".confidence")
    reason = section.get("confidence_reason")
    if reason is not None and not isinstance(reason, str):
        raise T3SchemaError("%s.confidence_reason must be string or null" % path)
    return section


def _validate_parties(value: object) -> None:
    section = _evaluated_section(value, "parties_json")
    items = _require_list(section.get("items"), "parties_json.items")
    if section["evaluated"] and not items and not section.get("confidence_reason"):
        raise T3SchemaError("parties_json needs items or a reason why none were confirmed")
    for index, raw in enumerate(items):
        path = "parties_json.items[%d]" % index
        item = _require_object(raw, path)
        if not isinstance(item.get("name"), str) or not str(item["name"]).strip():
            raise T3SchemaError(path + ".name must be a non-empty string")
        if not isinstance(item.get("role"), str) or not str(item["role"]).strip():
            raise T3SchemaError(path + ".role must be a non-empty string")
        _location(item, path, required=True)
        _confidence(item.get("confidence"), path + ".confidence")


def _validate_consideration(value: object) -> None:
    section = _evaluated_section(value, "consideration_json")
    _location(section, "consideration_json", required=False)
    methods = _require_list(section.get("payment_methods"), "consideration_json.payment_methods")
    if not all(isinstance(item, str) and item.strip() for item in methods):
        raise T3SchemaError("consideration_json.payment_methods must contain non-empty strings")
    amount = section.get("amount_value")
    if amount is not None and (isinstance(amount, bool) or not isinstance(amount, (int, float))):
        raise T3SchemaError("consideration_json.amount_value must be numeric or null")
    earnout = section.get("has_earnout")
    if earnout is not None and not isinstance(earnout, bool):
        raise T3SchemaError("consideration_json.has_earnout must be boolean or null")


def _validate_definitions(value: object) -> None:
    section = _evaluated_section(value, "definitions_json")
    items = _require_list(section.get("items"), "definitions_json.items")
    for index, raw in enumerate(items):
        path = "definitions_json.items[%d]" % index
        item = _require_object(raw, path)
        if not isinstance(item.get("term"), str) or not str(item["term"]).strip():
            raise T3SchemaError(path + ".term must be a non-empty string")
        if not isinstance(item.get("gist"), str) or not str(item["gist"]).strip():
            raise T3SchemaError(path + ".gist must be a non-empty string")
        _location(item, path, required=True)
        _confidence(item.get("confidence"), path + ".confidence")


def _validate_normalized(value: object, path: str) -> None:
    normalized = _require_object(value, path)
    for key, item in normalized.items():
        if key in NUMERIC_NORMALIZED_FIELDS and item is not None:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise T3SchemaError("%s.%s must be numeric or null" % (path, key))
        if key.endswith("_months") and item is not None:
            if isinstance(item, bool) or not isinstance(item, int) or item < 0:
                raise T3SchemaError("%s.%s must be a non-negative integer or null" % (path, key))


def _validate_clause_map(value: object, ctype: str) -> None:
    clause_map = _require_object(value, "clause_map_json")
    missing = [tag for tag in required_clause_tags(ctype) if tag not in clause_map]
    if missing:
        raise T3SchemaError("clause_map_json missing evaluated tags: %s" % ", ".join(missing))
    for tag, raw in clause_map.items():
        path = "clause_map_json[%s]" % tag
        item = _require_object(raw, path)
        if not isinstance(item.get("present"), bool):
            raise T3SchemaError(path + ".present must be boolean")
        present = bool(item["present"])
        _location(item, path, required=present)
        _confidence(item.get("confidence"), path + ".confidence")
        reason = item.get("confidence_reason")
        if reason is not None and not isinstance(reason, str):
            raise T3SchemaError(path + ".confidence_reason must be string or null")
        if present:
            for key in ("summary", "verbatim"):
                if not isinstance(item.get(key), str) or not str(item[key]).strip():
                    raise T3SchemaError("%s.%s must be a non-empty string" % (path, key))
        elif item.get("loc_start") is not None or item.get("loc_end") is not None:
            raise T3SchemaError(path + " absent clause must not have a location")
        _validate_normalized(item.get("normalized"), path + ".normalized")


def validate_v3_result(data: Dict[str, object], *, file_key: str, ctype: str) -> Dict[str, object]:
    required = (
        "file_key",
        "meta_schema_version",
        "document_status",
        "parties_json",
        "deal_type_detail",
        "consideration_json",
        "clause_map_json",
        "special_notes",
        "definitions_json",
        "confidence",
        "confidence_reason",
    )
    for key in required:
        if key not in data:
            raise T3SchemaError("missing result key: %s" % key)
    if data["file_key"] != file_key:
        raise T3SchemaError("result file_key does not match candidate")
    if data["meta_schema_version"] != V3_SCHEMA_VERSION:
        raise T3SchemaError("meta_schema_version must be 3")
    if data["document_status"] not in DOCUMENT_STATUS_VALUES:
        raise T3SchemaError("document_status must be contract, not_contract, or insufficient_text")
    if data["deal_type_detail"] is not None and not isinstance(data["deal_type_detail"], str):
        raise T3SchemaError("deal_type_detail must be string or null")
    _confidence(data["confidence"], "confidence")
    reason = data["confidence_reason"]
    if reason is not None and not isinstance(reason, str):
        raise T3SchemaError("confidence_reason must be string or null")
    notes = _require_list(data["special_notes"], "special_notes")
    if not all(isinstance(item, str) and item.strip() for item in notes):
        raise T3SchemaError("special_notes must contain non-empty strings")
    if data["document_status"] != "contract":
        if not data["confidence_reason"]:
            raise T3SchemaError("non-contract or insufficient text requires confidence_reason")
        if not isinstance(data["parties_json"], dict) or data["parties_json"].get("evaluated") is not False:
            raise T3SchemaError("non-contract parties_json.evaluated must be false")
        if not isinstance(data["consideration_json"], dict) or data["consideration_json"].get("evaluated") is not False:
            raise T3SchemaError("non-contract consideration_json.evaluated must be false")
        if not isinstance(data["definitions_json"], dict) or data["definitions_json"].get("evaluated") is not False:
            raise T3SchemaError("non-contract definitions_json.evaluated must be false")
        if data["clause_map_json"] != {}:
            raise T3SchemaError("non-contract clause_map_json must be empty")
        return data
    _validate_parties(data["parties_json"])
    _validate_consideration(data["consideration_json"])
    _validate_definitions(data["definitions_json"])
    _validate_clause_map(data["clause_map_json"], ctype)
    return data

import re
import unicodedata


_ZERO_WIDTH_CHARS = {
    "\u00ad",
    "\u200b",
    "\u200c",
    "\u200d",
    "\u2060",
    "\ufeff",
}


def normalize(text: str) -> str:
    """Normalize text for deterministic indexing and search."""
    if text is None:
        return ""

    text = unicodedata.normalize("NFC", text)

    text = text.translate(_FULLWIDTH_TRANSLATION_TABLE)

    for ch in _ZERO_WIDTH_CHARS:
        text = text.replace(ch, "")

    for old, new in _HYPHEN_REPLACEMENTS:
        text = text.replace(old, new)

    for old, new in _QUOTE_REPLACEMENTS:
        text = text.replace(old, new)

    text = re.sub(r"[\u0000-\u001F\u007F]", " ", text)
    text = re.sub(r"[\t\n\r\f\v]+", " ", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


_FULLWIDTH_TRANSLATION_TABLE = {
    ord("Ａ"): ord("A"),
    ord("Ｂ"): ord("B"),
    ord("Ｃ"): ord("C"),
    ord("Ｄ"): ord("D"),
    ord("Ｅ"): ord("E"),
    ord("Ｆ"): ord("F"),
    ord("Ｇ"): ord("G"),
    ord("Ｈ"): ord("H"),
    ord("Ｉ"): ord("I"),
    ord("Ｊ"): ord("J"),
    ord("Ｋ"): ord("K"),
    ord("Ｌ"): ord("L"),
    ord("Ｍ"): ord("M"),
    ord("Ｎ"): ord("N"),
    ord("Ｏ"): ord("O"),
    ord("Ｐ"): ord("P"),
    ord("Ｑ"): ord("Q"),
    ord("Ｒ"): ord("R"),
    ord("Ｓ"): ord("S"),
    ord("Ｔ"): ord("T"),
    ord("Ｕ"): ord("U"),
    ord("Ｖ"): ord("V"),
    ord("Ｗ"): ord("W"),
    ord("Ｘ"): ord("X"),
    ord("Ｙ"): ord("Y"),
    ord("Ｚ"): ord("Z"),
    ord("ａ"): ord("a"),
    ord("ｂ"): ord("b"),
    ord("ｃ"): ord("c"),
    ord("ｄ"): ord("d"),
    ord("ｅ"): ord("e"),
    ord("ｆ"): ord("f"),
    ord("ｇ"): ord("g"),
    ord("ｈ"): ord("h"),
    ord("ｉ"): ord("i"),
    ord("ｊ"): ord("j"),
    ord("ｋ"): ord("k"),
    ord("ｌ"): ord("l"),
    ord("ｍ"): ord("m"),
    ord("ｎ"): ord("n"),
    ord("ｏ"): ord("o"),
    ord("ｐ"): ord("p"),
    ord("ｑ"): ord("q"),
    ord("ｒ"): ord("r"),
    ord("ｓ"): ord("s"),
    ord("ｔ"): ord("t"),
    ord("ｕ"): ord("u"),
    ord("ｖ"): ord("v"),
    ord("ｗ"): ord("w"),
    ord("ｘ"): ord("x"),
    ord("ｙ"): ord("y"),
    ord("ｚ"): ord("z"),
    ord("０"): ord("0"),
    ord("１"): ord("1"),
    ord("２"): ord("2"),
    ord("３"): ord("3"),
    ord("４"): ord("4"),
    ord("５"): ord("5"),
    ord("６"): ord("6"),
    ord("７"): ord("7"),
    ord("８"): ord("8"),
    ord("９"): ord("9"),
    ord("！"): ord("!"),
    ord("＂"): ord('"'),
    ord("＃"): ord("#"),
    ord("＄"): ord("$"),
    ord("％"): ord("%"),
    ord("＆"): ord("&"),
    ord("＇"): ord("'"),
    ord("（"): ord("("),
    ord("）"): ord(")"),
    ord("＊"): ord("*"),
    ord("＋"): ord("+"),
    ord("，"): ord(","),
    ord("－"): ord("-"),
    ord("．"): ord("."),
    ord("／"): ord("/"),
    ord("："): ord(":"),
    ord("；"): ord(";"),
    ord("＜"): ord("<"),
    ord("＝"): ord("="),
    ord("＞"): ord(">"),
    ord("？"): ord("?"),
    ord("＠"): ord("@"),
    ord("［"): ord("["),
    ord("＼"): ord("\\"),
    ord("］"): ord("]"),
    ord("＾"): ord("^"),
    ord("＿"): ord("_"),
    ord("｀"): ord("`"),
    ord("｛"): ord("{"),
    ord("｜"): ord("|"),
    ord("｝"): ord("}"),
    ord("～"): ord("~"),
    ord("　"): ord(" "),
}

_FULLWIDTH_TRANSLATION_TABLE = {k: v for k, v in _FULLWIDTH_TRANSLATION_TABLE.items()}

_HYPHEN_REPLACEMENTS = [
    ("\u2010", "-"),
    ("\u2011", "-"),
    ("\u2012", "-"),
    ("\u2013", "-"),
    ("\u2014", "-"),
    ("\u2212", "-"),
    ("\uFE58", "-"),
    ("\uFE63", "-"),
    ("\uFF0D", "-"),
]

_QUOTE_REPLACEMENTS = [
    ("\u2018", "'"),
    ("\u2019", "'"),
    ("\u201b", "'"),
    ("\u201c", '"'),
    ("\u201d", '"'),
    ("\u201f", '"'),
    ("\u2039", "'"),
    ("\u203a", "'"),
    ("\u00ab", '"'),
    ("\u00bb", '"'),
    ("\u301d", '"'),
    ("\u301e", '"'),
    ("\u301f", '"'),
    ("\uFF07", "'"),
    ("\uFF02", '"'),
]

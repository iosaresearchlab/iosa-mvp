"""X's weighted text length, as twitter-text v3 counts it (FIX-1f, 20/10/2026).

Twice on 19/10 the prepared X text was over 280 and the Post button stayed
disabled: the preparation counted characters itself. X counts with
twitter-text, config v3 (`config/v3.json`, ported below):

- the text is NFC-normalised;
- every URL, with or without protocol, and every bare domain on a valid TLD
  (`iosaresearch.org`, `youtu.be/x`) counts 23;
- an emoji, however many code points it is made of (skin tones, ZWJ
  families, flags, keycaps), counts 2;
- any other code point counts 1 in the ranges of the config (Latin, Greek,
  Cyrillic, most scripts up to U+10FF, some punctuation), 2 everywhere else
  (CJK, Hangul, most symbols).

    python social/xtext.py "text"        # prints the weighted length

Held by social/tests/test_xtext.py against the official conformance cases
(twitter-text conformance/validate.yml, v3 = WeightedTweetsWithDiscountedEmojiCounterTest).
"""
import re
import sys
import unicodedata

try:
    from social.xtext_tlds import COUNTRY, GENERIC
except ImportError:                                   # run as a script from social/
    from xtext_tlds import COUNTRY, GENERIC

# twitter-text config/v3.json
CONFIG = {
    "version": 3, "maxWeightedTweetLength": 280, "scale": 100, "defaultWeight": 200,
    "emojiParsingEnabled": True, "transformedURLLength": 23,
    "ranges": [(0, 4351, 100), (8192, 8205, 100), (8208, 8223, 100), (8242, 8247, 100)],
}
MAX = CONFIG["maxWeightedTweetLength"]
INVALID_CHARS = {0xFFFE, 0xFEFF, 0xFFFF}

# ---------- URLs ----------
_TLDS = sorted(set(GENERIC) | set(COUNTRY), key=len, reverse=True)
_TLD = "(?:" + "|".join(re.escape(t) for t in _TLDS) + ")"
_INVALID_PRECEDING = r"A-Za-z0-9@＠$#＃\-_."           # a domain never starts after these
_LATIN = r"\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u024F"
_SUB = rf"[a-z0-9{_LATIN}](?:[a-z0-9{_LATIN}_\-]*[a-z0-9{_LATIN}])?"      # subdomain: underscores allowed
_NAME = rf"[a-z0-9{_LATIN}](?:[a-z0-9{_LATIN}\-]*[a-z0-9{_LATIN}])?"      # domain name: no underscore
_ASCII_DOMAIN = rf"(?:{_SUB}\.)*{_NAME}\.{_TLD}"
_UNI = r"[^\W_]"                                       # a letter or digit, any script
_UNI_SUB = rf"{_UNI}(?:[\w\-]*{_UNI})?"
_UNI_NAME = rf"{_UNI}(?:(?:{_UNI}|-)*{_UNI})?"
_UNI_DOMAIN = rf"(?:{_UNI_SUB}\.)*{_UNI_NAME}\.{_TLD}"
_AFTER_TLD = r"(?![A-Za-z0-9@_+\-])"
_PATH_CHARS = r"a-z0-9\u00C0-\u024F\u0400-\u04FF!*';:=+,.$/%#\[\]\-\u2013_~&|@"
_PATH_END = r"a-z0-9\u00C0-\u024F\u0400-\u04FF=_#/+\-"
_PAREN = rf"\([{_PATH_CHARS}]*\)"
_PATH = rf"/(?:(?:[{_PATH_CHARS}]|{_PAREN})*(?:[{_PATH_END}]|{_PAREN}))?"
_QUERY = r"\?(?:[a-z0-9!?*'@();:&=+$/%#\[\]\-_.,~|]*[a-z0-9\-_&=#/])?"
_TAIL = rf"(?::\d+)?(?:{_PATH})?(?:{_QUERY})?"
_TCO = re.compile(r"^https?://t\.co/([a-z0-9]+)", re.IGNORECASE)
_URL = re.compile(
    rf"(?<![{_INVALID_PRECEDING}])"
    rf"(?:(?P<proto>https?://){_UNI_DOMAIN}|{_ASCII_DOMAIN}){_AFTER_TLD}{_TAIL}",
    re.IGNORECASE,
)


def _host_ok(url: str) -> bool:
    """Every label of the host fits DNS: 63 characters, punycode-encoded."""
    host = re.sub(r"^https?://", "", url, flags=re.I)
    host = re.split(r"[/?:]", host, maxsplit=1)[0]
    for label in host.split("."):
        if not label:
            return False
        if label.isascii():
            if len(label) > 63:
                return False
        elif label.lower().startswith("xn--"):
            return False
        else:
            try:
                enc = "xn--" + label.encode("punycode").decode("ascii")
            except UnicodeError:
                return False
            if len(enc) > 63:
                return False
    return True


def urls(text: str):
    """[(start, end)] of the URLs X shortens to 23, in an NFC text."""
    out = []
    for m in _URL.finditer(text):
        s, e = m.span()
        frag = text[s:e]
        if not m.group("proto") and text[:s].endswith("://"):
            continue                                       # the rest of a URL already refused

        if text[e:e + 1] == "@":                           # an e-mail address, not a URL
            continue
        tco = _TCO.match(frag)
        if tco:                                            # t.co: the slug only, at most 40
            if len(tco.group(1)) > 40:
                continue
            e = s + tco.end()
        if _host_ok(frag):
            out.append((s, e))
    return out


# ---------- emoji ----------
def _pictographic(c: int) -> bool:
    return (0x1F000 <= c <= 0x1FAFF or 0x2600 <= c <= 0x27BF or 0x2300 <= c <= 0x23FF
            or 0x2B00 <= c <= 0x2BFF or 0x2190 <= c <= 0x21FF or 0x25A0 <= c <= 0x25FF
            or c in (0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x24C2, 0x2934, 0x2935,
                     0x3030, 0x303D, 0x3297, 0x3299))


_KEYCAP_BASE = set("0123456789#*")


def _emoji_end(t: str, i: int) -> int:
    """End of the emoji sequence starting at i, or i when there is none."""
    n = len(t)
    c = ord(t[i])
    if t[i] in _KEYCAP_BASE:                                # 1⃣ 1️⃣
        j = i + 1
        if j < n and t[j] == "️":
            j += 1
        return j + 1 if j < n and t[j] == "⃣" else i
    if 0x1F1E6 <= c <= 0x1F1FF:                             # flags: a pair of regional indicators
        if i + 1 < n and 0x1F1E6 <= ord(t[i + 1]) <= 0x1F1FF:
            return i + 2
        return i + 1
    if not _pictographic(c):
        return i
    j = i + 1
    while j < n:
        d = ord(t[j])
        if d == 0xFE0F or 0x1F3FB <= d <= 0x1F3FF or 0xE0020 <= d <= 0xE007F:
            j += 1                                          # presentation, skin tone, tag sequence
        elif d == 0x200D and j + 1 < n and _pictographic(ord(t[j + 1])):
            j += 2                                          # ZWJ sequence
        else:
            break
    return j


# ---------- length ----------
def _weight(c: int) -> int:
    for lo, hi, w in CONFIG["ranges"]:
        if lo <= c <= hi:
            return w
    return CONFIG["defaultWeight"]


def parse(text: str) -> dict:
    """weightedLength and valid, as twitter-text's parseTweet reports them."""
    t = unicodedata.normalize("NFC", text or "")
    spans = dict(urls(t))
    scale = CONFIG["scale"]
    total = 0
    invalid = False
    i = 0
    while i < len(t):
        if i in spans:
            total += CONFIG["transformedURLLength"] * scale
            i = spans[i]
            continue
        j = _emoji_end(t, i) if CONFIG["emojiParsingEnabled"] else i
        if j > i:
            total += CONFIG["defaultWeight"]
            i = j
            continue
        c = ord(t[i])
        invalid = invalid or c in INVALID_CHARS
        total += _weight(c)
        i += 1
    length = total // scale
    return {"weightedLength": length, "valid": not invalid and 0 < length <= MAX}


def weighted_length(text: str) -> int:
    return parse(text)["weightedLength"]


if __name__ == "__main__":
    print(weighted_length(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()))

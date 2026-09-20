import re
import json
import unicodedata
from pathlib import Path

_KEY_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="


class SceneError(ValueError):
    """The file is not an excalidraw scene with compressed JSON."""


def _decompress(length, reset_value, get_next_value):
    dictionary = {0: 0, 1: 1, 2: 2}
    enlarge_in = 4
    dict_size = 4
    num_bits = 3
    result = []
    data_val = get_next_value(0)
    data_position = reset_value
    data_index = 1

    def read_bits(nbits):
        nonlocal data_val, data_position, data_index
        bits = 0
        power = 1
        maxpower = 1 << nbits
        while power != maxpower:
            resb = data_val & data_position
            data_position >>= 1
            if data_position == 0:
                data_position = reset_value
                data_val = get_next_value(data_index)
                data_index += 1
            bits |= (1 if resb > 0 else 0) * power
            power <<= 1
        return bits

    c_type = read_bits(2)
    if c_type == 0:
        c = chr(read_bits(8))
    elif c_type == 1:
        c = chr(read_bits(16))
    else:
        return ""
    dictionary[3] = c
    w = c
    result.append(c)

    while True:
        if data_index > length:
            return ""
        c_code = read_bits(num_bits)
        if c_code == 0:
            dictionary[dict_size] = chr(read_bits(8))
            dict_size += 1
            c_code = dict_size - 1
            enlarge_in -= 1
        elif c_code == 1:
            dictionary[dict_size] = chr(read_bits(16))
            dict_size += 1
            c_code = dict_size - 1
            enlarge_in -= 1
        elif c_code == 2:
            return "".join(result)
        if enlarge_in == 0:
            enlarge_in = 1 << num_bits
            num_bits += 1
        if c_code in dictionary:
            entry = dictionary[c_code]
        elif c_code == dict_size:
            entry = w + w[0]
        else:
            return "".join(result)
        result.append(entry)
        dictionary[dict_size] = w + entry[0]
        dict_size += 1
        enlarge_in -= 1
        w = entry
        if enlarge_in == 0:
            enlarge_in = 1 << num_bits
            num_bits += 1


def decompress_from_base64(inp):
    if not inp:
        return None
    index = {c: i for i, c in enumerate(_KEY_B64)}
    n = len(inp)
    return _decompress(n, 32, lambda i: (index.get(inp[i], 0) if i < n else 0))


def strip_emoji(s: str) -> str:
    out = []
    for ch in s:
        if ch in "\n\t":
            out.append(ch)
            continue
        code = ord(ch)
        if 0xD800 <= code <= 0xDFFF:
            continue
        if unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co"):
            continue
        if (0x1F000 <= code <= 0x1FAFF
                or 0x1F1E6 <= code <= 0x1F1FF
                or code in (0x200D, 0x20E3, 0xFE0F)):
            continue
        out.append(ch)
    return "".join(out)


def clean(s: str) -> str:
    return s.encode("utf-8", "replace").decode("utf-8")


def load_cases(path):
    path = Path(path)
    md = path.read_text(encoding="utf-8")
    m = re.search(r"```compressed-json\s*\n(.*?)\n```", md, re.S)
    if not m:
        raise SceneError(f"compressed-json block not found: {path}")
    raw = re.sub(r"\s+", "", m.group(1))
    text = decompress_from_base64(raw)
    if not text or "{" not in text:
        raise SceneError(f"could not decompress scene: {path}")
    scene = json.loads(clean(text[text.index("{"):]))
    elements = scene.get("elements", [])
    rects = {e["id"]: e for e in elements
             if e.get("type") == "rectangle" and not e.get("isDeleted")}
    cases = []
    for t in elements:
        if t.get("type") != "text" or t.get("isDeleted"):
            continue
        txt = strip_emoji(t.get("originalText") or t.get("text") or "").strip()
        if not txt:
            continue
        r = rects.get(t.get("containerId"))
        x = round((r or t).get("x", 0))
        y = round((r or t).get("y", 0))
        cases.append({"text": txt, "x": x, "y": y, "source": path.name})
    cases.sort(key=lambda c: (round(c["y"] / 40), c["x"]))
    return _reindex(cases)


def load_path(path):
    path = Path(path)
    if path.is_dir():
        cases = []
        for md in sorted(path.rglob("*.md")):
            try:
                cases.extend(load_cases(md))
            except SceneError:
                continue
        return _reindex(cases)
    return load_cases(path)


def _reindex(cases):
    for i, c in enumerate(cases, 1):
        c["id"] = i
    return cases

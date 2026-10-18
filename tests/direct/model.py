"""Model-answer builders + image fixtures for Pavvl Direct Mode tests.

Mirrors the proven Direct Mode harness idioms against the real v0.2.16 SDK:
- `look` / `look_by`: examination answers (per prompt position or per image tag)
- `crit` / `judge`: criterion judgments (model names items relative to the
  criterion: supports/against; NOT_ESTABLISHED swaps basis/contrary)
- `jpeg` / `png`: synthetic images with the structure the contract validates
"""

import zlib


def jpeg_segment(marker: int, body: bytes) -> bytes:
    return b"\xff" + bytes([marker]) + (len(body) + 2).to_bytes(2, "big") + body


def jpeg(tag: str = "a", size: int = 2000, width: int = 640, height: int = 480,
         extra: bytes = b"", tail: bytes = b"\xff\xd9") -> bytes:
    """A JPEG with the structure a decoder needs up to its first scan (JFIF
    header, a quantization table, a baseline frame, a Huffman table, the scan
    header), then `size` bytes carrying the tag in place of a real scan.
    `extra` goes between the header and the tables: a metadata segment, say."""
    head = (b"\xff\xd8" + jpeg_segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00") + extra
            + jpeg_segment(0xDB, b"\x00" + bytes(range(1, 65)))
            + jpeg_segment(0xC0, b"\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00")
            + jpeg_segment(0xC4, b"\x00" + bytes(16))
            + jpeg_segment(0xDA, b"\x01\x01\x00\x00\x3f\x00"))
    body = (tag.encode() * (size // max(1, len(tag)) + 1))[:size]
    return head + body + tail


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return len(data).to_bytes(4, "big") + kind + data + zlib.crc32(kind + data).to_bytes(4, "big")


def png(tag: str = "p", size: int = 600, width: int = 640, height: int = 480,
        extra: bytes = b"", tail: bytes = b"") -> bytes:
    """A PNG with a real header, one data chunk carrying the tag, and an end."""
    header = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([8, 2, 0, 0, 0])
    return (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header) + extra
            + png_chunk(b"IDAT", (tag.encode() * size)[:size]) + png_chunk(b"IEND", b"") + tail)


def read_canary(data: bytes) -> str:
    """Read the calibration PNG the way an honest sighted model does: decode
    the PNG (checking every chunk's CRC and the zlib stream) and match the
    dot-matrix digits. Also proves the contract's hand-written PNG is valid."""
    from gltest.direct.sdk_loader import setup_sdk_paths

    from tests.direct.conftest import CONTRACT_PATH

    setup_sdk_paths(CONTRACT_PATH, "v0.2.16")
    import genlayer.gl as gl  # noqa: F401  (ensures SDK importable)

    # Font duplicated from the contract (kept in sync by test_canary_roundtrip).
    src = CONTRACT_PATH.read_text()
    assert "_FONT" in src
    font = {
        "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
        "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
        "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
        "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
        "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
        "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
        "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
        "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
        "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
        "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    }
    cell = 10
    assert data[:8] == bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]), "not a PNG"
    pos, idat, width = 8, b"", 0
    while pos < len(data):
        size = int.from_bytes(data[pos:pos + 4], "big")
        tag_b, chunk = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + size]
        assert zlib.crc32(tag_b + chunk) == int.from_bytes(data[pos + 8 + size:pos + 12 + size], "big"), "bad crc"
        if tag_b == b"IHDR":
            width = int.from_bytes(chunk[:4], "big")
        if tag_b == b"IDAT":
            idat += chunk
        pos += 12 + size
    raw = zlib.decompress(idat)
    stride = width + 1
    out = ""
    for d in range(6):
        x0 = (2 + d * 6) * cell
        rows = tuple("".join("1" if raw[((2 + r) * cell + cell // 2) * stride + 1 + x0 + c * cell + cell // 2] < 128
                             else "0" for c in range(5)) for r in range(7))
        out += next(k for k, v in font.items() if v == rows)
    return out


# ---- model answers ---------------------------------------------------------------

def look(seen=True, shows="cartons stacked on pallets in a warehouse", text=None,
         dates=None, doubts="", quality="GOOD"):
    """An examination answer for whatever images the prompt carries."""

    def answer(prompt, images):
        n = len(images or [])
        rows = []
        for _i in range(1, n + 1):
            rows.append({"n": _i, "seen": seen, "shows": shows if seen else "",
                         "text": text or [], "dates": dates or [],
                         "subject_doubts": doubts, "quality": quality})
        return {"images": rows}

    return answer


def look_by(mapping, default=None):
    """Per-image examination keyed by the tag inside each image's bytes."""

    def answer(prompt, images):
        rows = []
        for i, img in enumerate(images or [], start=1):
            blob = bytes(img)
            tag = next((k for k in mapping if k.encode() in blob), None)
            spec = mapping[tag] if tag else (default or {"seen": True, "shows": "cartons on pallets"})
            rows.append({"n": i, "seen": spec.get("seen", True), "shows": spec.get("shows", ""),
                         "text": spec.get("text", []), "dates": spec.get("dates", []),
                         "subject_doubts": spec.get("subject_doubts", ""),
                         "quality": spec.get("quality", "GOOD")})
        return {"images": rows}

    return answer


def crit(cid, finding, basis=(), contrary=(), adequate=True, missing=(), rationale="reasons"):
    """One criterion of a model's answer. Tests say what the finding rests on
    (basis) and what opposes it (contrary); the model names items relative to
    the criterion (supports, against), so NOT_ESTABLISHED swaps the two."""
    rests, opposes = list(basis), list(contrary)
    supports, against = (opposes, rests) if finding == "NOT_ESTABLISHED" else (rests, opposes)
    return {"id": cid, "rationale": rationale, "supports": supports, "against": against,
            "evidence_adequate": adequate, "finding": finding, "missing": list(missing)}


def judge(*rows, instructions=(), limitations=("capture times are not independently verified",)):
    return {"criteria": list(rows), "limitations": list(limitations),
            "instructions_found": list(instructions)}

"""Text normalisation and script analysis for Nepali (Devanagari) evaluation.

The normaliser removes differences that are *representational* rather than
linguistic, so a model is not penalised for them:

* Unicode composition (NFC), e.g. decomposed vs. precomposed nukta letters
* zero-width joiner / non-joiner characters
* Devanagari digits vs. ASCII digits
* the danda (U+0964) vs. a full stop
* case of Latin letters and runs of whitespace

It deliberately does NOT merge genuine spelling variants (for example chandrabindu
vs. anusvara, or short vs. long vowels); those can be listed as separate acceptable
references in a task instead, so the decision stays visible and reviewable.
"""

from __future__ import annotations

import re
import unicodedata

ZERO_WIDTH = {"‌", "‍", "​", "﻿"}
DEVANAGARI_DIGITS = {ord("०") + i: str(i) for i in range(10)}
_PUNCT_MAP = {ord("।"): ".", ord("॥"): "."}
_WS = re.compile(r"\s+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def is_devanagari(ch: str) -> bool:
    return "ऀ" <= ch <= "ॿ"


def normalize_text(text: str, *, strip_punct: bool = False) -> str:
    """Return ``text`` with representational differences removed (see module doc)."""
    text = unicodedata.normalize("NFC", text)
    text = "".join(c for c in text if c not in ZERO_WIDTH)
    text = text.translate(DEVANAGARI_DIGITS).translate(_PUNCT_MAP)
    text = text.casefold()
    if strip_punct:
        text = "".join(c for c in text if not unicodedata.category(c).startswith("P"))
    return _WS.sub(" ", text).strip()


def extract_numbers(text: str) -> list[str]:
    """Numbers in ``text`` as ASCII strings, with thousands separators removed."""
    text = text.translate(DEVANAGARI_DIGITS)
    return [m.replace(",", "") for m in _NUMBER.findall(text)]


def script_stats(text: str) -> dict[str, float]:
    """Share of letters by script (digits/punctuation/space ignored)."""
    dev = lat = other = 0
    for ch in text:
        is_mark = is_devanagari(ch) and unicodedata.category(ch).startswith("M")
        if not ch.isalpha() and not is_mark:
            continue
        if is_devanagari(ch):
            dev += 1
        elif ch.isascii():
            lat += 1
        else:
            other += 1
    total = dev + lat + other
    if total == 0:
        return {"devanagari": 0.0, "latin": 0.0, "other": 0.0, "letters": 0}
    return {
        "devanagari": dev / total,
        "latin": lat / total,
        "other": other / total,
        "letters": total,
    }


def classify_script(text: str, *, threshold: float = 0.9) -> str:
    """Coarse label: ``devanagari``, ``latin``, ``mixed``, ``other`` or ``empty``.

    ``latin`` cannot distinguish English from Romanised Nepali; that needs a language
    model or human judgement and is out of scope for this function.
    """
    s = script_stats(text)
    if s["letters"] == 0:
        return "empty"
    if s["devanagari"] >= threshold:
        return "devanagari"
    if s["latin"] >= threshold:
        return "latin"
    if s["other"] >= threshold:
        return "other"
    return "mixed"

"""Automated, heuristic lint for task files.

IMPORTANT: these checks catch mechanical problems (script mix, punctuation, zero-width characters,
duplicate references, phone-number-like digits, informal-register markers). They do NOT judge whether Nepali
is correct, natural, or culturally appropriate. That needs a human native-speaker review
(see docs/REVIEW_GUIDE.md); a task with zero findings here is still ``unreviewed`` until a person signs it off.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .normalize import DEVANAGARI_DIGITS, ZERO_WIDTH, normalize_text, script_stats
from .tasks import Task

# 10-digit runs that look like a Nepali mobile number (97/98 prefix) must never ship in a public task file.
_PHONE_LIKE = re.compile(r"(?<!\d)9[78]\d{8}(?!\d)")
_INFORMAL = re.compile(r"तिमी|तिम्रो|तिमीलाई|तँ\b|तेरो|\btimi\b|\btimro\b", re.I)
_SENTENCE_END = ("।", "?", "!", "॥")
NEPALI_TARGET_TYPES = ("translation_en_ne", "transliteration")


@dataclass
class Finding:
    task_id: str
    severity: str  # error | warning | info
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.severity.upper():7} {self.task_id}: [{self.code}] {self.message}"


def _digits_ascii(s: str) -> str:
    return s.translate(DEVANAGARI_DIGITS)


def lint_task(t: Task) -> list[Finding]:
    out: list[Finding] = []

    def add(sev: str, code: str, msg: str) -> None:
        out.append(Finding(t.id, sev, code, msg))

    texts = [("prompt", t.prompt)] + [(f"reference {i + 1}", r) for i, r in enumerate(t.references)]
    for where, text in texts:
        if _PHONE_LIKE.search(_digits_ascii(text)):
            add("error", "phone-like", f"{where} contains a 10-digit number starting 97/98 that could be a "
                "real mobile number; use an obviously invalid placeholder")
        if any(c in text for c in ZERO_WIDTH):
            add("warning", "zero-width", f"{where} contains zero-width characters; check they are intended")
        has_dev_digit = any(c in text for c in "०१२३४५६७८९")
        has_asc_digit = any(c.isascii() and c.isdigit() for c in text)
        if has_dev_digit and has_asc_digit:
            add("warning", "mixed-digits", f"{where} mixes Devanagari and ASCII digits")

    nepali_target = t.task_type in NEPALI_TARGET_TYPES or "min_devanagari_ratio" in t.checks
    for i, r in enumerate(t.references, 1):
        s = script_stats(r)
        if nepali_target:
            if s["devanagari"] < 0.8:
                add("warning", "reference-script", f"reference {i} is only {s['devanagari']:.0%} Devanagari "
                    "but the task expects Nepali output")
            stripped = r.strip()
            if stripped.endswith("."):
                add("info", "ascii-full-stop", f"reference {i} ends with '.'; Nepali sentences normally use '।'")
            elif stripped and not stripped.endswith(_SENTENCE_END) and len(stripped.split()) > 2:
                add("info", "no-sentence-end", f"reference {i} has no sentence-ending mark (।/?/!)")
            if " ?" in r or " ।" in r:
                add("info", "space-before-mark", f"reference {i} has a space before the sentence-ending mark")

    seen: dict[str, int] = {}
    for i, r in enumerate(t.references, 1):
        key = normalize_text(r, strip_punct=True)
        if key in seen:
            add("warning", "duplicate-reference", f"reference {i} equals reference {seen[key]} after normalisation")
        seen.setdefault(key, i)
    if t.task_type.startswith("translation") and len(t.references) == 1:
        add("info", "single-reference", "only one reference: valid paraphrases/variants may be scored as wrong")
    if _INFORMAL.search(t.prompt) and not any(tag.startswith("register") or tag == "informal" for tag in t.tags):
        add("info", "register", "informal second-person form (तिमी/तिम्रो/तँ…) without a 'register' or 'informal' tag; "
            "a formal alternative (तपाईं) may also be acceptable")
    if t.review_status == "unreviewed":
        add("info", "unreviewed", "no native-speaker review recorded")
    return out


def lint_tasks(tasks: list[Task]) -> list[Finding]:
    out: list[Finding] = []
    for t in tasks:
        out += lint_task(t)
    return out

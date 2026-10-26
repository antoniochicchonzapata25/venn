"""Deterministic safety checks around the agents. None of these depend on the model behaving well.

1. Untrusted text (food names, notes) is sanitised and marked before it reaches the model.
2. Numeric grounding: every number in an answer must match a number in the tool results
   (or the user's question); otherwise the answer is flagged as unverified.
3. Exercise guard: any catalog exercise named in an answer is re-checked against the user's
   equipment and reported limitations with the same rules the workout generator uses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|messages|rules)",
    r"disregard (all |any |the )?(previous|prior|above) ",
    r"\bsystem prompt\b", r"\byou are now\b", r"\bnew instructions?\b", r"\bact as\b",
    r"\b(call|use|run|invoke) (the )?(tool|function)\b", r"\buser[_ ]?id\b", r"\bother users?\b",
    r"\breveal\b", r"\bapi[_ ]?key\b", r"<\s*/?\s*(system|assistant|tool)\s*>",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
MAX_UNTRUSTED_CHARS = 80


def sanitize_untrusted(text: str | None, limit: int = MAX_UNTRUSTED_CHARS) -> tuple[str, bool]:
    """Return (safe text, flagged). Control characters are removed, length is capped, and text that
    looks like an instruction is replaced so it can't steer the model."""
    if not text:
        return "", False
    clean = "".join(ch for ch in text if ch.isprintable()).strip()
    flagged = bool(_INJECTION_RE.search(clean))
    if flagged:
        return "[text removed: looked like an instruction]", True
    return (clean[:limit] + "…") if len(clean) > limit else clean, False


_NUMBER_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?")


def numbers_in(text: str) -> list[float]:
    out = []
    for m in _NUMBER_RE.finditer(text or ""):
        whole = m.group(1).replace(",", "")
        out.append(float(f"{whole}.{m.group(2)}" if m.group(2) else whole))
    return out


def collect_numbers(obj, acc: set[float] | None = None) -> set[float]:
    """All numbers in tool results, including the parts of dates (2026-10-25 -> 2026, 10, 25)."""
    acc = set() if acc is None else acc
    if isinstance(obj, bool) or obj is None:
        return acc
    if isinstance(obj, (int, float)):
        acc.add(float(obj))
    elif isinstance(obj, str):
        acc.update(numbers_in(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            collect_numbers(v, acc)
    return acc


@dataclass
class Grounding:
    checked: int = 0
    verified: int = 0
    unverified: list[float] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.unverified


def check_numbers(answer: str, facts: set[float], question: str = "") -> Grounding:
    """Every number in the answer must match a tool-result number (or one in the question) to within
    rounding (0.5 absolute or 1% relative). Small counting numbers (0-10) are allowed."""
    allowed = facts | set(numbers_in(question))
    g = Grounding()
    for n in numbers_in(answer):
        g.checked += 1
        if n <= 10 or any(abs(n - f) <= 0.5 or (f and abs(n - f) / abs(f) <= 0.01) for f in allowed):
            g.verified += 1
        else:
            g.unverified.append(n)
    return g


def mentioned_exercises(answer: str, catalog_names: dict[str, str]) -> list[str]:
    """Catalog exercise ids whose full name appears in the answer (case-insensitive)."""
    low = (answer or "").lower()
    return [ex_id for name, ex_id in catalog_names.items() if len(name) > 5 and name in low]

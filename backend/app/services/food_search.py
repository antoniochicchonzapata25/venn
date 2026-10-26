"""Offline food search: an in-memory token index over the bundled catalog, ranked by simple rules.

Every query word must prefix-match a word in the food's name or brand. Matches in the
first part of the name (before the first comma, e.g. "Chicken" in "Chicken, broilers...,
breast") count more; shorter, simpler names rank higher. Two boosts: a curated list of
everyday staples (app/data/staple_foods.json, e.g. "Egg, whole, raw, fresh" rather than
"Egg, whole, dried") and foods the user logged recently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD = re.compile(r"[a-z0-9]+")


def normalize_word(w: str) -> str:
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def words(text: str) -> list[str]:
    return [normalize_word(w) for w in _WORD.findall(text.lower())]


@dataclass(frozen=True)
class IndexedFood:
    id: int
    head: tuple[str, ...]  # words before the first comma
    rest: tuple[str, ...]  # remaining words of the name and the brand
    n_words: int
    head_text: str
    staple: bool = False


STAPLE_BOOST = 7.0
RECENT_BOOST = 4.0


def build_index(rows, staple_names: frozenset[str] = frozenset()) -> list[IndexedFood]:  # noqa: ANN001
    """rows: iterable of (id, name, brand)."""
    index = []
    for fid, name, brand in rows:
        head, _, tail = name.partition(",")
        hw, rw = words(head), words(tail) + words(brand or "")
        index.append(IndexedFood(fid, tuple(hw), tuple(rw), len(hw) + len(words(tail)), " ".join(hw), name in staple_names))
    return index


def _match(q: str, ws: tuple[str, ...]) -> int:
    """2 = exact word match, 1 = prefix match, 0 = no match."""
    best = 0
    for w in ws:
        if w == q:
            return 2
        if w.startswith(q):
            best = 1
    return best


def search(index: list[IndexedFood], query: str, limit: int = 20, boost_ids: frozenset[int] = frozenset()) -> list[int]:
    qs = words(query)
    if not qs:
        return []
    scored = []
    for f in index:
        score = 0.0
        for q in qs:
            head, rest = _match(q, f.head), _match(q, f.rest)
            if not head and not rest:
                break
            score += 3 + head if head else 1 + rest
        else:
            if f.head_text == " ".join(qs):
                score += 2
            if f.head and f.head[0].startswith(qs[0]):
                score += 2
            if f.staple:
                score += STAPLE_BOOST
            if f.id in boost_ids:
                score += RECENT_BOOST
            score -= 0.15 * f.n_words
            scored.append((-score, f.n_words, f.id))
    scored.sort()
    return [fid for _, _, fid in scored[:limit]]

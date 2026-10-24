"""Identity matching for Indian names: "is this probably the same person under another APAAR ID?".

A plain fuzzy ratio is wrong in both directions for Indian records. It calls twins and rhyming
siblings the same person (Rohit/Mohit Sharma score 92), and it misses real variants of one name
(Mohd Irfan / Mohammed Irfan, V S Krishna / Venkata Sai Krishna, Laxmi / Lakshmi). This module
instead aligns names token by token:

* normalisation keeps Indic combining vowel signs (so Devanagari and Tamil names survive),
  drops honorifics (Shri, Smt, Late, Dr) and optional suffixes (Kumar, Kumari, Devi), and maps
  common spellings to one form (Mohd / Md / Muhammad -> mohammed);
* Latin tokens are folded for transliteration (sh->s, x->ks, ee->i, oo->u, w->v, au/ou->o, ai/ei->e,
  doubled letters, a final a or e);
* every token of the shorter name must match a token of the longer one: equal after folding,
  an initial of it, or a one-letter insertion, deletion or swap (a typing slip). A changed letter
  (Rohit / Mohit, Ramesh / Rajesh) never matches, which is what keeps twins apart;
* a parent's name must also match, and dates of birth must be equal or have day and month swapped.

Every decision comes with plain-language reasons. A match is a review item, never a verdict.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

from rapidfuzz import fuzz

HONORIFICS = {"shri", "sri", "shree", "smt", "shrimati", "srimati", "sushri", "kum", "km", "late", "lt", "dr",
              "mr", "mrs", "ms", "miss", "prof", "sh", "thiru", "tmt", "selvi", "md.", "श्री", "श्रीमती", "स्व",
              "स्वर्गीय", "डॉ", "कुमारी", "திரு", "திருமதி"}
OPTIONAL = {"kumar", "kumari", "devi", "bai", "ben", "कुमार", "कुमारी", "देवी"}
CANONICAL = {"mohd": "mohammed", "md": "mohammed", "mohammad": "mohammed", "muhammad": "mohammed",
             "mohamed": "mohammed", "mohammed": "mohammed", "mohamad": "mohammed", "sayyed": "syed",
             "sayed": "syed", "saiyad": "syed"}
_FOLDS = (("ksh", "ks"), ("x", "ks"), ("sh", "s"), ("ph", "f"), ("th", "t"), ("dh", "d"), ("bh", "b"),
          ("kh", "k"), ("gh", "g"), ("jh", "j"), ("ch", "c"), ("ee", "i"), ("oo", "u"), ("au", "o"), ("ou", "o"),
          ("ow", "o"), ("ai", "e"), ("ei", "e"), ("ay", "e"), ("w", "v"), ("z", "j"), ("q", "k"), ("ck", "k"))
VOWELS = set("aeiou")


def tokens(name: str | None) -> list[str]:
    """Normalised name tokens. Single letters are kept as initials."""
    return list(_tokens(name or ""))


@lru_cache(maxsize=200_000)
def _tokens(name: str) -> tuple[str, ...]:
    text = unicodedata.normalize("NFKC", name or "").lower()
    # Keep letters and combining marks (Indic vowel signs are category M); everything else separates.
    text = "".join(c if unicodedata.category(c)[0] in "LM" else " " for c in text)
    out = []
    for t in text.split():
        if t in HONORIFICS:
            continue
        t = CANONICAL.get(t, t)
        if t.isascii() and len(t) == 2 and not (set(t) & VOWELS):
            out.extend(t)  # "VS" -> initials v, s
        else:
            out.append(t)
    return tuple(out)


def norm_name(name: str | None) -> str:
    """Display / blocking form: normalised tokens joined by spaces (initials and optional words kept)."""
    return " ".join(tokens(name))


@lru_cache(maxsize=200_000)
def fold(t: str) -> str:
    if not t.isascii():
        return t
    for a, b in _FOLDS:
        t = t.replace(a, b)
    t = re.sub(r"(.)\1+", r"\1", t)
    if len(t) > 3 and t[-1] in "ae":
        t = t[:-1]
    return t


@lru_cache(maxsize=200_000)
def match_key(name: str | None) -> str:
    """Folded tokens without optional words; used for cheap pre-filtering and exact-key blocking."""
    return " ".join(sorted(fold(t) for t in tokens(name) if t not in OPTIONAL))


def _slip(a: str, b: str) -> bool:
    """One inserted, deleted or swapped letter (a typing slip), never a changed letter."""
    if a[0] != b[0] or min(len(a), len(b)) < 5:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
    if abs(len(a) - len(b)) != 1:
        return False
    s, l = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(s) and s[i] == l[i]:
        i += 1
    return s[i:] == l[i + 1:]


def _tamil_suffix(a: str, b: str) -> bool:
    """Narayan / Narayanan, Murugan / Muruga: the same name with or without the -an ending."""
    s, l = sorted((a, b), key=len)
    return len(s) >= 5 and l in (s + "an", s + "n")


@dataclass
class NameMatch:
    match: bool
    score: int
    reasons: list[str] = field(default_factory=list)


def compare_names(a: str | None, b: str | None) -> NameMatch:
    ta = [t for t in tokens(a) if t not in OPTIONAL]
    tb = [t for t in tokens(b) if t not in OPTIONAL]
    if not ta or not tb:
        return NameMatch(False, 0, ["name missing"])
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    used = [False] * len(long_)
    score, reasons, full_hits = 100, [], 0
    # Full tokens first, so an initial does not consume a token a full word needed.
    for s in sorted(short, key=len, reverse=True):
        hit = None
        for j, l in enumerate(long_):
            if used[j]:
                continue
            if s == l:
                hit = (j, None, len(s) > 1)
            elif len(s) > 1 and len(l) > 1:
                fs, fl = fold(s), fold(l)
                if fs == fl or _tamil_suffix(fs, fl):
                    hit = (j, f"'{s}' and '{l}' are the same name in another spelling", True)
                elif _slip(fs, fl):
                    hit = (j, f"'{s}' and '{l}' differ by one typed letter", True)
            elif s[0] == l[0]:
                hit = (j, f"initial '{s if len(s) == 1 else l}' matches '{l if len(s) == 1 else s}'", False)
            if hit:
                break
        if not hit:
            return NameMatch(False, 0, [f"'{s}' has no counterpart in the other name"])
        j, why, full = hit
        used[j] = True
        full_hits += full
        if why:
            reasons.append(why)
            score -= 4 if "spelling" in why else 6
    if not full_hits:
        return NameMatch(False, 0, ["only initials match"])
    extra = used.count(False)
    if extra > 2:
        return NameMatch(False, 0, [f"{extra} words of the longer name are unmatched"])
    if extra:
        left = [t for t, u in zip(long_, used) if not u]
        initials = [t.upper() for t in left if len(t) == 1]
        words = [t for t in left if len(t) > 1]
        if initials:
            reasons.append(f"initial{'s' * (len(initials) > 1)} {' '.join(i + '.' for i in initials)} in one record only")
        if words:
            reasons.append(f"'{' '.join(words)}' in one record only")
        score -= 3 * len(initials) + 5 * len(words)
    if [fold(t) for t in ta] != [fold(t) for t in tb] and sorted(map(fold, ta)) == sorted(map(fold, tb)):
        reasons.append("same words in a different order")
    return NameMatch(True, max(score, 60), reasons)


def dob_compatible(a: date | None, b: date | None) -> tuple[bool, str | None]:
    if not a or not b:
        return False, None
    if a == b:
        return True, None
    if a.year == b.year and a.day == b.month and a.month == b.day:
        return True, "day and month swapped in one date of birth"
    return False, None


@dataclass
class Person:
    name: str
    dob: date | None
    gender: str
    father_name: str | None = None
    mother_name: str | None = None
    guardian_name: str | None = None


@dataclass
class IdentityMatch:
    match: bool
    score: int
    name_score: int = 0
    parent_score: int = 0
    reasons: list[str] = field(default_factory=list)


PARENTS = (("father_name", "father's name"), ("mother_name", "mother's name"), ("guardian_name", "guardian's name"))


def quick_reject(a: str, b: str) -> bool:
    """Cheap filter before alignment: folded names sharing almost nothing cannot match."""
    return fuzz.token_set_ratio(match_key(a), match_key(b)) < 55


def same_person(a: Person, b: Person) -> IdentityMatch:
    if a.gender != b.gender:
        return IdentityMatch(False, 0, reasons=["different gender"])
    ok, dob_note = dob_compatible(a.dob, b.dob)
    if not ok:
        return IdentityMatch(False, 0, reasons=["different date of birth"])
    nm = compare_names(a.name, b.name)
    if not nm.match:
        return IdentityMatch(False, 0, reasons=[f"name: {nm.reasons[0]}"])
    compared, parent_scores, reasons = 0, [], []
    for attr, label in PARENTS:
        pa, pb = getattr(a, attr), getattr(b, attr)
        if not pa or not pb:
            continue
        compared += 1
        pm = compare_names(pa, pb)
        if not pm.match:
            return IdentityMatch(False, 0, reasons=[f"{label}: {pm.reasons[0]}"])
        parent_scores.append(pm.score)
        reasons += [f"{label}: {r}" for r in pm.reasons]
    if not compared:
        return IdentityMatch(False, 0, reasons=["no parent or guardian name to compare"])
    parent = min(parent_scores)
    reasons = ["same date of birth" if not dob_note else dob_note, *[f"name: {r}" for r in nm.reasons], *reasons]
    score = round(0.6 * nm.score + 0.4 * parent) - (5 if dob_note else 0)
    return IdentityMatch(True, score, nm.score, parent, reasons)

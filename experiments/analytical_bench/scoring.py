"""Deterministic answer scoring for the analytical benchmark.

Five answer kinds:
- "int":    exact integer match (allows tolerance via _abs).
- "float":  match within tolerance (1% relative or 0.01 absolute, whichever
            is larger).
- "string": case-insensitive substring match in either direction (handles
            "Tokyo" vs "Tokyo, Japan"); empty gold matches empty prediction.
- "set":    case-insensitive set equality (after stripping/lowering).
- "list":   ordered list equality (case-insensitive per-element).
"""
from __future__ import annotations

import re
from typing import Any


_INT_RE = re.compile(r"-?\d+")
_FLOAT_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_int(text: Any) -> int | None:
    if isinstance(text, (int, float)):
        return int(text)
    s = str(text).strip()
    # Common case: bare number, possibly with commas.
    s_stripped = s.replace(",", "")
    if _INT_RE.fullmatch(s_stripped):
        return int(s_stripped)
    # Otherwise pull the last integer in the string (LLMs often end with the
    # number after explanation).
    matches = _INT_RE.findall(s_stripped)
    if matches:
        try:
            return int(matches[-1])
        except ValueError:
            return None
    return None


def _extract_float(text: Any) -> float | None:
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip().replace(",", "").replace("$", "").replace("USD", "").strip()
    if _FLOAT_RE.fullmatch(s):
        return float(s)
    matches = _FLOAT_RE.findall(s)
    if matches:
        try:
            return float(matches[-1])
        except ValueError:
            return None
    return None


def _norm_str(s: Any) -> str:
    return str(s).strip().lower()


def score_int(pred: Any, gold: Any) -> bool:
    p = _extract_int(pred)
    if p is None:
        return False
    return int(p) == int(gold)


def score_float(pred: Any, gold: Any) -> bool:
    p = _extract_float(pred)
    if p is None:
        return False
    g = float(gold)
    tol = max(abs(g) * 0.01, 0.01)
    return abs(p - g) <= tol


def score_string(pred: Any, gold: Any) -> bool:
    p = _norm_str(pred)
    g = _norm_str(gold)
    if not g:
        return not p
    if p == g:
        return True
    return g in p or p in g


def _parse_collection(value: Any) -> list:
    """Best-effort parse of a value into a list of element strings.

    Handles: native list/tuple/set, JSON arrays, Python repr lists like
    "['a', 'b']", and comma/semicolon/newline-separated strings.
    """
    if isinstance(value, (list, tuple, set)):
        return list(value)
    s = str(value).strip()
    # Try JSON / Python literal first.
    if s.startswith("[") or s.startswith("("):
        import ast
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, (list, tuple, set)):
                return list(parsed)
        except (ValueError, SyntaxError):
            pass
    # Strip enclosing brackets/quotes if present, then split on common
    # separators.
    s = s.strip("[](){}")
    return [x.strip().strip("'\"") for x in re.split(r"[,;\n]", s) if x.strip()]


def score_set(pred: Any, gold: Any) -> bool:
    g = {_norm_str(x) for x in _parse_collection(gold)}
    p = {_norm_str(x) for x in _parse_collection(pred)}
    if p == g:
        return True
    # Empty-gold sentinels: any "none/no/empty" answer matches an empty gold.
    if not g:
        s = _norm_str(pred)
        if s == "" or "none" in s or "no " in s or "empty" in s or "no item" in s:
            return True
    return False


def score_list(pred: Any, gold: Any) -> bool:
    g = [_norm_str(x) for x in _parse_collection(gold)]
    p = [_norm_str(x) for x in _parse_collection(pred)]
    return p == g


SCORERS = {
    "int": score_int,
    "float": score_float,
    "string": score_string,
    "set": score_set,
    "list": score_list,
}


def score(answer_kind: str, pred: Any, gold: Any) -> bool:
    fn = SCORERS.get(answer_kind)
    if fn is None:
        raise ValueError(f"unknown answer kind: {answer_kind}")
    return fn(pred, gold)

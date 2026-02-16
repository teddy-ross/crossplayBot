"""Leave evaluation for Crossplay Engine.

After playing a move, the tiles remaining on your rack (the "leave") have
strategic value.  A good leave keeps flexible, high-synergy tiles so that
future turns can score well.  This module provides a heuristic leave
evaluator inspired by competitive Scrabble AI research (Maven / Quackle).

The evaluation considers:
  1. Individual tile desirability (some tiles draw better future moves)
  2. Vowel / consonant balance  (ideally ~40 % vowels)
  3. Duplicate penalties         (two of the same tile = awkward rack)
  4. Synergy bonuses             (common useful combos like S, -ING, -ER, …)
  5. Blank preservation          (blanks are hugely valuable)
  6. Q-without-U penalty
"""

from __future__ import annotations

from crossplay.constants import TILE_VALUES

# ── 1. Individual tile desirability ──────────────────────────────────────
#
# Positive = good to keep,  Negative = you'd rather play it now.
# Based on how flexibly a letter participates in future words, weighted
# for the Crossplay tile distribution.

_TILE_DESIRABILITY: dict[str, float] = {
    "A":  0.5,  "B": -2.0,  "C": -0.5,  "D":  0.5,  "E":  1.5,
    "F": -2.0,  "G": -1.0,  "H":  0.5,  "I":  0.5,  "J": -4.0,
    "K": -2.5,  "L":  1.0,  "M": -0.5,  "N":  1.5,  "O":  0.0,
    "P": -0.5,  "Q": -6.0,  "R":  2.0,  "S":  5.0,  "T":  1.0,
    "U": -0.5,  "V": -4.0,  "W": -2.5,  "X": -1.0,  "Y": -0.5,
    "Z": -2.0,  "?": 15.0,   # blank is the best tile to keep
}

# ── 2. Vowel / consonant balance ─────────────────────────────────────────

_VOWELS = set("AEIOU")

def _balance_penalty(leave: list[str]) -> float:
    """Penalise heavy vowel or consonant skew in the leave."""
    if not leave:
        return 0.0
    n = len(leave)
    vowels = sum(1 for t in leave if t in _VOWELS)
    ratio = vowels / n
    # Ideal ~0.40;  distance from ideal is penalised quadratically
    deviation = ratio - 0.40
    return -15.0 * deviation * deviation * n


# ── 3. Duplicate penalty ────────────────────────────────────────────────

def _duplicate_penalty(leave: list[str]) -> float:
    """Penalise having 2+ copies of the same tile (except blanks)."""
    from collections import Counter
    counts = Counter(leave)
    penalty = 0.0
    for tile, cnt in counts.items():
        if tile == "?":
            continue
        if cnt >= 2:
            penalty -= 3.0 * (cnt - 1)
        if cnt >= 3:
            penalty -= 4.0  # triple+ is extra painful
    return penalty


# ── 4. Synergy bonuses ──────────────────────────────────────────────────
#
# Award a bonus when the leave contains useful letter combos that form
# common word fragments.

_SYNERGY_PAIRS: dict[frozenset[str], float] = {
    frozenset("ER"): 1.5,
    frozenset("ED"): 1.0,
    frozenset("ES"): 1.5,
    frozenset("EN"): 1.0,
    frozenset("IN"): 1.5,
    frozenset("AN"): 1.0,
    frozenset("AT"): 0.5,
    frozenset("RE"): 1.5,
    frozenset("ST"): 1.5,
    frozenset("RS"): 1.0,
    frozenset("EL"): 0.5,
    frozenset("ET"): 0.5,
}

_SYNERGY_TRIPLES: dict[frozenset[str], float] = {
    frozenset("ING"): 3.5,
    frozenset("ERS"): 3.0,
    frozenset("EST"): 2.5,
    frozenset("IES"): 2.5,
    frozenset("ENT"): 2.0,
    frozenset("ATE"): 1.5,
    frozenset("ANE"): 1.5,
    frozenset("INE"): 1.5,
}

def _synergy_bonus(leave_set: set[str]) -> float:
    """Bonus for containing useful letter combos."""
    bonus = 0.0
    for combo, val in _SYNERGY_PAIRS.items():
        if combo <= leave_set:
            bonus += val
    for combo, val in _SYNERGY_TRIPLES.items():
        if combo <= leave_set:
            bonus += val
    return bonus


# ── 5. Q-without-U penalty ──────────────────────────────────────────────

def _q_without_u(leave: list[str]) -> float:
    if "Q" in leave and "U" not in leave:
        return -8.0
    return 0.0


# ── Public API ───────────────────────────────────────────────────────────

def evaluate_leave(leave: list[str]) -> float:
    """Return a heuristic value (in "points") for the tiles remaining
    on the rack after a move.  Higher = better strategic position.

    Parameters
    ----------
    leave : list[str]
        Uppercase tile letters remaining (e.g. ``["S", "E", "R"]``).
        Use ``"?"`` for blanks.
    """
    if not leave:
        # Using all tiles is neither penalised nor rewarded here;
        # the sweep bonus already handles that.
        return 0.0

    score = 0.0

    # 1. Tile desirability
    for t in leave:
        score += _TILE_DESIRABILITY.get(t, 0.0)

    # 2. Vowel / consonant balance
    score += _balance_penalty(leave)

    # 3. Duplicates
    score += _duplicate_penalty(leave)

    # 4. Synergy
    score += _synergy_bonus(set(leave))

    # 5. Q-without-U
    score += _q_without_u(leave)

    return round(score, 1)

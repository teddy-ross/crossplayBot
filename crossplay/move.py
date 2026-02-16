"""Move representation for Crossplay."""

from __future__ import annotations


class Move:
    """Represents a single scored move on the board."""

    __slots__ = (
        "word", "row", "col", "direction", "score",
        "tiles_used", "cross_words", "is_sweep", "blank_positions",
    )

    def __init__(
        self,
        word: str,
        row: int,
        col: int,
        direction: str,
        score: int,
        tiles_used: list[tuple[str, int, int]],
        cross_words: list[str] | None = None,
        is_sweep: bool = False,
        blank_positions: set[tuple[int, int]] | None = None,
    ):
        self.word = word
        self.row = row
        self.col = col
        self.direction = direction  # 'H' or 'V'
        self.score = score
        self.tiles_used = tiles_used  # [(letter, row, col), ...]
        self.cross_words = cross_words or []
        self.is_sweep = is_sweep
        self.blank_positions = blank_positions or set()

    def __repr__(self) -> str:
        sweep = " +SWEEP!" if self.is_sweep else ""
        arrow = "→" if self.direction == "H" else "↓"
        return f"{self.word} at ({self.row},{self.col}) {arrow} = {self.score} pts{sweep}"

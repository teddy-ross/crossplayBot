"""Move representation for Crossplay."""

from __future__ import annotations


class Move:
    """Represents a single scored move on the board."""

    __slots__ = (
        "word", "row", "col", "direction", "score",
        "tiles_used", "cross_words", "is_sweep", "blank_positions",
        "leave_score", "equity", "sim_score", "sim_equity",
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
        leave_score: float = 0.0,
        equity: float = 0.0,
        sim_score: float | None = None,
        sim_equity: float | None = None,
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
        self.leave_score = leave_score  # heuristic value of remaining rack
        self.equity = equity            # score + leave_score
        self.sim_score = sim_score      # score - avg opponent best (Monte Carlo)
        self.sim_equity = sim_equity    # sim_score + leave_score

    def __repr__(self) -> str:
        sweep = " +SWEEP!" if self.is_sweep else ""
        arrow = "→" if self.direction == "H" else "↓"
        eq = f"  equity={self.equity:+.1f}" if self.equity != self.score else ""
        return f"{self.word} at ({self.row},{self.col}) {arrow} = {self.score} pts{sweep}{eq}"

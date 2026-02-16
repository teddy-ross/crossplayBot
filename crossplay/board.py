"""15×15 Crossplay game board."""

from __future__ import annotations

from crossplay.constants import BOARD_SIZE, BONUS_GRID


class Board:
    """15x15 game board. Cells are None (empty), 'A'-'Z' (tile),
    or lowercase 'a'-'z' (blank used as that letter)."""

    def __init__(self):
        self.cells: list[list[str | None]] = [
            [None] * BOARD_SIZE for _ in range(BOARD_SIZE)
        ]

    def get(self, row: int, col: int) -> str | None:
        """Letter at (row, col), or None."""
        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            return self.cells[row][col]
        return None

    def set(self, row: int, col: int, letter: str | None) -> None:
        """Place a letter or clear the cell."""
        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            self.cells[row][col] = letter

    def is_empty(self, row: int, col: int) -> bool:
        """True if no tile at (row, col)."""
        return self.get(row, col) is None

    def is_occupied(self, row: int, col: int) -> bool:
        """True if there's a tile at (row, col)."""
        return not self.is_empty(row, col)

    def is_board_empty(self) -> bool:
        """True if no tiles on the board."""
        return all(
            self.cells[r][c] is None
            for r in range(BOARD_SIZE)
            for c in range(BOARD_SIZE)
        )

    def count_tiles(self) -> int:
        """Number of tiles on the board."""
        return sum(
            1 for r in range(BOARD_SIZE) for c in range(BOARD_SIZE)
            if self.is_occupied(r, c)
        )

    def get_bonus(self, row: int, col: int) -> str | None:
        """Bonus type at (row, col) if uncovered, else None."""
        if self.is_occupied(row, col):
            return None
        return BONUS_GRID[row][col]

    def copy(self) -> Board:
        """Shallow copy of the board."""
        b = Board()
        for r in range(BOARD_SIZE):
            b.cells[r] = self.cells[r][:]
        return b

    def __str__(self) -> str:
        header = "    " + " ".join(f"{c:>2}" for c in range(BOARD_SIZE))
        sep = "   " + "---" * BOARD_SIZE
        lines = [header, sep]
        for r in range(BOARD_SIZE):
            parts = [f"{r:>2} |"]
            for c in range(BOARD_SIZE):
                val = self.cells[r][c]
                if val:
                    parts.append(f" {val.upper()} ")
                else:
                    bonus = BONUS_GRID[r][c]
                    if bonus in (".", "*"):
                        parts.append(f" {bonus} ")
                    else:
                        parts.append(f"{bonus:>3}")
            lines.append("".join(parts))
        return "\n".join(lines)

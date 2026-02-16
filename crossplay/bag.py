"""Tile bag for Crossplay.

Defines the full tile distribution (how many of each letter exist in
the game) and provides helpers to compute the remaining unseen tiles
given the board state and the player's rack.
"""

from __future__ import annotations

from crossplay.board import Board
from crossplay.constants import BOARD_SIZE

# ── Crossplay tile distribution ─────────────────────────────────────────
# Total: 100 tiles (97 lettered + 3 blanks), same as standard Scrabble.
# Adjust counts here if Crossplay uses a different distribution.

TILE_DISTRIBUTION: dict[str, int] = {
    "A": 9,  "B": 2,  "C": 2,  "D": 4,  "E": 12, "F": 2,  "G": 3,
    "H": 3,  "I": 8,  "J": 1,  "K": 1,  "L": 4,  "M": 2,  "N": 5,
    "O": 8,  "P": 2,  "Q": 1,  "R": 6,  "S": 5,  "T": 6,  "U": 3,
    "V": 2,  "W": 2,  "X": 1,  "Y": 2,  "Z": 1,  "?": 3,
}

TOTAL_TILES = sum(TILE_DISTRIBUTION.values())  # 100


def make_full_bag() -> list[str]:
    """Return a list of all tiles in the bag (unshuffled)."""
    bag: list[str] = []
    for tile, count in TILE_DISTRIBUTION.items():
        bag.extend([tile] * count)
    return bag


def remaining_tiles(board: Board, my_rack: list[str]) -> list[str]:
    """Compute the unseen tiles: full bag minus board tiles minus my rack.

    Board tiles that are lowercase (mystery/blank) are counted as blanks
    consumed from the bag.

    Parameters
    ----------
    board : Board
        The current board state.
    my_rack : list[str]
        The player's current rack (uppercase letters, ``"?"`` for blanks).

    Returns
    -------
    list[str]
        Tiles remaining in the bag + opponent's rack (unseen pool).
    """
    # Start with the full distribution
    pool: dict[str, int] = dict(TILE_DISTRIBUTION)

    # Subtract board tiles
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            cell = board.get(r, c)
            if cell is not None:
                if cell.islower():
                    # Mystery / blank tile — counts as a "?" from the bag
                    pool["?"] = pool.get("?", 0) - 1
                else:
                    tile = cell.upper()
                    pool[tile] = pool.get(tile, 0) - 1

    # Subtract player's rack
    for tile in my_rack:
        t = tile.upper() if tile != "?" else "?"
        pool[t] = pool.get(t, 0) - 1

    # Build the remaining tile list (ignore negative counts from errors)
    remaining: list[str] = []
    for tile, count in pool.items():
        remaining.extend([tile] * max(0, count))

    return remaining

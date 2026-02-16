#!/usr/bin/env python3
"""
Crossplay Engine

Reads the board state from your screen (or manual input) and finds
the highest-scoring move. Uses Tesseract OCR for screen reading
and a trie-backed move engine for fast word search.

Requires: pip install mss Pillow pytesseract opencv-python numpy
Also needs Tesseract OCR (brew install tesseract on macOS).
"""

from __future__ import annotations

import argparse
import logging
import os
import string
import time


# Logging setup

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
log = logging.getLogger("crossplay")

__all__ = [
    "Board",
    "Dictionary",
    "Move",
    "MoveEngine",
    "ScreenReader",
    "Trie",
    "TrieNode",
]

# Game constants

BOARD_SIZE = 15
CENTER = 7  # 0-indexed center square

# Crossplay tile point values (differs from Scrabble!)
TILE_VALUES: dict[str, int] = {
    'A': 1, 'B': 4, 'C': 3, 'D': 2, 'E': 1, 'F': 4, 'G': 4,
    'H': 3, 'I': 1, 'J': 10, 'K': 6, 'L': 2, 'M': 3, 'N': 1,
    'O': 1, 'P': 3, 'Q': 10, 'R': 1, 'S': 1, 'T': 1, 'U': 2,
    'V': 6, 'W': 5, 'X': 8, 'Y': 4, 'Z': 10, '?': 0,
}

# Bonus square layout for Crossplay board
# Key: . = normal, DL = double letter, TL = triple letter,
#      DW = double word, TW = triple word, * = center (star)
# fmt: off
BONUS_GRID: list[list[str]] = [
    ["TL", ".",  ".",  "TW", ".",  ".",  ".",  "DL", ".",  ".",  ".",  "TW", ".",  ".",  "TL"],
    [".",  "DW", ".",  ".",  ".",  ".",  "TL", ".",  "TL", ".",  ".",  ".",  ".",  "DW", "." ],
    [".",  ".",  ".",  ".",  "DL", ".",  ".",  ".",  ".",  ".",  "DL", ".",  ".",  ".",  "." ],
    ["TW", ".",  ".",  "DL", ".",  ".",  ".",  "DW", ".",  ".",  ".",  "DL", ".",  ".",  "TW"],
    [".",  ".",  "DL", ".",  ".",  "TL",  ".", ".",  ".", "TL",  ".",  ".",  "DL", ".",  "." ],
    [".",  ".",  ".",  ".",  "TL",  ".", ".",  "DL", ".",  ".", "TL",  ".",  ".",  ".",  "." ],
    [".",  "TL", ".",  ".",  ".",  ".",  ".",  ".",  ".",  ".",  ".",  ".",  ".",  "TL", "." ],
    ["DL", ".",  ".", "DW",  ".",  "DL",  ".",  "*",  ".",  "DL",  ".",  "DW", ".", ".",  "DL"],
    [".",  "TL", ".",  ".",  ".",  ".",  ".",  ".",  ".",  ".",  ".",  ".",  ".",  "TL", "." ],
    [".",  ".",  ".",  ".",  "TL",  ".", ".",  "DL", ".",  ".", "TL",  ".",  ".",  ".",  "." ],
    [".",  ".",  "DL", ".",  ".",  "TL",  ".", ".",  ".", "TL",  ".",  ".",  "DL", ".",  "." ],
    ["TW", ".",  ".",  "DL", ".",  ".",  ".",  "DW", ".",  ".",  ".",  "DL", ".",  ".",  "TW"],
    [".",  ".",  ".",  ".",  "DL", ".",  ".",  ".",  ".",  ".",  "DL", ".",  ".",  ".",  "." ],
    [".",  "DW", ".",  ".",  ".",  ".",  "TL", ".",  "TL", ".",  ".",  ".",  ".",  "DW", "." ],
    ["TL", ".",  ".",  "TW", ".",  ".",  ".",  "DL", ".",  ".",  ".",  "TW", ".",  ".",  "TL"],
]
# fmt: on

SWEEP_BONUS = 40  # 40 points for using all 7 tiles in one turn


# Trie for prefix lookups

class TrieNode:
    """Single node in the prefix trie."""

    __slots__ = ("children", "is_terminal")

    def __init__(self):
        self.children: dict[str, TrieNode] = {}
        self.is_terminal: bool = False


class Trie:
    """Prefix trie for fast word and prefix checks."""

    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_terminal = True

    def is_word(self, word: str) -> bool:
        node = self._walk(word)
        return node is not None and node.is_terminal

    def is_prefix(self, prefix: str) -> bool:
        return self._walk(prefix) is not None

    def _walk(self, s: str) -> TrieNode | None:
        node = self.root
        for ch in s:
            node = node.children.get(ch)
            if node is None:
                return None
        return node


# Dictionary / word list

class Dictionary:
    """Word list with both set-lookup and trie-based prefix search."""

    def __init__(self, dict_path: str | None = None):
        self.words: set[str] = set()
        self.trie = Trie()
        self._load(dict_path)

    def _load(self, dict_path: str | None) -> None:
        search_paths: list[str] = []
        if dict_path:
            search_paths.append(dict_path)

        search_paths.extend([
            "dictionary.txt",
            "twl06.txt",
            "sowpods.txt",
            "words.txt",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "dictionary.txt"),
            "/usr/share/dict/words",
        ])

        for path in search_paths:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        word = line.strip().upper()
                        if 2 <= len(word) <= BOARD_SIZE and word.isalpha():
                            self.words.add(word)
                            self.trie.insert(word)
                if self.words:
                    log.info("Loaded %s words from %s", f"{len(self.words):,}", path)
                    return

        log.warning("No dictionary file found -- using built-in minimal word list.")
        log.warning("Download TWL06 or SOWPODS and save as dictionary.txt for best results.")
        self._load_minimal()

    def _load_minimal(self) -> None:
        two_letter = {
            "AA", "AB", "AD", "AE", "AG", "AH", "AI", "AL", "AM", "AN",
            "AR", "AS", "AT", "AW", "AX", "AY", "BA", "BE", "BI", "BO",
            "BY", "DA", "DE", "DO", "ED", "EF", "EH", "EL", "EM", "EN",
            "ER", "ES", "ET", "EW", "EX", "FA", "FE", "GO", "HA", "HE",
            "HI", "HM", "HO", "ID", "IF", "IN", "IS", "IT", "JO", "KA",
            "KI", "LA", "LI", "LO", "MA", "ME", "MI", "MM", "MO", "MU",
            "MY", "NA", "NE", "NO", "NU", "OD", "OE", "OF", "OH", "OI",
            "OK", "OM", "ON", "OP", "OR", "OS", "OU", "OW", "OX", "OY",
            "PA", "PE", "PI", "PO", "QI", "RE", "SH", "SI", "SO", "TA",
            "TI", "TO", "UH", "UM", "UN", "UP", "US", "UT", "WE", "WO",
            "XI", "XU", "YA", "YE", "YO", "ZA",
        }
        common = {
            "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN",
            "HER", "WAS", "ONE", "OUR", "OUT", "DAY", "HAD", "HAS", "HIS",
            "HOW", "ITS", "MAY", "NEW", "NOW", "OLD", "SEE", "WAY", "WHO",
            "BOY", "DID", "GET", "HIM", "LET", "SAY", "SHE", "TOO", "USE",
            "CAT", "DOG", "RUN", "SET", "TOP", "RED", "WORD", "PLAY", "GAME",
            "TILE", "BEST", "MOVE", "QUIZ", "QUAY", "JINX", "ZERO", "ZONE",
            "JAZZ", "FIZZ", "BUZZ", "FUZZ", "HAZE", "MAZE", "GAZE", "LAZE",
            "OXEN", "APEX", "LYNX", "ONYX", "WAXY", "DEWY", "ENVY", "LEVY",
            "NAVY", "WAVY", "HAVE", "GAVE", "SAVE", "WAVE", "CAVE", "DOVE",
            "FIVE", "GIVE", "HIVE", "JIVE", "LIVE", "LOVE", "OVEN", "OVER",
            "VERY", "VIEW", "VOWS", "AVOW", "AVID", "EVEN", "EVER", "EVIL",
            "VOID",
        }
        self.words = two_letter | common
        for w in self.words:
            self.trie.insert(w)

    def is_valid(self, word: str) -> bool:
        return word.upper() in self.words

    def __contains__(self, word: str) -> bool:
        return self.is_valid(word)


# Board

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

    def copy(self) -> "Board":
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


# Move

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


# Move engine

class MoveEngine:
    """Finds legal moves using anchor-based generation with trie pruning
    (similar to the Appel-Jacobson algorithm)."""

    def __init__(self, dictionary: Dictionary):
        self.dict = dictionary
        self.trie = dictionary.trie

    # public API

    def find_best_moves(self, board: Board, rack: list[str], top_n: int = 10) -> list[Move]:
        """Top N highest-scoring legal moves."""
        all_moves = self._generate_all_moves(board, rack)
        # Deduplicate (same word + same position + same direction)
        seen: set[tuple[str, int, int, str]] = set()
        unique: list[Move] = []
        for m in all_moves:
            key = (m.word, m.row, m.col, m.direction)
            if key not in seen:
                seen.add(key)
                unique.append(m)
        unique.sort(key=lambda m: m.score, reverse=True)
        return unique[:top_n]

    # move generation

    def _generate_all_moves(self, board: Board, rack: list[str]) -> list[Move]:
        moves: list[Move] = []
        rack_upper = [t.upper() for t in rack]

        if board.is_board_empty():
            moves.extend(self._generate_first_moves(board, rack_upper))
        else:
            anchors = self._find_anchors(board)
            for direction in ("H", "V"):
                for ar, ac in anchors:
                    moves.extend(
                        self._generate_moves_at_anchor(board, rack_upper, ar, ac, direction)
                    )
        return moves

    def _generate_first_moves(self, board: Board, rack: list[str]) -> list[Move]:
        """First move must cross the center square."""
        moves: list[Move] = []
        for length in range(2, min(len(rack) + 1, BOARD_SIZE + 1)):
            # Horizontal through center
            for sc in range(max(0, CENTER - length + 1),
                            min(CENTER + 1, BOARD_SIZE - length + 1)):
                if sc <= CENTER < sc + length:
                    moves.extend(self._try_placements(board, rack, CENTER, sc, "H", length))
            # Vertical through center
            for sr in range(max(0, CENTER - length + 1),
                            min(CENTER + 1, BOARD_SIZE - length + 1)):
                if sr <= CENTER < sr + length:
                    moves.extend(self._try_placements(board, rack, sr, CENTER, "V", length))
        return moves

    def _find_anchors(self, board: Board) -> set[tuple[int, int]]:
        """An anchor is an empty square adjacent to at least one occupied square."""
        anchors: set[tuple[int, int]] = set()
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if board.is_empty(r, c):
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board.is_occupied(nr, nc):
                            anchors.add((r, c))
                            break
        return anchors

    def _generate_moves_at_anchor(
        self,
        board: Board,
        rack: list[str],
        anchor_r: int,
        anchor_c: int,
        direction: str,
    ) -> list[Move]:
        """Generate valid moves that include placing at least one tile on *anchor*."""
        dr = 1 if direction == "V" else 0
        dc = 1 if direction == "H" else 0

        # Walk backwards to find existing prefix tiles before the anchor
        pr, pc = anchor_r - dr, anchor_c - dc
        prefix_len = 0
        while 0 <= pr < BOARD_SIZE and 0 <= pc < BOARD_SIZE and board.is_occupied(pr, pc):
            prefix_len += 1
            pr -= dr
            pc -= dc

        start_r = anchor_r - prefix_len * dr
        start_c = anchor_c - prefix_len * dc

        # Walk forward from anchor to find how far tiles extend
        suffix_tiles = 0
        sr, sc = anchor_r + dr, anchor_c + dc
        while 0 <= sr < BOARD_SIZE and 0 <= sc < BOARD_SIZE and board.is_occupied(sr, sc):
            suffix_tiles += 1
            sr += dr
            sc += dc

        moves: list[Move] = []
        max_length = min(prefix_len + len(rack) + suffix_tiles + 1, BOARD_SIZE)
        for length in range(2, max_length + 1):
            end_r = start_r + (length - 1) * dr
            end_c = start_c + (length - 1) * dc
            if end_r >= BOARD_SIZE or end_c >= BOARD_SIZE:
                break
            # Word must cover the anchor
            anchor_offset_r = anchor_r - start_r
            anchor_offset_c = anchor_c - start_c
            anchor_idx = anchor_offset_r if dr else anchor_offset_c
            if anchor_idx < 0 or anchor_idx >= length:
                continue
            moves.extend(self._try_placements(board, rack, start_r, start_c, direction, length))
        return moves

    # placement with trie-guided search

    def _try_placements(
        self,
        board: Board,
        rack: list[str],
        start_r: int,
        start_c: int,
        direction: str,
        length: int,
    ) -> list[Move]:
        """Try filling a word of given length at the start position using
        recursive trie-guided search, consuming only rack tiles."""
        dr = 1 if direction == "V" else 0
        dc = 1 if direction == "H" else 0

        # Build positional info
        positions: list[tuple[int, int]] = []
        fixed: list[str | None] = []  # letter or None
        for i in range(length):
            r = start_r + i * dr
            c = start_c + i * dc
            if r >= BOARD_SIZE or c >= BOARD_SIZE:
                return []
            positions.append((r, c))
            existing = board.get(r, c)
            fixed.append(existing.upper() if existing else None)

        tiles_needed = sum(1 for f in fixed if f is None)
        if tiles_needed == 0 or tiles_needed > len(rack):
            return []

        # Trie-guided recursive fill
        moves: list[Move] = []
        rack_avail = list(rack)  # mutable copy

        def _fill(idx: int, trie_node: TrieNode, placed: list[tuple[str, int, int]]) -> None:
            if idx == length:
                if trie_node.is_terminal:
                    # Rebuild the word
                    word_chars: list[str] = []
                    p_idx = 0
                    for i in range(length):
                        if fixed[i] is not None:
                            word_chars.append(fixed[i])
                        else:
                            word_chars.append(placed[p_idx][0])
                            p_idx += 1
                    word = "".join(word_chars)
                    # Track which positions used a blank tile
                    blank_positions = {(r, c) for _, r, c, is_blank in placed if is_blank}

                    move = self._validate_and_score(
                        board, word, start_r, start_c, direction, fixed, placed,
                        blank_positions,
                    )
                    if move:
                        moves.append(move)
                return

            r, c = positions[idx]
            if fixed[idx] is not None:
                # Square already has a tile -- must follow it in the trie
                ch = fixed[idx]
                child = trie_node.children.get(ch)
                if child:
                    _fill(idx + 1, child, placed)
            else:
                # Try each available rack tile (and blank expansions)
                tried: set[str] = set()
                for ri in range(len(rack_avail)):
                    tile = rack_avail[ri]
                    if tile == "?":
                        # Blank: try every letter (value stays 0)
                        for ch in string.ascii_uppercase:
                            if ch in tried:
                                continue
                            child = trie_node.children.get(ch)
                            if child:
                                tried.add(ch)
                                rack_avail.pop(ri)
                                _fill(idx + 1, child, placed + [(ch, r, c, True)])
                                rack_avail.insert(ri, tile)
                    else:
                        if tile in tried:
                            continue
                        child = trie_node.children.get(tile)
                        if child:
                            tried.add(tile)
                            rack_avail.pop(ri)
                            _fill(idx + 1, child, placed + [(tile, r, c, False)])
                            rack_avail.insert(ri, tile)

        _fill(0, self.trie.root, [])
        return moves

    # scoring

    def _validate_and_score(
        self,
        board: Board,
        word: str,
        start_r: int,
        start_c: int,
        direction: str,
        fixed: list[str | None],
        placed: list[tuple[str, int, int, bool]],
        blank_positions: set[tuple[int, int]],
    ) -> Move | None:
        """Validate cross-words and compute the total score."""
        dr = 1 if direction == "V" else 0
        dc = 1 if direction == "H" else 0
        cross_dr = dc  # perpendicular
        cross_dc = dr

        main_score = 0
        word_mult = 1
        total_cross = 0
        cross_words: list[str] = []

        placed_set = {(r, c): letter for letter, r, c, _ in placed}

        for i in range(len(word)):
            r = start_r + i * dr
            c = start_c + i * dc
            letter = word[i]
            # Blank tiles are always worth 0 points
            # Also check if the board cell is lowercase (mystery/blank tile)
            board_letter = board.get(r, c)
            is_board_blank = board_letter is not None and board_letter.islower()
            is_blank = (r, c) in blank_positions or is_board_blank
            letter_val = 0 if is_blank else TILE_VALUES.get(letter, 0)

            if (r, c) in placed_set:
                bonus = BONUS_GRID[r][c]
                lm = 1
                if bonus == "DL":
                    lm = 2
                elif bonus == "TL":
                    lm = 3
                elif bonus == "DW":
                    word_mult *= 2
                elif bonus == "TW":
                    word_mult *= 3
                main_score += letter_val * lm

                # Cross-word validation
                cw, cs = self._get_cross_word(
                    board, r, c, letter, cross_dr, cross_dc, bonus, is_blank,
                )
                if cw and len(cw) > 1:
                    if cw.upper() not in self.dict:
                        return None
                    cross_words.append(cw)
                    total_cross += cs
            else:
                # Existing tile on board -- no bonus
                main_score += letter_val

        main_score *= word_mult
        total_score = main_score + total_cross

        is_sweep = len(placed) == 7
        if is_sweep:
            total_score += SWEEP_BONUS

        return Move(
            word=word,
            row=start_r,
            col=start_c,
            direction=direction,
            score=total_score,
            tiles_used=[(letter, r, c) for letter, r, c, _ in placed],
            cross_words=cross_words,
            is_sweep=is_sweep,
            blank_positions=blank_positions,
        )

    def _get_cross_word(
        self,
        board: Board,
        r: int,
        c: int,
        placed_letter: str,
        cross_dr: int,
        cross_dc: int,
        bonus: str,
        is_blank: bool = False,
    ) -> tuple[str | None, int]:
        """Build the perpendicular word formed at (r, c) and return (word, score)."""
        # Gather letters before (track raw case to detect board blanks)
        before_raw: list[str] = []
        nr, nc = r - cross_dr, c - cross_dc
        while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board.is_occupied(nr, nc):
            before_raw.append(board.get(nr, nc))
            nr -= cross_dr
            nc -= cross_dc
        before_raw.reverse()
        before = [ch.upper() for ch in before_raw]

        # Gather letters after (track raw case to detect board blanks)
        after_raw: list[str] = []
        nr, nc = r + cross_dr, c + cross_dc
        while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board.is_occupied(nr, nc):
            after_raw.append(board.get(nr, nc))
            nr += cross_dr
            nc += cross_dc
        after = [ch.upper() for ch in after_raw]

        if not before and not after:
            return None, 0

        cross_word = "".join(before) + placed_letter + "".join(after)

        # Score cross-word (blank / mystery tiles on board are worth 0)
        score = sum(
            0 if raw.islower() else TILE_VALUES.get(raw.upper(), 0)
            for raw in before_raw
        )

        letter_val = 0 if is_blank else TILE_VALUES.get(placed_letter, 0)
        cw_mult = 1
        if bonus == "DL":
            score += letter_val * 2
        elif bonus == "TL":
            score += letter_val * 3
        else:
            score += letter_val
        if bonus == "DW":
            cw_mult = 2
        elif bonus == "TW":
            cw_mult = 3

        score += sum(
            0 if raw.islower() else TILE_VALUES.get(raw.upper(), 0)
            for raw in after_raw
        )
        score *= cw_mult
        return cross_word, score


# Screen reader (OCR)

class ScreenReader:
    """Reads the Crossplay board from a screenshot using OpenCV + Tesseract."""

    def __init__(self):
        self.mss = self._try_import("mss")
        self.cv2 = self._try_import("cv2", pip_name="opencv-python")
        self.pytesseract = self._try_import("pytesseract")
        self.np = self._try_import("numpy")

    @staticmethod
    def _try_import(name: str, pip_name: str | None = None):
        try:
            return __import__(name)
        except ImportError:
            log.error("'%s' not installed.  Run: pip install %s", name, pip_name or name)
            return None

    @property
    def is_available(self) -> bool:
        return all(x is not None for x in (self.cv2, self.pytesseract, self.np))

    # capture

    def capture_screen(self, region: dict | None = None):
        """Grab a screenshot; returns a PIL Image."""
        if not self.mss:
            raise RuntimeError("mss not available -- install with: pip install mss")
        from PIL import Image

        with self.mss.mss() as sct:
            shot = sct.grab(region or sct.monitors[0])
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    # read board from image

    def read_board_from_image(self, img) -> tuple[Board, list[str]]:
        """
        Read the Crossplay board and rack from a PIL Image.
        Returns ``(Board, rack_letters)``.
        """
        if not self.is_available:
            raise RuntimeError("OCR dependencies not available (cv2, pytesseract, numpy)")

        cv2 = self.cv2
        np = self.np

        img_array = np.array(img)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

        board = Board()

        # 1. Detect board region
        board_rect = self._find_board_region(img_bgr, gray)
        if board_rect is None:
            log.warning("Board region not detected -- falling back to heuristic crop.")
            h, w = img_bgr.shape[:2]
            size_px = int(min(h, w) * 0.7)
            bx = (w - size_px) // 2
            by = int(h * 0.08)
            board_rect = (bx, by, size_px, size_px)

        bx, by, bw, bh = board_rect
        cell_w = bw / BOARD_SIZE
        cell_h = bh / BOARD_SIZE
        log.info("Board at (%d,%d) size %dx%d  |  cell %.1fx%.1f px", bx, by, bw, bh, cell_w, cell_h)

        # 2. Read each cell
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                cx = int(bx + col * cell_w)
                cy = int(by + row * cell_h)
                cw = int(cell_w)
                ch = int(cell_h)
                pad = max(2, int(min(cw, ch) * 0.1))

                cell_bgr = img_bgr[cy + pad:cy + ch - pad, cx + pad:cx + cw - pad]
                if cell_bgr.size == 0:
                    continue

                cell_hsv = hsv[cy + pad:cy + ch - pad, cx + pad:cx + cw - pad]
                if self._cell_has_tile(cell_bgr, cell_hsv):
                    cell_gray = gray[cy + pad:cy + ch - pad, cx + pad:cx + cw - pad]
                    letter = self._ocr_cell(cell_bgr, cell_gray)
                    if letter:
                        board.set(row, col, letter)

        # 3. Read the rack
        rack = self._read_rack(img_bgr, gray, hsv, board_rect)
        return board, rack

    # helpers

    def _find_board_region(self, img_bgr, gray) -> tuple[int, int, int, int] | None:
        cv2 = self.cv2
        edges = cv2.Canny(gray, 50, 150)
        edges = cv2.dilate(edges, None, iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = img_bgr.shape[:2]
        min_area = (min(h, w) * 0.3) ** 2

        best = None
        best_area = 0.0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > min_area:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect = cw / ch if ch > 0 else 0
                if 0.7 < aspect < 1.3 and area > best_area:
                    best = (x, y, cw, ch)
                    best_area = area
        return best

    def _cell_has_tile(self, cell_bgr, cell_hsv) -> bool:
        np = self.np
        mean_val = float(np.mean(cell_hsv[:, :, 2]))
        mean_sat = float(np.mean(cell_hsv[:, :, 1]))
        # Tiles are light & desaturated (beige/cream); bonus squares are saturated.
        return mean_val > 150 and mean_sat < 80

    def _ocr_cell(self, cell_bgr, cell_gray) -> str | None:
        """Run single-character OCR on a cell image."""
        return self._ocr_single_letter(cell_gray)

    def _ocr_single_letter(self, gray_region) -> str | None:
        """Threshold, resize, and OCR a grayscale region for one letter."""
        cv2 = self.cv2
        pytesseract = self.pytesseract
        _, thresh = cv2.threshold(gray_region, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        resized = cv2.resize(thresh, (60, 60), interpolation=cv2.INTER_CUBIC)
        if cv2.mean(resized)[0] < 128:
            resized = cv2.bitwise_not(resized)
        config = "--psm 10 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        text = pytesseract.image_to_string(resized, config=config).strip()
        if text and len(text) == 1 and text.isalpha():
            return text.upper()
        return None

    def _read_rack(self, img_bgr, gray, hsv, board_rect) -> list[str]:
        """Locate and OCR the 7-tile rack below the board."""
        cv2 = self.cv2
        np = self.np

        bx, by, bw, bh = board_rect
        h, w = img_bgr.shape[:2]

        rack_y = by + bh + int(bh * 0.05)
        rack_h = int(bh * 0.08)
        rack_x = bx + int(bw * 0.1)
        rack_w = int(bw * 0.8)

        if rack_y + rack_h > h:
            rack_y = by + bh
            rack_h = min(int(bh * 0.06), h - rack_y)

        rack: list[str] = []
        tile_w = rack_w // 7

        for i in range(7):
            tx = rack_x + i * tile_w
            if tx + tile_w > w or rack_y + rack_h > h:
                break
            cell_gray = gray[rack_y:rack_y + rack_h, tx:tx + tile_w]
            if cell_gray.size == 0:
                continue
            letter = self._ocr_single_letter(cell_gray)
            if letter:
                rack.append(letter)
        return rack


# Manual board input

def manual_board_input() -> tuple[Board, list[str]]:
    """Interactive board + rack entry from the terminal."""
    board = Board()
    print("\n" + "=" * 60)
    print("  CROSSPLAY ENGINE -- Manual Board Entry")
    print("=" * 60)
    print()
    print("Commands:")
    print("  ROW COL LETTER        -- place one tile     (e.g. 7 7 H)")
    print("  ROW COL WORD H|V      -- place a whole word (e.g. 7 5 HELLO H)")
    print("  show                  -- print the board")
    print("  clear                 -- reset the board")
    print("  done                  -- finish entering tiles")
    print()

    while True:
        try:
            inp = input("  tile> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        cmd = inp.lower()
        if cmd == "done":
            break
        if cmd == "show":
            print(board)
            continue
        if cmd == "clear":
            board = Board()
            print("  Board cleared.")
            continue

        parts = inp.split()
        if len(parts) == 3:
            try:
                r, c = int(parts[0]), int(parts[1])
                letter = parts[2].upper()
                if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and len(letter) == 1 and letter.isalpha():
                    board.set(r, c, letter)
                    print(f"  Placed {letter} at ({r},{c})")
                else:
                    print("  Invalid.  ROW(0-14) COL(0-14) LETTER(A-Z)")
            except ValueError:
                print("  Invalid.  ROW COL LETTER")
        elif len(parts) >= 4:
            try:
                r, c = int(parts[0]), int(parts[1])
                word = parts[2].upper()
                d = parts[3].upper()
                d_r = 1 if d == "V" else 0
                d_c = 1 if d == "H" else 0
                for i, ch in enumerate(word):
                    board.set(r + i * d_r, c + i * d_c, ch)
                arrow = "→" if d == "H" else "↓"
                print(f"  Placed '{word}' at ({r},{c}) {arrow}")
            except (ValueError, IndexError):
                print("  Invalid.  ROW COL WORD H|V")
        else:
            print("  Format: ROW COL LETTER  or  ROW COL WORD H|V")

    print()
    print(board)

    rack_input = input("\nEnter your rack (e.g. AEIOUQZ, use ? for blanks): ").strip().upper()
    return board, list(rack_input)


# GUI (tkinter)

# Colour palette
_BG = "#0f0f1a"
_FG = "#e2e2f0"
_ACCENT = "#7c3aed"
_CELL_EMPTY = "#1a1a2e"
_CELL_TILE = "#f5e6c8"
_CELL_TILE_FG = "#1a1a2e"
_BONUS_COLORS = {
    "DL": "#eab308", "TL": "#16a34a",
    "DW": "#2563eb", "TW": "#7c3aed",
    "*": "#3a3a5e", ".": _CELL_EMPTY,
}
_HIGHLIGHT = "#ef4444"
_CELL_SIZE = 38
_BOARD_PX = _CELL_SIZE * BOARD_SIZE


def _draw_board(
    canvas,
    board: Board,
    highlight_tiles: list[tuple[str, int, int]] | None = None,
    blank_positions: set[tuple[int, int]] | None = None,
):
    """Draw the board on the canvas, highlighting placed tiles if given."""
    canvas.delete("all")
    ht_map: dict[tuple[int, int], str] = {}
    if highlight_tiles:
        ht_map = {(r, c): letter for letter, r, c in highlight_tiles}
    blanks = blank_positions or set()

    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            x1 = c * _CELL_SIZE + 1
            y1 = r * _CELL_SIZE + 1
            x2 = x1 + _CELL_SIZE
            y2 = y1 + _CELL_SIZE
            cx = x1 + _CELL_SIZE // 2
            cy = y1 + _CELL_SIZE // 2

            letter = board.get(r, c)
            is_hl = (r, c) in ht_map
            is_board_blank = letter is not None and letter.islower()

            # Determine colours
            if is_hl:
                bg, fg, outline, olw = _HIGHLIGHT, "#fff", "#fca", 2
            elif letter and is_board_blank:
                bg, fg, outline, olw = "#d4c4a8", _CELL_TILE_FG, "#7c3aed", 2
            elif letter:
                bg, fg, outline, olw = _CELL_TILE, _CELL_TILE_FG, "#0a0a14", 1
            else:
                bonus = BONUS_GRID[r][c]
                bg = _BONUS_COLORS.get(bonus, _CELL_EMPTY)
                fg, outline, olw = "#fff", "#0a0a14", 1

            canvas.create_rectangle(x1, y1, x2, y2, fill=bg, outline=outline, width=olw)

            # Draw letter (either existing or highlighted placement)
            display = letter.upper() if letter else ht_map.get((r, c))
            if display:
                canvas.create_text(cx, cy - 2, text=display,
                                   font=("Helvetica", 14, "bold"), fill=fg)
                pts = 0 if (is_board_blank or (r, c) in blanks) else TILE_VALUES.get(display, 0)
                sub_fg = "#fcc" if is_hl else "#888"
                canvas.create_text(x2 - 6, y2 - 5, text=str(pts),
                                   font=("Helvetica", 7), fill=sub_fg)
            else:
                bonus = BONUS_GRID[r][c]
                if bonus != ".":
                    _display_labels = {"DL": "2L", "TL": "3L", "DW": "2W", "TW": "3W", "*": "★"}
                    label = _display_labels.get(bonus, bonus)
                    canvas.create_text(cx, cy, text=label,
                                       font=("Helvetica", 8, "bold"),
                                       fill="#fff" if bonus != "*" else "#555")


def run_gui(dictionary: Dictionary) -> None:
    """Launch the GUI."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        log.error("tkinter not available -- use --manual mode.")
        return

    root = tk.Tk()
    root.title("Crossplay Engine -- Best Move Finder")
    root.configure(bg=_BG)

    board = Board()
    engine = MoveEngine(dictionary)
    selected_cell: list[tuple[int, int] | None] = [None]
    results: list[Move] = []

    # layout

    main_frame = tk.Frame(root, bg=_BG)
    main_frame.pack(padx=15, pady=15)

    tk.Label(main_frame, text="CROSSPLAY ENGINE",
             font=("Helvetica", 22, "bold"), fg=_ACCENT, bg=_BG).pack(pady=(0, 10))

    board_frame = tk.Frame(main_frame, bg=_BG)
    board_frame.pack()

    canvas = tk.Canvas(board_frame, width=_BOARD_PX + 2, height=_BOARD_PX + 2,
                       bg="#0a0a14", highlightthickness=0)
    canvas.pack(side="left", padx=(0, 15))

    side = tk.Frame(board_frame, bg=_BG, width=320)
    side.pack(side="left", fill="y")

    # Rack
    tk.Label(side, text="YOUR RACK", font=("Helvetica", 11, "bold"),
             fg=_FG, bg=_BG).pack(anchor="w")
    rack_var = tk.StringVar()
    rack_entry = tk.Entry(side, textvariable=rack_var, font=("Courier", 18, "bold"),
             width=10, bg="#1a1a2e", fg=_FG, insertbackground=_FG,
             relief="flat", justify="center")
    rack_entry.pack(fill="x", pady=(2, 10))
    tk.Label(side, text="Use ? for blank tiles",
             font=("Helvetica", 9), fg="#666", bg=_BG).pack(anchor="w")

    # Mystery tile toggle
    blank_mode_var = tk.BooleanVar(value=False)
    blank_mode_cb = tk.Checkbutton(
        side, text="Mystery Tile (0 pts)",
        variable=blank_mode_var,
        font=("Helvetica", 10, "bold"), fg="#7c3aed", bg=_BG,
        selectcolor="#1a1a2e", activebackground=_BG, activeforeground="#7c3aed",
        cursor="hand2",
    )
    blank_mode_cb.pack(anchor="w", pady=(5, 10))

    def _make_button(parent, text, bg_color, fg_color, command, pady=(0, 0)):
        """Create a styled button using a Frame+Label to bypass macOS Aqua theming."""
        frame = tk.Frame(parent, bg=bg_color, cursor="hand2")
        frame.pack(fill="x", pady=pady)
        label = tk.Label(frame, text=text, bg=bg_color, fg=fg_color,
                         font=("Helvetica", 11, "bold"), pady=8)
        label.pack(fill="x")
        for widget in (frame, label):
            widget.bind("<Button-1>", lambda e: command())
            widget.bind("<Enter>", lambda e, f=frame, l=label: (
                f.configure(bg=_lighten(bg_color)),
                l.configure(bg=_lighten(bg_color)),
            ))
            widget.bind("<Leave>", lambda e, f=frame, l=label, c=bg_color: (
                f.configure(bg=c),
                l.configure(bg=c),
            ))
        return frame

    def _lighten(hex_color: str, amount: int = 30) -> str:
        """Lighten a hex color for hover effect."""
        r = min(255, int(hex_color[1:3], 16) + amount)
        g = min(255, int(hex_color[3:5], 16) + amount)
        b = min(255, int(hex_color[5:7], 16) + amount)
        return f"#{r:02x}{g:02x}{b:02x}"

    # Status
    status_var = tk.StringVar(value="Click board cells to place tiles, then Find Best Move.")
    status_label = tk.Label(main_frame, textvariable=status_var,
                            font=("Helvetica", 10), fg="#888", bg=_BG)

    # callbacks

    def refresh():
        _draw_board(canvas, board)

    def find_moves():
        rack_str = rack_var.get().upper().strip()
        if not rack_str:
            messagebox.showwarning("No Rack", "Enter your tile rack first!")
            return
        status_var.set("Searching...")
        root.update()

        t0 = time.time()
        best = engine.find_best_moves(board, list(rack_str), top_n=15)
        elapsed = time.time() - t0

        results.clear()
        results.extend(best)
        results_list.delete(0, tk.END)

        if not best:
            status_var.set("No valid moves found.")
            return

        for m in best:
            sweep = " *SWEEP" if m.is_sweep else ""
            arrow = ">" if m.direction == "H" else "v"
            results_list.insert(
                tk.END,
                f"{m.score:>3}pts  {m.word:<12} ({m.row},{m.col}){arrow}{sweep}",
            )
        results_list.selection_set(0)
        _highlight_result(0)
        status_var.set(
            f"Found {len(best)} moves in {elapsed:.2f}s  |  "
            f"Best: {best[0].word} = {best[0].score} pts"
        )

    def _highlight_result(idx: int):
        if 0 <= idx < len(results):
            m = results[idx]
            _draw_board(canvas, board, m.tiles_used, m.blank_positions)

    def on_result_select(event):
        sel = results_list.curselection()
        if sel:
            _highlight_result(sel[0])

    def clear_board():
        nonlocal board
        board = Board()
        results.clear()
        results_list.delete(0, tk.END)
        refresh()
        status_var.set("Board cleared.")

    def capture_screen():
        reader = ScreenReader()
        if not reader.is_available or not reader.mss:
            messagebox.showerror(
                "Missing Dependencies",
                "Screen capture requires:\n"
                "  pip install mss opencv-python pytesseract numpy\n\n"
                "Also install Tesseract OCR:\n"
                "  brew install tesseract  (macOS)\n"
                "  apt install tesseract-ocr  (Linux)",
            )
            return
        status_var.set("Capturing screen in 3 seconds...")
        root.update()
        time.sleep(3)
        try:
            img = reader.capture_screen()
            nonlocal board
            board, rack = reader.read_board_from_image(img)
            rack_var.set("".join(rack))
            refresh()
            status_var.set(
                f"Board read -- {board.count_tiles()} tiles, rack: {''.join(rack)}"
            )
        except Exception as exc:
            messagebox.showerror("Capture Error", str(exc))

    def load_image():
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")],
        )
        if not path:
            return
        reader = ScreenReader()
        if not reader.is_available:
            messagebox.showerror("Missing Dependencies",
                                 "OCR requires opencv-python, pytesseract, numpy.")
            return
        from PIL import Image
        img = Image.open(path)
        nonlocal board
        board, rack = reader.read_board_from_image(img)
        rack_var.set("".join(rack))
        refresh()
        status_var.set(f"Board loaded from image  |  Rack: {''.join(rack)}")

    # buttons

    _make_button(side, "FIND BEST MOVE", "#7c3aed", "#e9d5ff",
                 find_moves, pady=(10, 5))
    _make_button(side, "Clear Board", "#4a1a2e", "#f9a8b8",
                 clear_board, pady=(0, 10))
    _make_button(side, "Capture Screen (3s delay)", "#134e4a", "#99f6e4",
                 capture_screen, pady=(0, 5))
    _make_button(side, "Load Screenshot", "#1e3a5f", "#93c5fd",
                 load_image, pady=(0, 15))

    # Results list
    tk.Label(side, text="TOP MOVES", font=("Helvetica", 11, "bold"),
             fg=_FG, bg=_BG).pack(anchor="w")
    results_list = tk.Listbox(side, font=("Courier", 10), height=12,
                               bg="#1a1a2e", fg=_FG, selectbackground=_ACCENT,
                               selectforeground="#fff", relief="flat",
                               activestyle="none")
    results_list.pack(fill="both", expand=True, pady=(2, 10))
    results_list.bind("<<ListboxSelect>>", on_result_select)

    status_label.pack(pady=(10, 0))

    # click-to-place

    def on_canvas_click(event):
        col = (event.x - 1) // _CELL_SIZE
        row = (event.y - 1) // _CELL_SIZE
        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            selected_cell[0] = (row, col)
            mode = " [MYSTERY]" if blank_mode_var.get() else ""
            status_var.set(f"Selected ({row},{col}){mode} -- type a letter, or Del to remove.")

    canvas.bind("<Button-1>", on_canvas_click)

    def on_rack_focus_in(event):
        selected_cell[0] = None
        status_var.set("Typing in rack...")

    rack_entry.bind("<FocusIn>", on_rack_focus_in)

    def on_key(event):
        if event.widget is rack_entry:
            return
        if selected_cell[0] is None:
            return
        r, c = selected_cell[0]
        if event.char and event.char.upper() in string.ascii_uppercase:
            ch = event.char.upper()
            if blank_mode_var.get():
                board.set(r, c, ch.lower())  # lowercase = mystery/blank tile (0 pts)
            else:
                board.set(r, c, ch)
            refresh()
            nc = c + 1
            tag = " (mystery)" if blank_mode_var.get() else ""
            if nc < BOARD_SIZE:
                selected_cell[0] = (r, nc)
                status_var.set(f"Placed {ch}{tag} at ({r},{c}). Now at ({r},{nc}).")
        elif event.keysym in ("Delete", "BackSpace"):
            board.set(r, c, None)
            refresh()
            status_var.set(f"Removed tile at ({r},{c}).")

    root.bind("<Key>", on_key)

    # help label

    tk.Label(
        main_frame,
        text=(
            "Instructions:\n"
            "  Click a cell then type a letter to place a tile\n"
            "  Toggle 'Mystery Tile' to place 0-point blanks\n"
            "  Enter your rack letters above (? for blanks)\n"
            "  Click 'Find Best Move' to compute\n"
            "  Or capture your screen / load a screenshot\n"
            "  Click results to highlight moves on board"
        ),
        font=("Helvetica", 9), fg="#555", bg=_BG, justify="left",
    ).pack(pady=(10, 0), anchor="w")

    refresh()
    root.mainloop()


# CLI mode

def run_cli(dictionary: Dictionary) -> None:
    """Run in terminal mode."""
    engine = MoveEngine(dictionary)
    board, rack = manual_board_input()

    print(f"\nRack: {' '.join(rack)}")
    print("Searching for best moves...\n")

    t0 = time.time()
    best_moves = engine.find_best_moves(board, rack, top_n=10)
    elapsed = time.time() - t0

    print(f"Found {len(best_moves)} moves in {elapsed:.2f}s.\n")

    if not best_moves:
        print("No valid moves found. Check your board and rack.")
        return

    print("=" * 65)
    print(f" {'#':>2}  {'Score':>5}  {'Word':<15} {'Position':<10} {'Dir':>3}  Extra")
    print("-" * 65)
    for i, m in enumerate(best_moves):
        arrow = ">" if m.direction == "H" else "v"
        extra_parts: list[str] = []
        if m.is_sweep:
            extra_parts.append("SWEEP +40")
        if m.cross_words:
            extra_parts.append(f"Cross: {', '.join(m.cross_words)}")
        extra = "  ".join(extra_parts)
        print(f" {i+1:>2}  {m.score:>5}  {m.word:<15} ({m.row},{m.col})      {arrow}   {extra}")
    print("=" * 65)

    best = best_moves[0]
    print(
        f"\nBEST MOVE: Play '{best.word}' at ({best.row},{best.col}) "
        f"{'horizontally >' if best.direction == 'H' else 'vertically v'} "
        f"for {best.score} points!"
    )
    if best.is_sweep:
        print("   SWEEP (all 7 tiles) -- +40 bonus!")
    print("   Tiles to place: ", end="")
    for letter, r, c in best.tiles_used:
        print(f"{letter}>({r},{c}) ", end="")
    print()


# Entry point

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crossplay Engine -- finds the best move from your board state",
    )
    parser.add_argument("--manual", action="store_true",
                        help="Terminal-based manual board entry (no GUI)")
    parser.add_argument("--dict", type=str, default=None,
                        help="Path to dictionary / word list file")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug-level logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("CROSSPLAY ENGINE -- Best Move Finder")


    dictionary = Dictionary(args.dict)

    if args.manual:
        run_cli(dictionary)
    else:
        run_gui(dictionary)


if __name__ == "__main__":
    main()

"""Move engine — anchor-based generation with trie pruning."""

from __future__ import annotations

import string

from crossplay.board import Board
from crossplay.constants import BOARD_SIZE, BONUS_GRID, CENTER, SWEEP_BONUS, TILE_VALUES
from crossplay.dictionary import Dictionary
from crossplay.move import Move
from crossplay.trie import TrieNode


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

        # Reject if the word would extend into adjacent occupied cells
        # (the actual word formed on the board would be longer than `length`)
        before_r = start_r - dr
        before_c = start_c - dc
        if 0 <= before_r < BOARD_SIZE and 0 <= before_c < BOARD_SIZE and board.is_occupied(before_r, before_c):
            return []
        after_r = start_r + length * dr
        after_c = start_c + length * dc
        if 0 <= after_r < BOARD_SIZE and 0 <= after_c < BOARD_SIZE and board.is_occupied(after_r, after_c):
            return []

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

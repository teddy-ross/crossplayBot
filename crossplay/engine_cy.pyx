# cython: language_level=3, boundscheck=False, wraparound=False
"""Cython-accelerated move engine — anchor-based generation with trie pruning."""

import string

from crossplay.board import Board
from crossplay.constants import BOARD_SIZE, BONUS_GRID, CENTER, SWEEP_BONUS, TILE_VALUES
from crossplay.dictionary import Dictionary
from crossplay.leave import evaluate_leave
from crossplay.move import Move
from crossplay.trie import TrieNode


cdef int _BOARD_SIZE = 15
cdef int _CENTER = 7
cdef int _SWEEP_BONUS = 40

# Pre-build uppercase letters as a tuple for blank expansion
cdef tuple _UPPERCASE = tuple(string.ascii_uppercase)


cdef class MoveEngine:
    """Finds legal moves using anchor-based generation with trie pruning
    (similar to the Appel-Jacobson algorithm)."""

    cdef object dict_obj
    cdef object trie

    def __init__(self, dictionary):
        self.dict_obj = dictionary
        self.trie = dictionary.trie

    def find_best_moves(self, object board, list rack, int top_n=10,
                               bint use_leave_eval=False):
        """Top N highest-scoring legal moves."""
        cdef list all_moves, unique
        cdef set seen
        cdef tuple key
        cdef list rack_upper, used_tiles, leave
        cdef str tile
        cdef int _r, _c
        cdef object m

        all_moves = self._generate_all_moves(board, rack)

        # Deduplicate
        seen = set()
        unique = []
        for m in all_moves:
            key = (m.word, m.row, m.col, m.direction)
            if key not in seen:
                seen.add(key)
                unique.append(m)

        if use_leave_eval:
            rack_upper = [t.upper() for t in rack]
            for m in unique:
                used_tiles = []
                for letter, _r, _c in m.tiles_used:
                    if (_r, _c) in m.blank_positions:
                        used_tiles.append("?")
                    else:
                        used_tiles.append(letter.upper())
                leave = list(rack_upper)
                for tile in used_tiles:
                    if tile in leave:
                        leave.remove(tile)
                m.leave_score = evaluate_leave(leave)
                m.equity = m.score + m.leave_score
            unique.sort(key=lambda m: m.equity, reverse=True)
        else:
            for m in unique:
                m.equity = float(m.score)
            unique.sort(key=lambda m: m.score, reverse=True)

        return unique[:top_n]

    # ── move generation ──────────────────────────────────────────────────

    cdef list _generate_all_moves(self, object board, list rack):
        cdef list moves, rack_upper
        cdef set anchors
        cdef int ar, ac
        cdef str direction

        moves = []
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

    cdef list _generate_first_moves(self, object board, list rack):
        """First move must cross the center square."""
        cdef list moves
        cdef int length, sc, sr
        cdef int max_len, lo, hi

        moves = []
        max_len = min(len(rack) + 1, _BOARD_SIZE + 1)
        for length in range(2, max_len):
            # Horizontal through center
            lo = max(0, _CENTER - length + 1)
            hi = min(_CENTER + 1, _BOARD_SIZE - length + 1)
            for sc in range(lo, hi):
                if sc <= _CENTER < sc + length:
                    moves.extend(self._try_placements(board, rack, _CENTER, sc, "H", length))
            # Vertical through center
            lo = max(0, _CENTER - length + 1)
            hi = min(_CENTER + 1, _BOARD_SIZE - length + 1)
            for sr in range(lo, hi):
                if sr <= _CENTER < sr + length:
                    moves.extend(self._try_placements(board, rack, sr, _CENTER, "V", length))
        return moves

    cdef set _find_anchors(self, object board):
        """An anchor is an empty square adjacent to at least one occupied square."""
        cdef set anchors
        cdef int r, c, nr, nc, dr, dc

        anchors = set()
        for r in range(_BOARD_SIZE):
            for c in range(_BOARD_SIZE):
                if board.is_empty(r, c):
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr = r + dr
                        nc = c + dc
                        if 0 <= nr < _BOARD_SIZE and 0 <= nc < _BOARD_SIZE and board.is_occupied(nr, nc):
                            anchors.add((r, c))
                            break
        return anchors

    cdef list _generate_moves_at_anchor(self, object board, list rack,
                                         int anchor_r, int anchor_c,
                                         str direction):
        """Generate valid moves that include placing at least one tile on the anchor."""
        cdef int dr, dc, pr, pc, prefix_len, suffix_tiles, sr, sc
        cdef int start_r, start_c, max_length, length, end_r, end_c
        cdef int anchor_offset_r, anchor_offset_c, anchor_idx
        cdef list moves

        dr = 1 if direction == "V" else 0
        dc = 1 if direction == "H" else 0

        # Walk backwards to find existing prefix tiles before the anchor
        pr = anchor_r - dr
        pc = anchor_c - dc
        prefix_len = 0
        while 0 <= pr < _BOARD_SIZE and 0 <= pc < _BOARD_SIZE and board.is_occupied(pr, pc):
            prefix_len += 1
            pr -= dr
            pc -= dc

        start_r = anchor_r - prefix_len * dr
        start_c = anchor_c - prefix_len * dc

        # Walk forward from anchor to find how far tiles extend
        suffix_tiles = 0
        sr = anchor_r + dr
        sc = anchor_c + dc
        while 0 <= sr < _BOARD_SIZE and 0 <= sc < _BOARD_SIZE and board.is_occupied(sr, sc):
            suffix_tiles += 1
            sr += dr
            sc += dc

        moves = []
        max_length = min(prefix_len + len(rack) + suffix_tiles + 1, _BOARD_SIZE)
        for length in range(2, max_length + 1):
            end_r = start_r + (length - 1) * dr
            end_c = start_c + (length - 1) * dc
            if end_r >= _BOARD_SIZE or end_c >= _BOARD_SIZE:
                break
            # Word must cover the anchor
            anchor_offset_r = anchor_r - start_r
            anchor_offset_c = anchor_c - start_c
            anchor_idx = anchor_offset_r if dr else anchor_offset_c
            if anchor_idx < 0 or anchor_idx >= length:
                continue
            moves.extend(self._try_placements(board, rack, start_r, start_c, direction, length))
        return moves

    # ── placement with trie-guided search ────────────────────────────────

    cdef list _try_placements(self, object board, list rack,
                               int start_r, int start_c,
                               str direction, int length):
        """Try filling a word of given length using recursive trie-guided search."""
        cdef int dr, dc, before_r, before_c, after_r, after_c
        cdef int i, r, c, tiles_needed
        cdef list positions, fixed, moves, rack_avail
        cdef str existing_raw
        cdef object existing

        dr = 1 if direction == "V" else 0
        dc = 1 if direction == "H" else 0

        # Reject if the word would extend into adjacent occupied cells
        before_r = start_r - dr
        before_c = start_c - dc
        if 0 <= before_r < _BOARD_SIZE and 0 <= before_c < _BOARD_SIZE and board.is_occupied(before_r, before_c):
            return []
        after_r = start_r + length * dr
        after_c = start_c + length * dc
        if 0 <= after_r < _BOARD_SIZE and 0 <= after_c < _BOARD_SIZE and board.is_occupied(after_r, after_c):
            return []

        # Build positional info
        positions = []
        fixed = []
        for i in range(length):
            r = start_r + i * dr
            c = start_c + i * dc
            if r >= _BOARD_SIZE or c >= _BOARD_SIZE:
                return []
            positions.append((r, c))
            existing = board.get(r, c)
            if existing is not None:
                fixed.append(existing.upper())
            else:
                fixed.append(None)

        tiles_needed = 0
        for f in fixed:
            if f is None:
                tiles_needed += 1
        if tiles_needed == 0 or tiles_needed > len(rack):
            return []

        # Trie-guided recursive fill
        moves = []
        rack_avail = list(rack)  # mutable copy

        self._fill(0, length, self.trie.root, [], positions, fixed,
                   rack_avail, moves, board, start_r, start_c, direction)
        return moves

    cdef void _fill(self, int idx, int length, object trie_node,
                    list placed, list positions, list fixed,
                    list rack_avail, list moves,
                    object board, int start_r, int start_c, str direction):
        """Recursive trie-guided fill of word positions."""
        cdef int i, ri, p_idx, r, c
        cdef str ch, tile, word
        cdef object child, move
        cdef list word_chars
        cdef set blank_positions, tried

        if idx == length:
            if trie_node.is_terminal:
                # Rebuild the word
                word_chars = []
                p_idx = 0
                for i in range(length):
                    if fixed[i] is not None:
                        word_chars.append(fixed[i])
                    else:
                        word_chars.append(placed[p_idx][0])
                        p_idx += 1
                word = "".join(word_chars)
                blank_positions = set()
                for item in placed:
                    if item[3]:  # is_blank
                        blank_positions.add((item[1], item[2]))

                move = self._validate_and_score(
                    board, word, start_r, start_c, direction, fixed, placed,
                    blank_positions,
                )
                if move is not None:
                    moves.append(move)
            return

        r = positions[idx][0]
        c = positions[idx][1]

        if fixed[idx] is not None:
            # Square already has a tile -- must follow it in the trie
            ch = fixed[idx]
            child = trie_node.children.get(ch)
            if child is not None:
                self._fill(idx + 1, length, child, placed, positions, fixed,
                           rack_avail, moves, board, start_r, start_c, direction)
        else:
            # Try each available rack tile (and blank expansions)
            tried = set()
            for ri in range(len(rack_avail)):
                tile = rack_avail[ri]
                if tile == "?":
                    # Blank: try every letter
                    for ch in _UPPERCASE:
                        if ch in tried:
                            continue
                        child = trie_node.children.get(ch)
                        if child is not None:
                            tried.add(ch)
                            rack_avail.pop(ri)
                            self._fill(idx + 1, length, child,
                                       placed + [(ch, r, c, True)],
                                       positions, fixed, rack_avail, moves,
                                       board, start_r, start_c, direction)
                            rack_avail.insert(ri, tile)
                else:
                    if tile in tried:
                        continue
                    child = trie_node.children.get(tile)
                    if child is not None:
                        tried.add(tile)
                        rack_avail.pop(ri)
                        self._fill(idx + 1, length, child,
                                   placed + [(tile, r, c, False)],
                                   positions, fixed, rack_avail, moves,
                                   board, start_r, start_c, direction)
                        rack_avail.insert(ri, tile)

    # ── scoring ──────────────────────────────────────────────────────────

    cdef object _validate_and_score(self, object board, str word,
                                     int start_r, int start_c,
                                     str direction, list fixed,
                                     list placed, set blank_positions):
        """Validate cross-words and compute the total score."""
        cdef int dr, dc, cross_dr, cross_dc
        cdef int main_score, word_mult, total_cross, total_score
        cdef int i, r, c, letter_val, lm
        cdef str letter, bonus
        cdef object board_letter
        cdef bint is_board_blank, is_blank, is_sweep
        cdef dict placed_set
        cdef list cross_words
        cdef str cw
        cdef int cs

        dr = 1 if direction == "V" else 0
        dc = 1 if direction == "H" else 0
        cross_dr = dc
        cross_dc = dr

        main_score = 0
        word_mult = 1
        total_cross = 0
        cross_words = []

        placed_set = {}
        for item in placed:
            placed_set[(item[1], item[2])] = item[0]

        for i in range(len(word)):
            r = start_r + i * dr
            c = start_c + i * dc
            letter = word[i]

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
                if cw is not None and len(cw) > 1:
                    if cw.upper() not in self.dict_obj:
                        return None
                    cross_words.append(cw)
                    total_cross += cs
            else:
                main_score += letter_val

        main_score *= word_mult
        total_score = main_score + total_cross

        is_sweep = len(placed) == 7
        if is_sweep:
            total_score += _SWEEP_BONUS

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

    cdef tuple _get_cross_word(self, object board, int r, int c,
                                str placed_letter, int cross_dr, int cross_dc,
                                str bonus, bint is_blank):
        """Build the perpendicular word formed at (r, c) and return (word, score)."""
        cdef int nr, nc, score, letter_val, cw_mult
        cdef list before_raw, after_raw, before, after
        cdef str cross_word, raw
        cdef object cell

        # Gather letters before
        before_raw = []
        nr = r - cross_dr
        nc = c - cross_dc
        while 0 <= nr < _BOARD_SIZE and 0 <= nc < _BOARD_SIZE and board.is_occupied(nr, nc):
            before_raw.append(board.get(nr, nc))
            nr -= cross_dr
            nc -= cross_dc
        before_raw.reverse()
        before = [ch.upper() for ch in before_raw]

        # Gather letters after
        after_raw = []
        nr = r + cross_dr
        nc = c + cross_dc
        while 0 <= nr < _BOARD_SIZE and 0 <= nc < _BOARD_SIZE and board.is_occupied(nr, nc):
            after_raw.append(board.get(nr, nc))
            nr += cross_dr
            nc += cross_dc
        after = [ch.upper() for ch in after_raw]

        if not before and not after:
            return None, 0

        cross_word = "".join(before) + placed_letter + "".join(after)

        # Score cross-word
        score = 0
        for raw in before_raw:
            if raw.islower():
                score += 0
            else:
                score += TILE_VALUES.get(raw.upper(), 0)

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

        for raw in after_raw:
            if raw.islower():
                score += 0
            else:
                score += TILE_VALUES.get(raw.upper(), 0)
        score *= cw_mult
        return cross_word, score

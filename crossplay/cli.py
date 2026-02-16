"""CLI / terminal mode for Crossplay Engine."""

from __future__ import annotations

import time

from crossplay.board import Board
from crossplay.constants import BOARD_SIZE
from crossplay.dictionary import Dictionary
from crossplay.engine import MoveEngine


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

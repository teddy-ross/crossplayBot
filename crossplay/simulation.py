"""Monte Carlo simulation for Crossplay Engine.

After the engine generates the top candidate moves, this module can
evaluate each one by simulating multiple future turns:

  1. Play the candidate move on a copy of the board.
  2. Randomly draw 7 tiles from the remaining pool for the opponent.
  3. Find the opponent's best response.
  4. Repeat for N iterations with different random opponent racks.
  5. The candidate's "simulation equity" = move_score - avg(opponent_best).

This lets the engine penalise moves that open up huge scoring
opportunities for the opponent (e.g. leaving a Triple Word square
exposed next to a vowel).
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from crossplay.bag import remaining_tiles
from crossplay.board import Board

if TYPE_CHECKING:
    from crossplay.engine import MoveEngine
    from crossplay.move import Move

logger = logging.getLogger("crossplay.sim")


def simulate_move(
    engine: "MoveEngine",
    board: Board,
    move: "Move",
    my_rack: list[str],
    n_simulations: int = 50,
    seed: int | None = None,
) -> float:
    """Run Monte Carlo simulations for a single candidate move.

    Returns the **simulation equity**: the candidate's score minus the
    average of the opponent's best response scores across all trials.
    A higher value means the move is harder for the opponent to punish.

    Parameters
    ----------
    engine : MoveEngine
        The move engine (used to find the opponent's best response).
    board : Board
        Current board state *before* the candidate move.
    move : Move
        The candidate move to evaluate.
    my_rack : list[str]
        The player's current rack (before the move).
    n_simulations : int
        Number of random opponent racks to try.
    seed : int | None
        Optional RNG seed for reproducibility.
    """
    rng = random.Random(seed)

    # 1. Apply the candidate move to a board copy
    sim_board = board.copy()
    for letter, r, c in move.tiles_used:
        if (r, c) in move.blank_positions:
            sim_board.set(r, c, letter.lower())
        else:
            sim_board.set(r, c, letter)

    # 2. Compute tiles used from rack (to know what's left)
    rack_after: list[str] = list(my_rack)
    for letter, _r, _c in move.tiles_used:
        if (_r, _c) in move.blank_positions:
            tile = "?"
        else:
            tile = letter.upper()
        if tile in rack_after:
            rack_after.remove(tile)

    # 3. Compute the unseen tile pool (bag + opponent rack)
    #    After our move, the unseen tiles are: full bag - board_after - rack_after
    unseen = remaining_tiles(sim_board, rack_after)

    if not unseen:
        # No tiles left for opponent — endgame, no response possible
        return float(move.score)

    opponent_scores: list[float] = []

    for _ in range(n_simulations):
        # 4. Draw a random 7-tile rack for the opponent from the unseen pool
        draw_count = min(7, len(unseen))
        opp_rack = rng.sample(unseen, draw_count)

        # 5. Find the opponent's best move on the post-move board
        opp_moves = engine.find_best_moves(
            sim_board, opp_rack, top_n=1, use_leave_eval=False,
        )
        if opp_moves:
            opponent_scores.append(float(opp_moves[0].score))
        else:
            opponent_scores.append(0.0)

    avg_opp = sum(opponent_scores) / len(opponent_scores) if opponent_scores else 0.0

    sim_equity = move.score - avg_opp
    logger.debug(
        "SIM %s: score=%d  avg_opp=%.1f  sim_equity=%.1f  (%d trials)",
        move.word, move.score, avg_opp, sim_equity, n_simulations,
    )
    return round(sim_equity, 1)


def evaluate_candidates(
    engine: "MoveEngine",
    board: Board,
    candidates: list["Move"],
    my_rack: list[str],
    n_simulations: int = 50,
    progress_callback=None,
) -> list["Move"]:
    """Evaluate a list of candidate moves with Monte Carlo simulation.

    Each move gets its ``sim_score`` and ``sim_equity`` fields populated.
    The list is returned sorted by ``sim_equity`` (best first).

    Parameters
    ----------
    engine : MoveEngine
        Move engine instance.
    board : Board
        Current board state.
    candidates : list[Move]
        Top-N moves from the regular engine search.
    my_rack : list[str]
        Player's rack.
    n_simulations : int
        Simulations per candidate move.
    progress_callback : callable, optional
        Called with ``(completed_index, total)`` after each candidate is
        evaluated.  Useful for updating a progress bar in the GUI.

    Returns
    -------
    list[Move]
        Candidates sorted by sim_equity (descending).
    """
    total = len(candidates)
    for i, move in enumerate(candidates):
        eq = simulate_move(engine, board, move, my_rack, n_simulations)
        move.sim_score = eq
        move.sim_equity = move.score + move.leave_score + (eq - move.score)
        # sim_equity = score + leave_value - avg_opponent_best
        # Simplified: sim_equity = eq + leave_score
        #   where eq = score - avg_opp
        move.sim_equity = eq + move.leave_score

        if progress_callback:
            progress_callback(i + 1, total)

    candidates.sort(key=lambda m: m.sim_equity, reverse=True)
    return candidates

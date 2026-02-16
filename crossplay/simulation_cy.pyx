# cython: language_level=3, boundscheck=False, wraparound=False
"""Cython-accelerated Monte Carlo simulation for Crossplay Engine."""

import logging
import random

from crossplay.bag import remaining_tiles
from crossplay.board import Board


logger = logging.getLogger("crossplay.sim")


cpdef double simulate_move(object engine, object board, object move,
                           list my_rack, int n_simulations=50,
                           object seed=None):
    """Run Monte Carlo simulations for a single candidate move.

    Returns the simulation equity: candidate score minus the average
    of the opponent's best response scores across all trials.
    """
    cdef int i, draw_count
    cdef double avg_opp, sim_equity
    cdef list unseen, opp_rack, opp_moves, rack_after
    cdef list opponent_scores
    cdef str tile
    cdef object rng, sim_board
    cdef int _r, _c

    rng = random.Random(seed)

    # 1. Apply the candidate move to a board copy
    sim_board = board.copy()
    for letter, r, c in move.tiles_used:
        if (r, c) in move.blank_positions:
            sim_board.set(r, c, letter.lower())
        else:
            sim_board.set(r, c, letter)

    # 2. Compute tiles used from rack
    rack_after = list(my_rack)
    for letter, _r, _c in move.tiles_used:
        if (_r, _c) in move.blank_positions:
            tile = "?"
        else:
            tile = letter.upper()
        if tile in rack_after:
            rack_after.remove(tile)

    # 3. Compute the unseen tile pool
    unseen = remaining_tiles(sim_board, rack_after)

    if not unseen:
        return <double>move.score

    opponent_scores = []

    for i in range(n_simulations):
        # 4. Draw random opponent rack
        draw_count = min(7, len(unseen))
        opp_rack = rng.sample(unseen, draw_count)

        # 5. Find opponent's best move
        opp_moves = engine.find_best_moves(
            sim_board, opp_rack, top_n=1, use_leave_eval=False,
        )
        if opp_moves:
            opponent_scores.append(<double>(opp_moves[0].score))
        else:
            opponent_scores.append(0.0)

    if opponent_scores:
        avg_opp = 0.0
        for i in range(len(opponent_scores)):
            avg_opp += opponent_scores[i]
        avg_opp /= len(opponent_scores)
    else:
        avg_opp = 0.0

    sim_equity = <double>move.score - avg_opp
    logger.debug(
        "SIM %s: score=%d  avg_opp=%.1f  sim_equity=%.1f  (%d trials)",
        move.word, move.score, avg_opp, sim_equity, n_simulations,
    )
    return round(sim_equity, 1)


def evaluate_candidates(object engine, object board,
                                list candidates, list my_rack,
                                int n_simulations=50,
                                object progress_callback=None):
    """Evaluate candidates with Monte Carlo simulation.

    Populates sim_score and sim_equity fields on each move.
    Returns candidates sorted by sim_equity (best first).
    """
    cdef int total, i
    cdef double eq
    cdef object move

    total = len(candidates)
    for i in range(total):
        move = candidates[i]
        eq = simulate_move(engine, board, move, my_rack, n_simulations)
        move.sim_score = eq
        move.sim_equity = eq + move.leave_score

        if progress_callback is not None:
            progress_callback(i + 1, total)

    candidates.sort(key=lambda m: m.sim_equity, reverse=True)
    return candidates

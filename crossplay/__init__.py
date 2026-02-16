"""Crossplay Engine — modular package."""

from crossplay.constants import BOARD_SIZE, TILE_VALUES, BONUS_GRID, SWEEP_BONUS, CENTER
from crossplay.trie import Trie, TrieNode
from crossplay.dictionary import Dictionary
from crossplay.board import Board
from crossplay.move import Move
from crossplay.engine import MoveEngine
from crossplay.leave import evaluate_leave
from crossplay.ocr import ScreenReader

__all__ = [
    "BOARD_SIZE",
    "TILE_VALUES",
    "BONUS_GRID",
    "SWEEP_BONUS",
    "CENTER",
    "Board",
    "Dictionary",
    "Move",
    "MoveEngine",
    "ScreenReader",
    "evaluate_leave",
    "Trie",
    "TrieNode",
]

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

from crossplay.dictionary import Dictionary
from crossplay.gui import run_gui
from crossplay.cli import run_cli

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)


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

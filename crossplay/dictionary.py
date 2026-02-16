"""Dictionary / word list with trie-backed prefix search."""

from __future__ import annotations

import logging
import os

from crossplay.constants import BOARD_SIZE
from crossplay.trie import Trie

log = logging.getLogger("crossplay")


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
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dictionary.txt"),
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

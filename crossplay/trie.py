"""Prefix trie for fast word and prefix lookups."""

from __future__ import annotations


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

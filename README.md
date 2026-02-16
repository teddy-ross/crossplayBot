# Crossplay Engine — Best-Move Finder

A Python engine that reads your NYT Crossplay game screen via OCR, analyzes the board state, and computes the highest-scoring legal move using a trie-guided move-generation engine with Monte Carlo simulation. Cython-accelerated for speed. I built this engine to finally be able to defeat my girlfriend in Crossplay.

## Features

- **Screen Capture + OCR** — captures your screen and reads the 15×15 board + tile rack using OpenCV and Tesseract
- **Load Screenshot** — load a saved screenshot for analysis
- **Manual Board Entry** — click cells in the GUI or type in terminal mode
- **Full Move Engine** — finds all legal placements with cross-word validation (Appel-Jacobson style)
- **Cython Acceleration** — engine and simulation hot paths compiled to C for ~2× speedup (falls back to pure Python automatically)
- **Leave Evaluation** — heuristic scoring of remaining rack tiles (vowel/consonant balance, synergy combos, blank preservation)
- **Monte Carlo Simulation** — simulates random opponent racks from the remaining tile pool to find moves that minimise the opponent's best response
- **Crossplay-Accurate Scoring** — uses official Crossplay tile values (not Scrabble!), bonus squares, and the 40-point Sweep bonus
- **Mystery Tiles** — place 0-point blank tiles on the board with visual distinction
- **3 Game Tabs** — track up to 3 games simultaneously with independent board/rack/results state
- **Place Move on Board** — apply a highlighted engine result directly to the board
- **Directional Typing** — Enter for horizontal →, Shift+Enter for vertical ↓, with auto-advance cursor
- **Top 10 Results** — ranked by simulation equity with visual board highlighting
- **GUI + CLI** — tkinter desktop GUI or terminal mode

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Build Cython extensions (optional — falls back to pure Python)
pip install cython
python setup_cython.py build_ext --inplace

# 3. Run the engine
python crossplay_engine.py           # GUI mode (recommended)
python crossplay_engine.py --manual  # Terminal mode (no GUI needed)
```

## Requirements

### Python Packages
```bash
pip install -r requirements.txt
```

### System Dependencies
**Tesseract OCR** (required for screen reading):
- **macOS:** `brew install tesseract`
- **Ubuntu/Debian:** `sudo apt install tesseract-ocr`
- **Windows:** Download from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)

### Word Dictionary
The engine needs a word list file saved as `dictionary.txt` in the project directory. For best results, use a **TWL06** or **SOWPODS/NWL23** word list. Crossplay uses the NASPA Word List 2023 (NWL23).


### Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌───────────────┐
│  Screen Capture  │────▶│  OCR Reader  │────▶│  Board State  │
│  (mss library)   │     │  (OpenCV +   │     │  15×15 grid + │
│                  │     │   Tesseract) │     │  tile rack    │
└─────────────────┘     └──────────────┘     └───────┬───────┘
                                                      │
                                                      ▼
┌─────────────────┐     ┌──────────────┐     ┌───────────────┐
│  GUI Display     │◀────│  Simulation  │◀────│  Move Engine  │
│  (tkinter)       │     │  (Monte Carlo│     │  (anchor-based│
│  highlights best │     │   + leave    │     │   generation, │
│  move on board   │     │   eval)      │     │   dictionary) │
└─────────────────┘     └──────────────┘     └───────────────┘
```

### OCR Pipeline
1. **Capture** — takes a screenshot using `mss` (or loads an image file)
2. **Board Detection** — finds the game board rectangle via edge/contour detection
3. **Cell Analysis** — divides into 15×15 cells, checks color (HSV) to determine if a tile is placed
4. **Letter Recognition** — runs Tesseract in single-character mode on each occupied cell
5. **Rack Reading** — locates the tile rack below the board and reads those 7 tiles

### Move Engine
1. **Anchor Finding** — identifies empty squares adjacent to existing tiles
2. **Trie-Guided Search** — recursively fills positions using a prefix trie to prune invalid branches early (Appel-Jacobson style)
3. **Boundary Validation** — rejects words that extend into adjacent occupied tiles (prevents illegal partial-word placements)
4. **Cross-Word Validation** — ensures every newly formed perpendicular word is in the dictionary
5. **Scoring** — applies Crossplay tile values, letter/word multipliers, and Sweep bonus
6. **Leave Evaluation** — scores remaining rack tiles for strategic value (tile desirability, vowel/consonant balance, duplicate penalty, synergy bonuses, Q-without-U penalty)
7. **Monte Carlo Simulation** — for the top 10 candidates, simulates N random opponent racks from the remaining tile bag, finds the opponent's best response each time, and ranks moves by simulation equity (your score − average opponent best + leave value)

### Simulation Equity
Moves are ranked by **sim_equity** = (your score − avg opponent best response) + leave value. This accounts for:
- How many points you score
- How much you expose to the opponent (e.g. opening Triple Word squares)
- How good your remaining tiles are for future turns

## Crossplay-Specific Rules Implemented

| Rule | Implementation |
|------|---------------|
| **Tile Values** | Custom values (V=6, K=6, W=5, G=4, J=10, etc.) — NOT Scrabble values |
| **Bonus Squares** | 2L (2×letter), 3L (3×letter), 2W (2×word), 3W (3×word) |
| **Center Square** | Does NOT double the first word (unlike Scrabble) |
| **Sweep Bonus** | +40 points for playing all 7 tiles in one turn |
| **Cross-Words** | All newly formed words must be valid |
| **3 Blank Tiles** | Supported (use `?` in rack) — Crossplay has 3 blanks, not 2 |
| **No End Penalty** | Leftover tiles don't subtract from score |
| **100-Tile Bag** | Full tile distribution tracked for Monte Carlo simulation |


## GUI Usage

1. **Place tiles on board** — click a cell, then type a letter (Backspace to undo)
2. **Typing direction** — press Enter for horizontal →, Shift+Enter for vertical ↓
3. **Mystery tiles** — toggle the checkbox to place 0-point blank tiles
4. **Enter your rack** — type up to 7 tiles in the rack field (use `?` for blanks)
5. **Sims/move** — adjust simulation count (default 50; higher = more accurate, slower)
6. **Find Best Move** — runs the engine + Monte Carlo simulation
7. **Browse results** — click any result to see it highlighted on the board; click again to toggle off
8. **Place Move on Board** — applies the highlighted move's tiles to the board and updates your rack
9. **Game tabs** — switch between 3 independent game states
10. **Screen Capture** — captures after a 3-second delay, reads board via OCR
11. **Load Screenshot** — open a saved image file for OCR analysis

## License

For personal/educational use. NYT Crossplay is a trademark of The New York Times Company.

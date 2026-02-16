# NYT Crossplay Bot — Screen-Reading Best-Move Finder

A Python bot that reads your NYT Crossplay game screen via OCR, analyzes the board state, and computes the highest-scoring legal move using a trie-guided move-generation engine. I built this to finally be able to defeat my girlfriend in Crossplay.

## Features

- **Screen Capture + OCR** — captures your screen and reads the 15×15 board + tile rack using OpenCV and Tesseract
- **Load Screenshot** — load a saved screenshot for analysis
- **Manual Board Entry** — click cells in the GUI or type in terminal mode
- **Full Move Engine** — finds all legal placements with cross-word validation
- **Crossplay-Accurate Scoring** — uses official Crossplay tile values (not Scrabble!), bonus squares, and the 40-point Sweep bonus
- **Top 15 Results** — ranked by score with visual board highlighting
- **GUI + CLI** — tkinter desktop GUI or terminal mode

## Quick Start

```bash
# 1. Install dependencies
python bootstrap.py

# 2. Run the bot
python crossplay_bot.py           # GUI mode (recommended)
python crossplay_bot.py --manual  # Terminal mode (no GUI needed)
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
The bot needs a word list file. The setup script will try to create one automatically. For best results, download a **TWL06** or **SOWPODS/NWL23** word list and save it as `dictionary.txt` in the bot directory. Crossplay uses the NASPA Word List 2023 (NWL23).

## How It Works

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
│  GUI Display     │◀────│  Move Scorer │◀────│  Move Engine  │
│  (tkinter)       │     │  (bonuses,   │     │  (anchor-based│
│  highlights best │     │   sweeps,    │     │   generation, │
│  move on board   │     │   cross-wrds)│     │   dictionary) │
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
3. **Cross-Word Validation** — ensures every newly formed perpendicular word is in the dictionary
4. **Scoring** — applies Crossplay tile values, letter/word multipliers, and Sweep bonus
5. **Ranking** — returns top N moves sorted by score

## Crossplay-Specific Rules Implemented

| Rule | Implementation |
|------|---------------|
| **Tile Values** | Custom values (V=6, K=5, W=5, G=4, J=10, etc.) — NOT Scrabble values |
| **Bonus Squares** | DL (2×letter), TL (3×letter), DW (2×word), TW (3×word) |
| **Center Square** | Does NOT double the first word (unlike Scrabble) |
| **Sweep Bonus** | +40 points for playing all 7 tiles in one turn |
| **Cross-Words** | All newly formed words must be valid |
| **3 Blank Tiles** | Supported (use `?` in rack) |
| **No End Penalty** | Leftover tiles don't subtract from score |

## GUI Usage

1. **Place tiles on board** — click a cell, then type a letter (Backspace to remove)
2. **Enter your rack** — type your 7 tiles in the rack field (use `?` for blanks)
3. **Find Best Move** — click the button to compute
4. **Browse results** — click any result to see it highlighted on the board
5. **Screen Capture** — captures after a 3-second delay, reads board automatically
6. **Load Screenshot** — open a saved image file for OCR analysis

## Tips for Best OCR Accuracy

- **Full screen the Crossplay app** before capturing
- **Good lighting / high brightness** helps OCR accuracy
- **Clean board state** — capture when it's clearly your turn
- If OCR misreads, you can manually correct cells in the GUI
- For consistent results, consider using the manual entry or screenshot loading

## File Structure

```
crossplay-bot/
├── crossplay_bot.py    # Main application (engine + GUI + OCR)
├── bootstrap.py        # Dependency installer + dictionary downloader
├── dictionary.txt      # Word list (created by bootstrap.py)
├── requirements.txt    # pip requirements
├── pyproject.toml      # PEP 621 project metadata
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Limitations & Notes

- OCR accuracy depends heavily on screen resolution, app styling, and image quality
- The board bonus layout is approximated from available sources — verify against your game
- Dictionary coverage depends on your word list file; NWL23 gives best accuracy
- The move engine uses trie-guided recursive search; complex board states are handled efficiently
- Blank tile (`?`) support works but increases search time (expands to 26 possible letters)

## License

For personal/educational use. NYT Crossplay is a trademark of The New York Times Company.

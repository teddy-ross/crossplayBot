"""Tkinter GUI for Crossplay Engine."""

from __future__ import annotations

import string
import time

from crossplay.board import Board
from crossplay.constants import BOARD_SIZE, BONUS_GRID, TILE_VALUES
from crossplay.dictionary import Dictionary
from crossplay.engine import MoveEngine
from crossplay.move import Move
from crossplay.ocr import ScreenReader
from crossplay.simulation import evaluate_candidates

# Colour palette
_BG = "#0f0f1a"
_FG = "#e2e2f0"
_ACCENT = "#7c3aed"
_CELL_EMPTY = "#1a1a2e"
_CELL_TILE = "#f5e6c8"
_CELL_TILE_FG = "#1a1a2e"
_BONUS_COLORS = {
    "DL": "#eab308", "TL": "#16a34a",
    "DW": "#2563eb", "TW": "#7c3aed",
    "*": "#3a3a5e", ".": _CELL_EMPTY,
}
_HIGHLIGHT = "#ef4444"
_CELL_SIZE = 38
_BOARD_PX = _CELL_SIZE * BOARD_SIZE


def _draw_board(
    canvas,
    board: Board,
    highlight_tiles: list[tuple[str, int, int]] | None = None,
    blank_positions: set[tuple[int, int]] | None = None,
):
    """Draw the board on the canvas, highlighting placed tiles if given."""
    canvas.delete("all")
    ht_map: dict[tuple[int, int], str] = {}
    if highlight_tiles:
        ht_map = {(r, c): letter for letter, r, c in highlight_tiles}
    blanks = blank_positions or set()

    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            x1 = c * _CELL_SIZE + 1
            y1 = r * _CELL_SIZE + 1
            x2 = x1 + _CELL_SIZE
            y2 = y1 + _CELL_SIZE
            cx = x1 + _CELL_SIZE // 2
            cy = y1 + _CELL_SIZE // 2

            letter = board.get(r, c)
            is_hl = (r, c) in ht_map
            is_board_blank = letter is not None and letter.islower()

            # Determine colours
            if is_hl:
                bg, fg, outline, olw = _HIGHLIGHT, "#fff", "#fca", 2
            elif letter and is_board_blank:
                bg, fg, outline, olw = "#d4c4a8", _CELL_TILE_FG, "#7c3aed", 2
            elif letter:
                bg, fg, outline, olw = _CELL_TILE, _CELL_TILE_FG, "#0a0a14", 1
            else:
                bonus = BONUS_GRID[r][c]
                bg = _BONUS_COLORS.get(bonus, _CELL_EMPTY)
                fg, outline, olw = "#fff", "#0a0a14", 1

            canvas.create_rectangle(x1, y1, x2, y2, fill=bg, outline=outline, width=olw)

            # Draw letter (either existing or highlighted placement)
            display = letter.upper() if letter else ht_map.get((r, c))
            if display:
                canvas.create_text(cx, cy - 2, text=display,
                                   font=("Helvetica", 14, "bold"), fill=fg)
                pts = 0 if (is_board_blank or (r, c) in blanks) else TILE_VALUES.get(display, 0)
                sub_fg = "#fcc" if is_hl else "#888"
                canvas.create_text(x2 - 6, y2 - 5, text=str(pts),
                                   font=("Helvetica", 7), fill=sub_fg)
            else:
                bonus = BONUS_GRID[r][c]
                if bonus != ".":
                    _display_labels = {"DL": "2L", "TL": "3L", "DW": "2W", "TW": "3W", "*": "★"}
                    label = _display_labels.get(bonus, bonus)
                    canvas.create_text(cx, cy, text=label,
                                       font=("Helvetica", 8, "bold"),
                                       fill="#fff" if bonus != "*" else "#555")


def run_gui(dictionary: Dictionary) -> None:
    """Launch the GUI."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        import logging
        logging.getLogger("crossplay").error("tkinter not available -- use --manual mode.")
        return

    root = tk.Tk()
    root.title("Crossplay Engine -- Best Move Finder")
    root.configure(bg=_BG)

    engine = MoveEngine(dictionary)
    selected_cell: list[tuple[int, int] | None] = [None]
    highlighted_idx: list[int | None] = [None]  # track currently shown move
    typing_direction: list[str] = ["H"]  # "H" = right, "V" = down

    # Per-tab game state
    NUM_TABS = 3
    game_states: list[dict] = [
        {"board": Board(), "rack": "", "results": [], "highlighted": None}
        for _ in range(NUM_TABS)
    ]
    active_tab: list[int] = [0]
    board = game_states[0]["board"]
    results: list[Move] = game_states[0]["results"]

    # layout

    main_frame = tk.Frame(root, bg=_BG)
    main_frame.pack(padx=15, pady=15)

    tk.Label(main_frame, text="CROSSPLAY ENGINE",
             font=("Helvetica", 22, "bold"), fg=_ACCENT, bg=_BG).pack(pady=(0, 10))

    # Tab bar
    tab_bar = tk.Frame(main_frame, bg=_BG)
    tab_bar.pack(fill="x", pady=(0, 8))
    tab_buttons: list[tk.Label] = []
    _TAB_ACTIVE_BG = "#7c3aed"
    _TAB_INACTIVE_BG = "#1a1a2e"
    _TAB_ACTIVE_FG = "#fff"
    _TAB_INACTIVE_FG = "#888"

    def _save_current_tab():
        """Persist current UI state into the active tab's slot."""
        idx = active_tab[0]
        game_states[idx]["rack"] = rack_var.get()
        game_states[idx]["highlighted"] = highlighted_idx[0]

    def _switch_tab(idx: int):
        nonlocal board, results
        if idx == active_tab[0]:
            return
        _save_current_tab()
        active_tab[0] = idx
        board = game_states[idx]["board"]
        results = game_states[idx]["results"]
        rack_var.set(game_states[idx]["rack"])
        highlighted_idx[0] = game_states[idx]["highlighted"]
        selected_cell[0] = None
        # Refresh results list
        results_list.delete(0, tk.END)
        for m in results:
            sweep = " *SWEEP" if m.is_sweep else ""
            arrow = ">" if m.direction == "H" else "v"
            results_list.insert(
                tk.END,
                f"{m.score:>3}pts  {m.word:<12} ({m.row},{m.col}){arrow}{sweep}",
            )
        if highlighted_idx[0] is not None and 0 <= highlighted_idx[0] < len(results):
            results_list.selection_set(highlighted_idx[0])
            _highlight_result(highlighted_idx[0])
        else:
            _draw_board(canvas, board)
        _update_tab_styles()
        status_var.set(f"Switched to Game {idx + 1}.")

    def _update_tab_styles():
        for i, btn in enumerate(tab_buttons):
            if i == active_tab[0]:
                btn.configure(bg=_TAB_ACTIVE_BG, fg=_TAB_ACTIVE_FG)
            else:
                btn.configure(bg=_TAB_INACTIVE_BG, fg=_TAB_INACTIVE_FG)

    for i in range(NUM_TABS):
        lbl = tk.Label(
            tab_bar, text=f"  Game {i + 1}  ",
            font=("Helvetica", 11, "bold"), cursor="hand2",
            bg=_TAB_ACTIVE_BG if i == 0 else _TAB_INACTIVE_BG,
            fg=_TAB_ACTIVE_FG if i == 0 else _TAB_INACTIVE_FG,
            padx=12, pady=4,
        )
        lbl.pack(side="left", padx=(0, 4))
        lbl.bind("<Button-1>", lambda e, idx=i: _switch_tab(idx))
        tab_buttons.append(lbl)

    board_frame = tk.Frame(main_frame, bg=_BG)
    board_frame.pack()

    canvas = tk.Canvas(board_frame, width=_BOARD_PX + 2, height=_BOARD_PX + 2,
                       bg="#0a0a14", highlightthickness=0)
    canvas.pack(side="left", padx=(0, 15))

    side = tk.Frame(board_frame, bg=_BG, width=320)
    side.pack(side="left", fill="y")

    # Rack
    tk.Label(side, text="YOUR RACK", font=("Helvetica", 11, "bold"),
             fg=_FG, bg=_BG).pack(anchor="w")
    rack_var = tk.StringVar()

    def _limit_rack(*_args):
        val = rack_var.get()
        if len(val) > 7:
            rack_var.set(val[:7])

    rack_var.trace_add("write", _limit_rack)
    rack_entry = tk.Entry(side, textvariable=rack_var, font=("Courier", 18, "bold"),
             width=10, bg="#1a1a2e", fg=_FG, insertbackground=_FG,
             relief="flat", justify="center")
    rack_entry.pack(fill="x", pady=(2, 10))
    tk.Label(side, text="Use ? for blank tiles",
             font=("Helvetica", 9), fg="#666", bg=_BG).pack(anchor="w")

    # Mystery tile toggle
    blank_mode_var = tk.BooleanVar(value=False)
    blank_mode_cb = tk.Checkbutton(
        side, text="Mystery Tile (0 pts)",
        variable=blank_mode_var,
        font=("Helvetica", 10, "bold"), fg="#7c3aed", bg=_BG,
        selectcolor="#1a1a2e", activebackground=_BG, activeforeground="#7c3aed",
        cursor="hand2",
    )
    blank_mode_cb.pack(anchor="w", pady=(5, 2))

    # Simulation trial count
    sim_count_frame = tk.Frame(side, bg=_BG)
    sim_count_frame.pack(anchor="w", pady=(0, 10))
    tk.Label(sim_count_frame, text="Sims/move:",
             font=("Helvetica", 9), fg="#888", bg=_BG).pack(side="left")
    sim_count_var = tk.StringVar(value="50")
    sim_count_entry = tk.Entry(sim_count_frame, textvariable=sim_count_var,
                                font=("Courier", 10), width=5,
                                bg="#1a1a2e", fg=_FG, insertbackground=_FG,
                                relief="flat")
    sim_count_entry.pack(side="left", padx=(4, 0))

    def _make_button(parent, text, bg_color, fg_color, command, pady=(0, 0)):
        """Create a styled button using a Frame+Label to bypass macOS Aqua theming."""
        frame = tk.Frame(parent, bg=bg_color, cursor="hand2")
        frame.pack(fill="x", pady=pady)
        label = tk.Label(frame, text=text, bg=bg_color, fg=fg_color,
                         font=("Helvetica", 11, "bold"), pady=8)
        label.pack(fill="x")
        for widget in (frame, label):
            widget.bind("<Button-1>", lambda e: command())
            widget.bind("<Enter>", lambda e, f=frame, l=label: (
                f.configure(bg=_lighten(bg_color)),
                l.configure(bg=_lighten(bg_color)),
            ))
            widget.bind("<Leave>", lambda e, f=frame, l=label, c=bg_color: (
                f.configure(bg=c),
                l.configure(bg=c),
            ))
        return frame

    def _lighten(hex_color: str, amount: int = 30) -> str:
        """Lighten a hex color for hover effect."""
        r = min(255, int(hex_color[1:3], 16) + amount)
        g = min(255, int(hex_color[3:5], 16) + amount)
        b = min(255, int(hex_color[5:7], 16) + amount)
        return f"#{r:02x}{g:02x}{b:02x}"

    # Status
    status_var = tk.StringVar(value="Click board cells to place tiles, then Find Best Move.")
    status_label = tk.Label(main_frame, textvariable=status_var,
                            font=("Helvetica", 10), fg="#888", bg=_BG)

    # callbacks

    def refresh():
        _draw_board(canvas, board)

    def find_moves():
        rack_str = rack_var.get().upper().strip()
        if not rack_str:
            messagebox.showwarning("No Rack", "Enter your tile rack first!")
            return
        status_var.set("Searching...")
        root.update()

        t0 = time.time()
        best = engine.find_best_moves(board, list(rack_str), top_n=15,
                                      use_leave_eval=True)

        # Monte Carlo simulation on top candidates
        if best:
            try:
                n_sims = max(10, min(500, int(sim_count_var.get())))
            except ValueError:
                n_sims = 50
            sim_candidates = best[:10]
            status_var.set(
                f"Simulating {len(sim_candidates)} moves × {n_sims} trials..."
            )
            root.update()

            def _sim_progress(done, total):
                status_var.set(
                    f"Simulating move {done}/{total}..."
                )
                root.update()

            sim_candidates = evaluate_candidates(
                engine, board, sim_candidates, list(rack_str),
                n_simulations=n_sims,
                progress_callback=_sim_progress,
            )
            best = sim_candidates

        elapsed_total = time.time() - t0

        nonlocal results
        results = list(best)
        game_states[active_tab[0]]["results"] = results
        highlighted_idx[0] = None
        results_list.delete(0, tk.END)

        if not best:
            status_var.set("No valid moves found.")
            return

        for m in best:
            sweep = " *SWEEP" if m.is_sweep else ""
            arrow = ">" if m.direction == "H" else "v"
            sim_eq = f"  sim{m.sim_equity:>+6.1f}" if m.sim_equity is not None else ""
            results_list.insert(
                tk.END,
                f"{m.score:>3}pts{sim_eq}  {m.word:<9} ({m.row},{m.col}){arrow}{sweep}",
            )
        results_list.selection_set(0)
        _highlight_result(0)
        if best[0].sim_equity is not None:
            status_var.set(
                f"Found {len(best)} moves in {elapsed_total:.1f}s  |  "
                f"Best: {best[0].word} = {best[0].score}pts  "
                f"sim_eq={best[0].sim_equity:+.1f}"
            )
        else:
            status_var.set(
                f"Found {len(best)} moves in {elapsed_total:.1f}s  |  "
                f"Best: {best[0].word} = {best[0].score} pts"
            )

    def _highlight_result(idx: int):
        if 0 <= idx < len(results):
            m = results[idx]
            _draw_board(canvas, board, m.tiles_used, m.blank_positions)

    def on_result_select(event):
        sel = results_list.curselection()
        if sel:
            idx = sel[0]
            if highlighted_idx[0] == idx:
                # Same item clicked again -- toggle off
                highlighted_idx[0] = None
                results_list.selection_clear(0, tk.END)
                refresh()
            else:
                # Show this move on the board
                highlighted_idx[0] = idx
                _highlight_result(idx)

    def place_move():
        """Place the currently highlighted move onto the board."""
        idx = highlighted_idx[0]
        if idx is None or idx < 0 or idx >= len(results):
            status_var.set("Select a move from the results list first.")
            return
        m = results[idx]
        for letter, r, c in m.tiles_used:
            if (r, c) in m.blank_positions:
                board.set(r, c, letter.lower())  # mystery / blank
            else:
                board.set(r, c, letter)
        # Remove used tiles from rack
        rack_letters = list(rack_var.get().upper())
        for letter, _r, _c, is_blank in (
            (lt, rr, cc, (rr, cc) in m.blank_positions)
            for lt, rr, cc in m.tiles_used
        ):
            tile = "?" if is_blank else letter
            if tile in rack_letters:
                rack_letters.remove(tile)
        rack_var.set("".join(rack_letters))
        # Clear results since board changed
        highlighted_idx[0] = None
        results.clear()
        game_states[active_tab[0]]["results"] = results
        results_list.delete(0, tk.END)
        refresh()
        status_var.set(f"Placed {m.word} ({m.score} pts) on the board.")

    def clear_board():
        nonlocal board, results
        board = Board()
        game_states[active_tab[0]]["board"] = board
        results = []
        game_states[active_tab[0]]["results"] = results
        highlighted_idx[0] = None
        results_list.delete(0, tk.END)
        refresh()
        status_var.set("Board cleared.")

    def capture_screen():
        reader = ScreenReader()
        if not reader.is_available or not reader.mss:
            messagebox.showerror(
                "Missing Dependencies",
                "Screen capture requires:\n"
                "  pip install mss opencv-python pytesseract numpy\n\n"
                "Also install Tesseract OCR:\n"
                "  brew install tesseract  (macOS)\n"
                "  apt install tesseract-ocr  (Linux)",
            )
            return
        status_var.set("Capturing screen in 3 seconds...")
        root.update()
        time.sleep(3)
        try:
            img = reader.capture_screen()
            nonlocal board
            board, rack = reader.read_board_from_image(img)
            game_states[active_tab[0]]["board"] = board
            rack_var.set("".join(rack))
            refresh()
            status_var.set(
                f"Board read -- {board.count_tiles()} tiles, rack: {''.join(rack)}"
            )
        except Exception as exc:
            messagebox.showerror("Capture Error", str(exc))

    def load_image():
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")],
        )
        if not path:
            return
        reader = ScreenReader()
        if not reader.is_available:
            messagebox.showerror("Missing Dependencies",
                                 "OCR requires opencv-python, pytesseract, numpy.")
            return
        from PIL import Image
        img = Image.open(path)
        nonlocal board
        board, rack = reader.read_board_from_image(img)
        game_states[active_tab[0]]["board"] = board
        rack_var.set("".join(rack))
        refresh()
        status_var.set(f"Board loaded from image  |  Rack: {''.join(rack)}")

    # buttons

    _make_button(side, "FIND BEST MOVE", "#7c3aed", "#e9d5ff",
                 find_moves, pady=(10, 5))
    _make_button(side, "Place Move on Board", "#065f46", "#6ee7b7",
                 place_move, pady=(0, 5))
    _make_button(side, "Clear Board", "#4a1a2e", "#f9a8b8",
                 clear_board, pady=(0, 10))
    _make_button(side, "Capture Screen (3s delay)", "#134e4a", "#99f6e4",
                 capture_screen, pady=(0, 5))
    _make_button(side, "Load Screenshot", "#1e3a5f", "#93c5fd",
                 load_image, pady=(0, 15))

    # Results list
    tk.Label(side, text="TOP MOVES", font=("Helvetica", 11, "bold"),
             fg=_FG, bg=_BG).pack(anchor="w")
    results_list = tk.Listbox(side, font=("Courier", 10), height=12,
                               bg="#1a1a2e", fg=_FG, selectbackground=_ACCENT,
                               selectforeground="#fff", relief="flat",
                               activestyle="none")
    results_list.pack(fill="both", expand=True, pady=(2, 10))
    results_list.bind("<<ListboxSelect>>", on_result_select)

    status_label.pack(pady=(10, 0))

    # help label (in sidebar, below results)
    tk.Label(
        side,
        text=(
            "Instructions:\n"
            "  Game 1/2/3 tabs to track multiple games\n"
            "  Click a cell then type a letter to place\n"
            "  Enter = type → horizontal\n"
            "  Shift+Enter = type ↓ vertical\n"
            "  Toggle 'Mystery Tile' for 0-point blanks\n"
            "  Enter rack letters above (? for blanks)\n"
            "  Click 'Find Best Move' to compute\n"
            "  Click results to highlight on board\n"
            "  'Place Move' to apply highlighted move"
        ),
        font=("Helvetica", 9), fg="#555", bg=_BG, justify="left",
    ).pack(pady=(5, 0), anchor="w")

    # click-to-place

    def on_canvas_click(event):
        col = (event.x - 1) // _CELL_SIZE
        row = (event.y - 1) // _CELL_SIZE
        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            selected_cell[0] = (row, col)
            root.focus_set()  # pull focus away from rack entry
            mode = " [MYSTERY]" if blank_mode_var.get() else ""
            arrow = "→" if typing_direction[0] == "H" else "↓"
            status_var.set(f"Selected ({row},{col}){mode} {arrow} -- type a letter, Enter/Shift+Enter to change direction.")

    canvas.bind("<Button-1>", on_canvas_click)

    def on_rack_focus_in(event):
        selected_cell[0] = None
        status_var.set("Typing in rack...")

    rack_entry.bind("<FocusIn>", on_rack_focus_in)

    def on_sim_focus_in(event):
        selected_cell[0] = None

    sim_count_entry.bind("<FocusIn>", on_sim_focus_in)

    def on_key(event):
        if event.widget in (rack_entry, sim_count_entry):
            return
        if selected_cell[0] is None:
            return
        r, c = selected_cell[0]
        # Enter = horizontal, Shift+Enter = vertical
        if event.keysym == "Return":
            if event.state & 0x1:  # Shift held
                typing_direction[0] = "V"
                status_var.set(f"Direction: ↓ vertical  |  Cell ({r},{c})")
            else:
                typing_direction[0] = "H"
                status_var.set(f"Direction: → horizontal  |  Cell ({r},{c})")
            return
        if event.char and event.char.upper() in string.ascii_uppercase:
            ch = event.char.upper()
            if blank_mode_var.get():
                board.set(r, c, ch.lower())  # lowercase = mystery/blank tile (0 pts)
            else:
                board.set(r, c, ch)
            refresh()
            tag = " (mystery)" if blank_mode_var.get() else ""
            arrow = "→" if typing_direction[0] == "H" else "↓"
            # Advance cursor in the current typing direction
            if typing_direction[0] == "H":
                nc = c + 1
                if nc < BOARD_SIZE:
                    selected_cell[0] = (r, nc)
                    status_var.set(f"Placed {ch}{tag} at ({r},{c}) {arrow}  Now at ({r},{nc}).")
            else:
                nr = r + 1
                if nr < BOARD_SIZE:
                    selected_cell[0] = (nr, c)
                    status_var.set(f"Placed {ch}{tag} at ({r},{c}) {arrow}  Now at ({nr},{c}).")
        elif event.keysym == "Delete":
            board.set(r, c, None)
            refresh()
            status_var.set(f"Removed tile at ({r},{c}).")
        elif event.keysym == "BackSpace":
            # If current cell is empty, step back first then delete
            if board.is_empty(r, c):
                if typing_direction[0] == "H" and c > 0:
                    c -= 1
                    selected_cell[0] = (r, c)
                elif typing_direction[0] == "V" and r > 0:
                    r -= 1
                    selected_cell[0] = (r, c)
            board.set(r, c, None)
            refresh()
            arrow = "→" if typing_direction[0] == "H" else "↓"
            status_var.set(f"Removed tile at ({r},{c}) {arrow}")

    root.bind("<Key>", on_key)

    refresh()
    root.mainloop()

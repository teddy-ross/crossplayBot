"""Screen reader — OCR-based board and rack detection."""

from __future__ import annotations

import logging

from crossplay.board import Board
from crossplay.constants import BOARD_SIZE

log = logging.getLogger("crossplay")


class ScreenReader:
    """Reads the Crossplay board from a screenshot using OpenCV + Tesseract."""

    def __init__(self):
        self.mss = self._try_import("mss")
        self.cv2 = self._try_import("cv2", pip_name="opencv-python")
        self.pytesseract = self._try_import("pytesseract")
        self.np = self._try_import("numpy")

    @staticmethod
    def _try_import(name: str, pip_name: str | None = None):
        try:
            return __import__(name)
        except ImportError:
            log.error("'%s' not installed.  Run: pip install %s", name, pip_name or name)
            return None

    @property
    def is_available(self) -> bool:
        return all(x is not None for x in (self.cv2, self.pytesseract, self.np))

    # capture

    def capture_screen(self, region: dict | None = None):
        """Grab a screenshot; returns a PIL Image."""
        if not self.mss:
            raise RuntimeError("mss not available -- install with: pip install mss")
        from PIL import Image

        with self.mss.mss() as sct:
            shot = sct.grab(region or sct.monitors[0])
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    # read board from image

    def read_board_from_image(self, img) -> tuple[Board, list[str]]:
        """
        Read the Crossplay board and rack from a PIL Image.
        Returns ``(Board, rack_letters)``.
        """
        if not self.is_available:
            raise RuntimeError("OCR dependencies not available (cv2, pytesseract, numpy)")

        cv2 = self.cv2
        np = self.np

        img_array = np.array(img)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

        board = Board()

        # 1. Detect board region
        board_rect = self._find_board_region(img_bgr, gray)
        if board_rect is None:
            log.warning("Board region not detected -- falling back to heuristic crop.")
            h, w = img_bgr.shape[:2]
            size_px = int(min(h, w) * 0.7)
            bx = (w - size_px) // 2
            by = int(h * 0.08)
            board_rect = (bx, by, size_px, size_px)

        bx, by, bw, bh = board_rect
        cell_w = bw / BOARD_SIZE
        cell_h = bh / BOARD_SIZE
        log.info("Board at (%d,%d) size %dx%d  |  cell %.1fx%.1f px", bx, by, bw, bh, cell_w, cell_h)

        # 2. Read each cell
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                cx = int(bx + col * cell_w)
                cy = int(by + row * cell_h)
                cw = int(cell_w)
                ch = int(cell_h)
                pad = max(2, int(min(cw, ch) * 0.1))

                cell_bgr = img_bgr[cy + pad:cy + ch - pad, cx + pad:cx + cw - pad]
                if cell_bgr.size == 0:
                    continue

                cell_hsv = hsv[cy + pad:cy + ch - pad, cx + pad:cx + cw - pad]
                if self._cell_has_tile(cell_bgr, cell_hsv):
                    cell_gray = gray[cy + pad:cy + ch - pad, cx + pad:cx + cw - pad]
                    letter = self._ocr_cell(cell_bgr, cell_gray)
                    if letter:
                        board.set(row, col, letter)

        # 3. Read the rack
        rack = self._read_rack(img_bgr, gray, hsv, board_rect)
        return board, rack

    # helpers

    def _find_board_region(self, img_bgr, gray) -> tuple[int, int, int, int] | None:
        cv2 = self.cv2
        edges = cv2.Canny(gray, 50, 150)
        edges = cv2.dilate(edges, None, iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = img_bgr.shape[:2]
        min_area = (min(h, w) * 0.3) ** 2

        best = None
        best_area = 0.0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > min_area:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect = cw / ch if ch > 0 else 0
                if 0.7 < aspect < 1.3 and area > best_area:
                    best = (x, y, cw, ch)
                    best_area = area
        return best

    def _cell_has_tile(self, cell_bgr, cell_hsv) -> bool:
        np = self.np
        mean_val = float(np.mean(cell_hsv[:, :, 2]))
        mean_sat = float(np.mean(cell_hsv[:, :, 1]))
        # Tiles are light & desaturated (beige/cream); bonus squares are saturated.
        return mean_val > 150 and mean_sat < 80

    def _ocr_cell(self, cell_bgr, cell_gray) -> str | None:
        """Run single-character OCR on a cell image."""
        return self._ocr_single_letter(cell_gray)

    def _ocr_single_letter(self, gray_region) -> str | None:
        """Threshold, resize, and OCR a grayscale region for one letter."""
        cv2 = self.cv2
        pytesseract = self.pytesseract
        _, thresh = cv2.threshold(gray_region, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        resized = cv2.resize(thresh, (60, 60), interpolation=cv2.INTER_CUBIC)
        if cv2.mean(resized)[0] < 128:
            resized = cv2.bitwise_not(resized)
        config = "--psm 10 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        text = pytesseract.image_to_string(resized, config=config).strip()
        if text and len(text) == 1 and text.isalpha():
            return text.upper()
        return None

    def _read_rack(self, img_bgr, gray, hsv, board_rect) -> list[str]:
        """Locate and OCR the 7-tile rack below the board."""
        cv2 = self.cv2
        np = self.np

        bx, by, bw, bh = board_rect
        h, w = img_bgr.shape[:2]

        rack_y = by + bh + int(bh * 0.05)
        rack_h = int(bh * 0.08)
        rack_x = bx + int(bw * 0.1)
        rack_w = int(bw * 0.8)

        if rack_y + rack_h > h:
            rack_y = by + bh
            rack_h = min(int(bh * 0.06), h - rack_y)

        rack: list[str] = []
        tile_w = rack_w // 7

        for i in range(7):
            tx = rack_x + i * tile_w
            if tx + tile_w > w or rack_y + rack_h > h:
                break
            cell_gray = gray[rack_y:rack_y + rack_h, tx:tx + tile_w]
            if cell_gray.size == 0:
                continue
            letter = self._ocr_single_letter(cell_gray)
            if letter:
                rack.append(letter)
        return rack

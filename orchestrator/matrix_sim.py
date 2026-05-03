"""Tkinter Canvas üstünde 16×16 LED matrisi görüntüleyicisi.

`update_pixels(pixels)` çağrıldığında 256 hücrenin rengini günceller.
Her hücre küçük bir kare; aralarda 2 piksel boşluk LED parıltısı hissi verir.
"""
from __future__ import annotations

import tkinter as tk

W, H = 32, 32


class MatrixView(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        cell_size: int = 13,
        padding: int = 1,
        bg: str = "#06060a",
    ) -> None:
        super().__init__(parent, bg=bg)
        self.cell_size = cell_size
        self.padding = padding
        size = (cell_size + padding) * W + padding
        self.canvas = tk.Canvas(
            self,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
        )
        self.canvas.pack(padx=6, pady=6)

        self.cells: list[int] = []
        for y in range(H):
            for x in range(W):
                x0 = padding + x * (cell_size + padding)
                y0 = padding + y * (cell_size + padding)
                rid = self.canvas.create_rectangle(
                    x0,
                    y0,
                    x0 + cell_size,
                    y0 + cell_size,
                    fill="#000000",
                    outline="",
                )
                self.cells.append(rid)

        # son frame'in renkleri — gereksiz canvas çağrısını kesmek için cache
        self._last: list[tuple[int, int, int]] = [(-1, -1, -1)] * (W * H)

    def update_pixels(self, pixels: list[tuple[int, int, int]]) -> None:
        last = self._last
        for i, color in enumerate(pixels):
            if color == last[i]:
                continue
            r, g, b = color
            self.canvas.itemconfig(self.cells[i], fill=f"#{r:02x}{g:02x}{b:02x}")
            last[i] = color

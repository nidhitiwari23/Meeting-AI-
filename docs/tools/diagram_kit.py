"""Small drawing toolkit for the documentation diagrams: dark 'MeetingAI' look (navy, violet, blue) on a rounded panel."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon  # noqa: E402

_have = {f.name for f in fm.fontManager.ttflist}
FONT = "Segoe UI" if "Segoe UI" in _have else "DejaVu Sans"
plt.rcParams["font.family"] = [FONT, "DejaVu Sans"]

OUT = Path(__file__).resolve().parents[1] / "images" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

# fill, border, accent-text
PAL = {
    "violet": ("#221C5C", "#8B5CF6", "#D4C8FF"),
    "blue": ("#10285C", "#3B82F6", "#A9CCFF"),
    "teal": ("#0B3238", "#14B8A6", "#7DF0DF"),
    "amber": ("#3F2D0B", "#F59E0B", "#FFD978"),
    "green": ("#0C3626", "#34D399", "#8CF0C6"),
    "red": ("#401819", "#F87171", "#FFB4B4"),
    "pink": ("#401537", "#F472B6", "#FFB7DE"),
    "grey": ("#1C2347", "#7C86B8", "#D2D7F5"),
}
BG0, BG1 = "#060A1C", "#101852"
WHITE = "#F4F6FF"
MUTED = "#9AA5D9"
LINE = "#8F99D6"


class Diagram:
    def __init__(self, h, title, subtitle=None, w=100, fig_w=11.5):
        self.w, self.h = w, h
        self.fig, self.ax = plt.subplots(figsize=(fig_w, fig_w * h / w))
        self.fig.subplots_adjust(0, 0, 1, 1)
        ax = self.ax
        ax.set_xlim(0, w)
        ax.set_ylim(0, h)
        ax.axis("off")
        panel = FancyBboxPatch((0.4, 0.4), w - 0.8, h - 0.8, boxstyle="round,pad=0,rounding_size=2.2", fc=BG0, ec="#2A3380", lw=1.4, zorder=0)
        ax.add_patch(panel)
        cmap = LinearSegmentedColormap.from_list("bg", [BG0, BG1, "#150F46"])
        xx, yy = np.meshgrid(np.linspace(0, 1, 200), np.linspace(0, 1, 120))
        im = ax.imshow((xx * 0.55 + (1 - yy) * 0.45), extent=(0, w, 0, h), cmap=cmap, zorder=0.1, aspect="auto", alpha=0.95)
        im.set_clip_path(panel)
        for cx, cy, r, col, a in ((8, h - 6, 22, "#7C3AED", 0.10), (w - 6, 6, 24, "#2563EB", 0.10), (w * 0.55, h * 0.5, 30, "#6D4AFF", 0.04)):
            g = Circle((cx, cy), r, fc=col, ec="none", alpha=a, zorder=0.2)
            ax.add_patch(g)
            g.set_clip_path(panel)
        # title
        ax.add_patch(FancyBboxPatch((3.2, h - 7.3), 0.9, 4.4, boxstyle="round,pad=0,rounding_size=0.4", fc="#8B5CF6", ec="none", zorder=3))
        ax.text(5.2, h - 4.0, title, color=WHITE, fontsize=15, fontweight="bold", va="center", ha="left", zorder=5)
        if subtitle:
            ax.text(5.2, h - 7.7, subtitle, color=MUTED, fontsize=8.3, va="center", ha="left", zorder=5)

    # ------------------------------------------------------------------ shapes
    def lane(self, x, y, w, h, label, c="grey", fs=9.5, label_pos="top"):
        f, e, a = PAL[c]
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.6", fc=e, ec=e, lw=1.1, alpha=0.10, zorder=1))
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.6", fc="none", ec=e, lw=1.1, ls=(0, (4, 3)), alpha=0.65, zorder=1.1))
        self.ax.text(x + 1.6, (y + h - 2.0) if label_pos == "top" else (y + 1.7), label.upper(), color=a, fontsize=fs - 1.8, fontweight="bold", va="center", ha="left", zorder=5)

    def node(self, x, y, w, h, title, sub=None, c="violet", num=None, fs=10.5, sub_fs=None, bold=True, align="center"):
        f, e, a = PAL[c]
        ax = self.ax
        ax.add_patch(FancyBboxPatch((x + 0.35, y - 0.4), w, h, boxstyle="round,pad=0,rounding_size=1.1", fc="#000000", ec="none", alpha=0.35, zorder=2))
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.1", fc=f, ec=e, lw=1.7, zorder=3))
        ax.add_patch(FancyBboxPatch((x + 0.5, y + h - 0.55), w - 1.0, 0.28, boxstyle="round,pad=0,rounding_size=0.14", fc=e, ec="none", alpha=0.9, zorder=3.2))
        tx = x + w / 2 if align == "center" else x + 1.4
        ha = "center" if align == "center" else "left"
        if sub:
            nlines = sub.count("\n") + 1
            ax.text(tx, y + h - 2.1, title, color=WHITE, fontsize=fs, fontweight="bold" if bold else "normal", va="center", ha=ha, zorder=5)
            ax.text(tx, y + (h - 3.4) / 2 + 0.1, sub, color=a, fontsize=sub_fs or fs - 1.9, va="center", ha=ha, zorder=5, linespacing=1.3)
        else:
            ax.text(tx, y + h / 2 - 0.1, title, color=WHITE, fontsize=fs, fontweight="bold" if bold else "normal", va="center", ha=ha, zorder=5, linespacing=1.3)
        if num is not None:
            ax.add_patch(Circle((x, y + h), 1.55, fc=e, ec=BG0, lw=1.4, zorder=6))
            ax.text(x, y + h, str(num), color="#0A0F2C", fontsize=8.5, fontweight="bold", va="center", ha="center", zorder=7)

    def pill(self, x, y, w, h, text, c="violet", fs=8, bold=True):
        f, e, a = PAL[c]
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=%.2f" % (h / 2), fc=f, ec=e, lw=1.2, zorder=3))
        self.ax.text(x + w / 2, y + h / 2 - 0.05, text, color=WHITE, fontsize=fs, fontweight="bold" if bold else "normal", va="center", ha="center", zorder=5)

    def diamond(self, cx, cy, w, h, text, c="amber", fs=9):
        f, e, a = PAL[c]
        pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
        self.ax.add_patch(Polygon(pts, closed=True, fc=f, ec=e, lw=1.8, zorder=3, joinstyle="round"))
        self.ax.text(cx, cy, text, color=WHITE, fontsize=fs, fontweight="bold", va="center", ha="center", zorder=5, linespacing=1.25)

    def label(self, x, y, text, c="#B9C2F2", fs=8.5, ha="left", bold=False, rot=0):
        self.ax.text(x, y, text, color=c, fontsize=fs, ha=ha, va="center", fontweight="bold" if bold else "normal", zorder=5, rotation=rot, linespacing=1.3)

    # ------------------------------------------------------------------ connectors
    def edge(self, pts, label=None, c=LINE, lw=1.9, dashed=False, arrow=True, lseg=None, loff=(0, 0), lfs=8):
        ax = self.ax
        xs, ys = zip(*pts)
        ls = (0, (5, 3)) if dashed else "-"
        end = len(pts) - 1 if arrow else len(pts)
        if arrow:
            ax.plot(xs[:-1], ys[:-1], color=c, lw=lw, ls=ls, zorder=2.5, solid_capstyle="round")
            ax.annotate("", xy=pts[-1], xytext=pts[-2], arrowprops=dict(arrowstyle="-|>", color=c, lw=lw, mutation_scale=15, shrinkA=0, shrinkB=0), zorder=2.6)
        else:
            ax.plot(xs, ys, color=c, lw=lw, ls=ls, zorder=2.5)
        if label:
            i = lseg if lseg is not None else max(range(len(pts) - 1), key=lambda k: abs(pts[k + 1][0] - pts[k][0]) + abs(pts[k + 1][1] - pts[k][1]))
            mx, my = (pts[i][0] + pts[i + 1][0]) / 2 + loff[0], (pts[i][1] + pts[i + 1][1]) / 2 + loff[1]
            ax.text(mx, my, label, color=WHITE, fontsize=lfs, ha="center", va="center", zorder=8, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.28,rounding_size=0.6", fc="#151D5C", ec=c, lw=0.9))

    def save(self, name):
        self.fig.savefig(OUT / f"{name}.png", dpi=210, transparent=True)
        plt.close(self.fig)
        print("drawn", name)

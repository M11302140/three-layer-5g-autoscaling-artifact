#!/usr/bin/env python3
"""fig_layers_timeline.pdf -- three-layer position model (IEEE single column, 3.4 in wide).

Top: containment / parallel relation  VY || UP, UP subset of WK.
Bottom: one layer's timeline: ready lead h_l, teardown lead d_l, horizon H_l = h_l + g (UP, VY),
exposure window W_l (= H_l) used for release, one replenish and one release event.
2026-10-24 R68 (spec §4.116 item 1b): the WK horizon chains the two leads, H_WK = h_WK + h_UP + g = 120 + 30 + 30 = 180 s
(daemon controller.go:306), because a slot starts its own 30 s lead only once its worker is ready; inset table and caption text updated.
Numbers from docs/paper/01-method.md section 1 and 2.2 (p90 leads, g = 30 s).
Run: nice -n 19 taskset -c 13 python3 fig_layers_timeline.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fig_layers_timeline.pdf")

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "Nimbus Roman", "DejaVu Serif"],
    "font.size": 8,
    "mathtext.fontset": "stix",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})
INK, MUTED = "#222222", "#555555"
C_VY, C_UP, C_WK = "#2F6FB3", "#C06A20", "#3B8A5A"
TINT_VY, TINT_UP, TINT_WK = "#E4EDF8", "#FBEBDD", "#E3F1E8"

W, H = 3.4, 2.65
fig = plt.figure(figsize=(W, H))

def rbox(ax, x, y, w, h, text, fill, edge, fs=8, lw=0.8, pad=0.02, color=INK, weight="normal"):
    ax.add_patch(FancyBboxPatch((x + pad, y + pad), w - 2 * pad, h - 2 * pad,
                                boxstyle=f"round,pad={pad},rounding_size=0.05",
                                fc=fill, ec=edge, lw=lw, zorder=3))
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
                weight=weight, color=color, zorder=4)

# ------------------------------------------------------------------ top panel: relation
TOP = 0.314
ax = fig.add_axes([0, 1 - TOP, 1, TOP])
ax.set_xlim(0, W); ax.set_ylim(0, TOP * H); ax.set_aspect("equal"); ax.axis("off")
ax.text(W / 2, 0.74, r"VY $\parallel$ UP,   UP $\subset$ WK", ha="center", va="center",
        fontsize=9)
# VY tier (parallel)
rbox(ax, 0.12, 0.17, 0.95, 0.46, "", TINT_VY, C_VY)
ax.text(0.19, 0.60, "VY", ha="left", va="top", fontsize=8, weight="bold", color=C_VY)
for i in range(3):
    rbox(ax, 0.40 + i * 0.21, 0.22, 0.19, 0.24, "VM", "#FFFFFF", C_VY, fs=7)
ax.text(0.595, 0.12, "VyOS SecGW VMs", ha="center", va="top", fontsize=8)
ax.text(1.24, 0.40, r"$\parallel$", ha="center", va="center", fontsize=11)
# WK tier containing UP slots
rbox(ax, 1.42, 0.17, 1.86, 0.46, "", TINT_WK, C_WK)
ax.text(1.49, 0.60, "WK", ha="left", va="top", fontsize=8, weight="bold", color=C_WK)
for i in range(3):
    x0 = 1.78 + i * 0.49
    rbox(ax, x0, 0.21, 0.46, 0.30, "", "#FFFFFF", C_WK, lw=0.6)
    for j in range(2):
        rbox(ax, x0 + 0.03 + j * 0.21, 0.245, 0.19, 0.22, "UP", TINT_UP, C_UP, fs=7)
ax.text(1.42 + 0.93, 0.12, "worker VMs, two eUPF slots each", ha="center", va="top",
        fontsize=8)

# ------------------------------------------------------------------ bottom panel: timeline
bx = fig.add_axes([0.05, 0.052, 0.93, 0.604])
T = 12                                   # axis length in ticks of g
bx.set_xlim(-0.3, T + 0.4); bx.set_ylim(-0.95, 2.45)
for s in ("top", "right", "left"):
    bx.spines[s].set_visible(False)
bx.spines["bottom"].set_position(("data", 0))
bx.spines["bottom"].set_color(MUTED)
bx.set_yticks([])
bx.set_xticks(range(0, T + 1)); bx.set_xticklabels([])
bx.tick_params(axis="x", length=3, color=MUTED, width=0.6)
bx.annotate("", xy=(T + 0.45, 0), xytext=(T - 0.2, 0),
            arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.6, mutation_scale=7))
bx.text(T + 0.4, -0.12, r"$t$", ha="right", va="top", fontsize=8)

# events (ticks): replenish order at t0, ready at t0 + h; release at t1, gone at t1 + d
t0, h, g = 1.0, 3.0, 1.0
t1, d = 9.0, 2.0
Wl = h + g                                # W_l = H_l = h_l + g (method section 2.2)
y0, y1 = 0.95, 1.55

# exposure window W_l before release (shaded)
bx.add_patch(Rectangle((t1 - Wl, 0), Wl, 2.1, fc="#ECECEC", ec="none", zorder=1))
bx.text(t1 - Wl / 2, 0.47, r"$W_l$: peak demand" + "\nevaluated for release", ha="center",
        va="center", fontsize=7.5, linespacing=1.1, zorder=6)

# ready-count step  n_l -> n_l + 1 -> n_l
xs = [-0.3, t0 + h, t0 + h, t1 + d, t1 + d, T + 0.3]
ys = [y0, y0, y1, y1, y0, y0]
bx.plot(xs, ys, color=INK, lw=1.2, zorder=4)
bx.text(-0.25, y0 + 0.06, r"$n_l$ ready", ha="left", va="bottom", fontsize=7.5, color=MUTED)
bx.text(t1 - Wl / 2, y1 + 0.06, r"$n_l + 1$", ha="center", va="bottom", fontsize=7.5,
        color=MUTED)
bx.plot([t0 + h], [y1], marker="o", ms=4, color=INK, zorder=5)
bx.text(t0 + h + 0.12, y1 - 0.06, "ready", ha="left", va="top", fontsize=7.5)
bx.plot([t1 + d], [y0], marker="o", ms=4, mfc="white", color=INK, zorder=5)
bx.text(t1 + d + 0.12, y0 + 0.06, "gone", ha="left", va="bottom", fontsize=7.5)

# order / release markers
for x in (t0, t1):
    bx.plot([x, x], [0, 2.0], ls=(0, (1.5, 1.5)), lw=0.7, color=MUTED, zorder=2)
bx.text(t0, 2.06, r"order ($t_0$)", ha="center", va="bottom", fontsize=7.5)
bx.text(t1, 2.06, r"release ($t_1$)", ha="center", va="bottom", fontsize=7.5)

def brace(x0, x1, y, text, above=True, fs=7.5, ha="center"):
    bx.annotate("", xy=(x0, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="|-|", color=INK, lw=0.7, mutation_scale=2.5))
    tx = (x0 + x1) / 2 if ha == "center" else x0 + 0.05
    bx.text(tx, y + (0.07 if above else -0.09), text, ha=ha,
            va="bottom" if above else "top", fontsize=fs, zorder=6)

brace(t0, t0 + h, 0.30, r"$h_l$ (ready lead)")
brace(t1, t1 + d, 0.30, r"$d_l$ (teardown)", ha="left")
brace(t0, t0 + h + g, -0.32, r"$H_l$ (horizon) $= h_l + g$;  WK: $h_{WK} + h_{UP} + g$", above=False)
# one tick = g
bx.annotate("", xy=(T - 1, -0.32), xytext=(T, -0.32),
            arrowprops=dict(arrowstyle="|-|", color=INK, lw=0.6, mutation_scale=2))
bx.text(T - 0.5, -0.41, r"$g$", ha="center", va="top", fontsize=7.5)

# rev. 4.6 (2026-11-02): inset table of planning constants removed (its rows are Table II of the paper); figure height 3.2 -> 2.65 in
fig.savefig(OUT, format="pdf")
print("wrote", os.path.abspath(OUT))

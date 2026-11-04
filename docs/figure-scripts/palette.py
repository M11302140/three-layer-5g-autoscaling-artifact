"""palette.py (rev. 4.1, 2026-11-01): one colour/marker table for every paper figure (Fig. 3 load band, Fig. 4 residuals, Fig. 5 cost vs violation,
Fig. 7 burst). Rules: planner = dark blue #1f4e9c, ε = 2 % filled circle, ε = 0.5 % filled diamond; CR = the same colour and shapes, hollow;
v6 = green triangle; B4c2 orange, B5c1 pink, B6 cyan (Okabe-Ito values); same-target baseline knobs = the baseline colour with a black edge;
single runs = small markers, cell means = large markers. Black is never a data colour; A-PL (simulation only) is grey."""
ARMS = {   # key -> (legend label, colour, marker, hollow)
    "S4p2":  ("planner, ε = 2 %",    "#1f4e9c", "o", False),
    "S4p05": ("planner, ε = 0.5 %",  "#1f4e9c", "D", False),
    "S4b":   ("CR, ε = 2 %",         "#1f4e9c", "o", True),
    "S4a":   ("CR, ε = 0.5 %",       "#1f4e9c", "D", True),
    "v6":    ("v6",                  "#009E73", "^", False),
    "B4c2":  ("HPA",                "#E69F00", "s", False),
    "B5c1":  ("Holt-forecast HPA",                "#CC79A7", "v", False),
    "B6":    ("multi-predictor (u = 0.70)",       "#56B4E9", "P", False),
    "B1":    ("B1 (static)",         "#777777", "X", False),
    "APL":   ("A-PL (sim. only)",    "#999999", "h", False),
}
ARM_ORDER = ["S4p2", "S4p05", "S4b", "S4a", "v6", "B4c2", "B5c1", "B6", "B1"]
SAME_TARGET_EDGE = "black"     # edge colour of same-target baseline knobs (B4 3.75/300, B5 4.0/L2, B6 0.775)
MS_RUN, MS_CELL = 3.2, 7.0      # marker sizes (points): single run / cell mean

def style(arm, same_target=False, cell=False, ms=None):
    """matplotlib kwargs for one marker: hollow CR, black edge for same-target knobs, size by run/cell."""
    lab, col, mk, hollow = ARMS[arm]
    kw = dict(marker=mk, ms=ms if ms is not None else (MS_CELL if cell else MS_RUN), ls="none",
              mfc="white" if hollow else col, mec=SAME_TARGET_EDGE if same_target else col, mew=0.9 if hollow else (0.5 if same_target else 0.6))
    return kw

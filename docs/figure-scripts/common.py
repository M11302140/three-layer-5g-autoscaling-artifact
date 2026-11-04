"""Shared style for the paper figures (IEEE TNSM).
Fixed arm -> colour/marker mapping (Okabe-Ito colourblind-safe palette), rcParams,
and loaders for rq_metrics.csv, the registered-prediction files and per-minute run CSVs.
Every plotted value is read from those files; nothing is hard-coded here except file paths.
"""
import csv, os, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FIGS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # .../paper/figs
RQ_CSV = "/home/user/experiment/paper_out_new/rq/rq_metrics.csv"
PRED_T345 = "/home/user/experiment/qsim/v8_predict_t345_2026-10-07.txt"
PRED_T67 = "/home/user/experiment/qsim/v8_predict_t67_2026-10-15.txt"
P2 = "/home/user/experiment/p2"

# arm key -> (legend label, colour, marker).  Okabe & Ito (2008) palette; yellow omitted (poor on white).
# rev. 4.1 (2026-11-01): colours and markers come from palette.py (one table for every figure); ARMS keeps the (label, colour, marker)
# triple for the older scripts, PAL exposes the hollow flag and the style() helper.
import palette as PAL
ARMS = {k: (v[0], v[1], v[2]) for k, v in PAL.ARMS.items()}
ARM_ORDER = PAL.ARM_ORDER

# exact group names in rq_metrics.csv for the MAIN test-set runs, per trace
def main_group(trace, arm):
    if arm == "B5c1":
        return f"MAIN {trace} B5c1 (q11)"
    if arm == "B6":
        return f"MAIN {trace} B6 u=0.70"
    return f"MAIN {trace} {arm}"

# development-set S-arm groups (t1/t2); all three use the t1/t2 registered prediction
DEV_GROUPS = [
    ("S4a", "t1", "S4a 0.5% G2b t1"),
    ("S4a", "t2", "S4a 0.5% G2b t2"),
    ("S4a", "t1", "S4a 0.5% G2c t1 (post-fix v9)"),
    ("S4b", "t1", "S4b 2% G2b t1"),
    ("S4b", "t2", "S4b 2% G2b t2"),
]

def set_style():
    plt.rcParams.update({
        "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8.5, "legend.fontsize": 7,
        "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "font.family": "serif", "font.serif": ["Nimbus Roman", "Times New Roman", "Liberation Serif", "STIXGeneral", "DejaVu Serif"],
        "pdf.fonttype": 42, "ps.fonttype": 42, "mathtext.fontset": "stix",            # embed TrueType (IEEE PDF eXpress friendly)
        "axes.linewidth": 0.6, "grid.linewidth": 0.4, "grid.alpha": 0.3,
        "lines.linewidth": 1.0, "legend.frameon": True, "legend.framealpha": 0.9,
        "legend.handletextpad": 0.4, "legend.borderpad": 0.4, "legend.labelspacing": 0.3,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    })

def load_rq():
    rows = list(csv.DictReader(open(RQ_CSV)))
    return [r for r in rows if r.get("group") and r["group"] != "group"]

def rows_of(rows, group):
    return [r for r in rows if r["group"] == group]

def viol(r):
    """violation minutes = 60 - slo (minutes passing of 60)."""
    return 60 - int(float(r["slo"]))

def alloc(r):
    return float(r["alloc_vm"])

def load_predictions():
    """Return {(arm, trace): alloc_vmexist} from the two registered prediction files."""
    pred = {}
    for line in open(PRED_T345, encoding="utf-8"):
        m = re.match(r"\s*(S4a|S4b)\s+(t\d)\s+\d+\s+\S+\s+(\d+)\s+(\d+)", line)
        if m:
            pred[(m.group(1), m.group(2))] = float(m.group(4))      # 4th field = alloc_vmexist
    for line in open(PRED_T67, encoding="utf-8"):
        m = re.match(r"\s*(S4a|S4b)\s+(t\d)\s+\S+\s+(\d+)\s+(\d+)", line)
        if m:
            pred[(m.group(1), m.group(2))] = float(m.group(4))
    return pred

def load_trace(run):
    """Per-minute run CSV -> list of dicts with parsed min/target_ue/ready/vyos_n/worker_n."""
    out = []
    for r in csv.DictReader(open(f"{P2}/trace_v7_{run}.csv")):
        cov = r["eupf_cov"]
        ready = int(cov.split("/")[0]) if "/" in cov else None
        loss = float(r["e2e_pct"]) if r["e2e_pct"] not in ("", "?") else 1e9
        p99 = float(r["lat_p99_us"]) if r["lat_p99_us"] not in ("", "?") else 1e9
        out.append({"min": int(r["min"]), "target_ue": int(float(r["target_ue"])), "ready": ready,
                    "slo_ok": (loss <= 0.1 and p99 <= 1000),       # rq_metrics.py: good = loss<=0.1 and p99<=1000
                    "cov_denom": int(cov.split("/")[1]) if "/" in cov else None,
                    "vyos_n": int(float(r["vyos_n"])), "worker_n": int(float(r["worker_n"]))})
    return out

def save(fig, name):
    path = os.path.join(FIGS, name)
    fig.savefig(path, format="pdf")   # exact figsize: 3.4 in (single column) / 7.0 in (double column)
    print("written", path)
    return path

#!/usr/bin/env python3
"""r62 Task A: conditional (rise1-bucket) calibration. Two columns = targets (S4a 0.5 %, S4b 2 %).
Top: held-out risk per bucket (six-split mean, error bar = SE = std/sqrt 6), dashed line = epsilon, hollow marker =
the bucket's risk under the deployed full-library lambda. Bottom: bucket lambda_VM and lambda_UP (six-split mean +- std),
dotted lines = deployed full-library lambda. Data: /home/user/experiment/qsim/r62ab/results.json (key "A")."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib.pyplot as plt
import common as C
C.set_style()
A = json.load(open("/home/user/experiment/qsim/r62ab/results.json"))["A"]
DEP = {0.005: ("S4a", 2.83, 3.08), 0.02: ("S4b", 1.83, 2.00)}
fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.2), sharex=True)
for col, tg in enumerate((0.005, 0.02)):
    arm, dv, du = DEP[tg]; _, colr, mk = C.ARMS[arm]
    ks = [k for k in A if k.endswith(f"|{tg}")]
    ks.sort(key=lambda k: int(k.split("|")[0][1:].split("+")[0]))
    names = [k.split("|")[0] for k in ks]; x = np.arange(len(ks))
    ho = np.array([A[k]["ho_mean"] for k in ks]) * 100; se = np.array([A[k]["se"] for k in ks]) * 100
    fr = np.array([A[k]["full_risk"] for k in ks]) * 100
    ax = axes[0, col]
    ax.errorbar(x, ho, yerr=se, fmt=mk, color=colr, ms=4, capsize=2, lw=0.8, label="bucket-calibrated $\\lambda$ (held-out)")
    ax.plot(x, fr, mk, mfc="none", mec="#555555", ms=4, label="deployed full-library $\\lambda$")
    ax.axhline(tg * 100, ls="--", color="k", lw=0.7, label=f"$\\varepsilon$ = {tg*100:g} %")
    ax.set_title(f"{arm} target {tg*100:g} %", pad=3); ax.set_ylabel("Minute risk (%)"); ax.grid(True); ax.set_ylim(bottom=0)
    if col == 0: ax.legend(loc="upper left")
    ax = axes[1, col]
    lv = [np.mean([r["lv"] for r in A[k]["rows"]]) for k in ks]; lvs = [np.std([r["lv"] for r in A[k]["rows"]]) for k in ks]
    lu = [np.mean([r["lu"] for r in A[k]["rows"]]) for k in ks]; lus = [np.std([r["lu"] for r in A[k]["rows"]]) for k in ks]
    ax.errorbar(x - 0.12, lv, yerr=lvs, fmt="o", color="#0072B2", ms=3.5, capsize=2, lw=0.8, label="$\\lambda_{VM}$")
    ax.errorbar(x + 0.12, lu, yerr=lus, fmt="s", color="#D55E00", ms=3.5, capsize=2, lw=0.8, label="$\\lambda_{UP}$")
    ax.axhline(dv, ls=":", color="#0072B2", lw=0.8); ax.axhline(du, ls=":", color="#D55E00", lw=0.8)
    ax.set_ylabel("$\\lambda$"); ax.grid(True); ax.set_xticks(x); ax.set_xticklabels(names, rotation=0)
    ax.set_xlabel("rise1 bucket (library decile; empty deciles merged)")
    if col == 0: ax.legend(loc="upper left")
fig.tight_layout(pad=0.4)
C.save(fig, "fig_r62_decile_lambda.pdf")
if len(sys.argv) > 1: fig.savefig(sys.argv[1], dpi=150)

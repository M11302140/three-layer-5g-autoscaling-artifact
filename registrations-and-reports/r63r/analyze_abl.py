#!/usr/bin/env python3
"""r63r: out/abl.jsonl -> out/abl_table.md + out/abl_summary.json (no simulation). Old = abl/ablation_raw.json (full-library σ̂).
Verdict rule (frozen, v8sim10_ablation.py): vs (e) |Δcost| > 1 % (held-out alloc vmexist) or |Δflaps| > 2 per run -> CONTRIBUTES;
NOTE if held-out risk > e's + 0.25·target (not equal-risk).  Check: variant e == r63a out/split.jsonl split by split."""
import json, numpy as np
Q = "/home/user/experiment/qsim"; R = f"{Q}/r63r"
VAR = [('e', 'full'), ('a', 'single_lambda'), ('b', 'independent'), ("b'", 'independent_full'), ('c', 'fixed_dwell'), ('d', 'lock_only')]
TG = (0.02, 0.005)
new = [json.loads(l) for l in open(f"{R}/out/abl.jsonl")]
NEW = [dict(variant=r["variant"], target=float(t), seed=r["seed"], **x) for r in new for t, x in r["rows"].items()]
OLD = [r for r in json.load(open(f"{Q}/abl/ablation_raw.json"))["rows"]]
def agg(rows, v, tg, old):
    rs = [r for r in rows if r["variant"] == v and r["target"] == tg and not r.get("infeasible")]
    ninf = sum(1 for r in rows if r["variant"] == v and r["target"] == tg and r.get("infeasible"))
    if not rs: return None
    g = lambda f: (float(np.mean([f(r) for r in rs])), float(np.std([f(r) for r in rs])))
    return dict(n=len(rs), ninf=ninf, lam_vm=g(lambda r: r["lam_vm"]), lam_up=g(lambda r: r["lam_up"]), risk=g(lambda r: r["ho"]["risk"]), alloc=g(lambda r: r["ho"]["alloc"]),
                alloc_d=g(lambda r: r["ho"]["alloc_dispatch"]), flaps=g(lambda r: r["ho"]["flaps"]), flaps_cd=g(lambda r: r["ho"]["flaps_cd"]), acts=g(lambda r: r["ho"]["acts"]),
                under_vy=g(lambda r: r["ho"]["under_vy"]), under_up=g(lambda r: r["ho"]["under_up"]), over_vy=g(lambda r: r["ho"]["over_vy"]), over_up=g(lambda r: r["ho"]["over_up"]))
def verdict(a, base, v, tg):
    dc = 100 * (a["alloc"][0] - base["alloc"][0]) / base["alloc"][0]; df = a["flaps"][0] - base["flaps"][0]
    if v == "full": return dc, df, "baseline"
    c = abs(dc) > 1.0 or abs(df) > 2.0
    s = ("CONTRIBUTES" if c else "no contribution") + f" (|Δcost| {abs(dc):.2f}% {'>' if abs(dc)>1 else '≤'} 1%, |Δflaps| {abs(df):.2f} {'>' if abs(df)>2 else '≤'} 2)"
    if a["risk"][0] > base["risk"][0] + 0.25 * tg: s += f"; NOTE ho risk {a['risk'][0]:.4f} vs e {base['risk'][0]:.4f}"
    return dc, df, s
pm = lambda x, p=2: f"{x[0]:.{p}f} ± {x[1]:.{p}f}"
L = []; SUM = {}
L += ["| variant | target | σ̂ | λ_VM | λ_UP | held-out risk | alloc vmexist (dispatch) | Δcost vs e | flaps/run (cd) | Δflaps vs e | under VY/UP | over VY/UP | verdict |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for tg in TG:
    bn = agg(NEW, "full", tg, False); bo = agg(OLD, "full", tg, True)
    for tag, v in VAR:
        an = agg(NEW, v, tg, False); ao = agg(OLD, v, tg, True)
        for nm, a, b in (("old (full library)", ao, bo), ("new (cal groups)", an, bn)):
            if a is None: L.append(f"| ({tag}) {v} | {tg} | {nm} | infeasible | | | | | | | | | |"); continue
            dc, df, vd = verdict(a, b, v, tg); inf_txt = "" if a["ninf"] == 0 else "; %d split(s) infeasible" % a["ninf"]
            SUM[f"{v}@{tg}@{nm.split()[0]}"] = dict(a, dcost_pct=dc, dflaps=df, verdict=vd)
            L.append(f"| ({tag}) {v} | {tg} | {nm} | {pm(a['lam_vm'])} | {pm(a['lam_up'])} | {pm(a['risk'],4)} | {pm(a['alloc'],1)} ({a['alloc_d'][0]:.1f}) | {dc:+.2f}% | {pm(a['flaps'])} ({a['flaps_cd'][0]:.2f}) | {df:+.2f} | {a['under_vy'][0]:.2f} / {a['under_up'][0]:.2f} | {a['over_vy'][0]:.2f} / {a['over_up'][0]:.2f} | {vd}{inf_txt} |")
# verdict-change summary
L += ["", "| variant | target | old verdict | new verdict | changed? | Δcost old → new | Δflaps old → new |", "|---|---|---|---|---|---|---|"]
chg = []
for tg in TG:
    for tag, v in VAR[1:]:
        o = SUM.get(f"{v}@{tg}@old"); n = SUM.get(f"{v}@{tg}@new")
        if not (o and n): continue
        ov = o["verdict"].split(" (")[0]; nv = n["verdict"].split(" (")[0]; ch = ov != nv; chg.append(ch)
        L.append(f"| ({tag}) {v} | {tg} | {ov} | {nv} | {'**YES**' if ch else 'no'} | {o['dcost_pct']:+.2f}% → {n['dcost_pct']:+.2f}% | {o['dflaps']:+.2f} → {n['dflaps']:+.2f} |")
L += ["", f"verdicts changed: {sum(chg)}/{len(chg)}"]
# e vs r63a
sp = {r["seed"]: r for r in (json.loads(l) for l in open(f"{Q}/r63a/out/split.jsonl"))}; bad = 0; n = 0; lines = []
for r in NEW:
    if r["variant"] != "full": continue
    o = sp[r["seed"]]["rows"][str(r["target"])]; n += 1
    same = (r["lam_vm"] == o["lam_vm"] and r["lam_up"] == o["lam_up"] and abs(r["cal_risk"] - o["cal_risk"]) < 1e-12 and abs(r["cal_alloc"] - o["cal_alloc"]) < 1e-6
            and abs(r["ho"]["risk"] - o["ho"]["risk"]) < 1e-12 and abs(r["ho"]["alloc"] - o["ho"]["alloc_vm"]) < 1e-6 and abs(r["ho"]["alloc_dispatch"] - o["ho"]["alloc_d"]) < 1e-6)
    bad += not same
    lines.append(f"| {r['target']} | {r['seed']} | {r['lam_vm']}/{r['lam_up']} | {o['lam_vm']}/{o['lam_up']} | {r['ho']['risk']:.5f} | {o['ho']['risk']:.5f} | {r['ho']['alloc']:.2f} | {o['ho']['alloc_vm']:.2f} | {r['ho']['alloc_dispatch']:.2f} | {o['ho']['alloc_d']:.2f} | {'same' if same else 'DIFF'} |")
L += ["", "Variant (e) vs r63a six-split (out/split.jsonl):", "", "| target | split | λ (e) | λ r63a | ho risk (e) | r63a | vmexist (e) | r63a | dispatch (e) | r63a | |", "|---|---|---|---|---|---|---|---|---|---|---|"] + lines
L += ["", f"**variant e vs r63a: {n-bad}/{n} identical** (λ, cal risk, cal alloc, ho risk, ho alloc vmexist and dispatch)"]
# per split
L += ["", "Per split (new):", "", "| variant | target | seed | λ | cal risk | ho risk | ho vmexist | ho dispatch | flaps | flaps cd | under VY/UP | over VY/UP |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for tag, v in VAR:
    for tg in TG:
        for r in sorted([r for r in NEW if r["variant"] == v and r["target"] == tg], key=lambda r: r["seed"]):
            if r.get("infeasible"): L.append(f"| {v} | {tg} | {r['seed']} | infeasible (min cal {r['min_cal_risk']:.4f}) | | | | | | | | |"); continue
            h = r["ho"]; L.append(f"| {v} | {tg} | {r['seed']} | {r['lam_vm']}/{r['lam_up']} | {r['cal_risk']:.4f} | {h['risk']:.4f} | {h['alloc']:.1f} | {h['alloc_dispatch']:.1f} | {h['flaps']:.2f} | {h['flaps_cd']:.2f} | {h['under_vy']:.2f}/{h['under_up']:.2f} | {h['over_vy']:.2f}/{h['over_up']:.2f} |")
L += ["", f"contexts {len(new)}, total context time {sum(r['t'] for r in new):.0f} s, sims {sum(r['nsim'] for r in new)}"]
open(f"{R}/out/abl_table.md", "w").write("\n".join(L) + "\n"); json.dump(dict(summary=SUM, e_vs_r63a=[n - bad, n], changed=sum(chg)), open(f"{R}/out/abl_summary.json", "w"), indent=1)
print("\n".join(L[:40]))

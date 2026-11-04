import timeit
import sys, os, json
sys.path.insert(0, '/home/user/experiment/qsim'); sys.path.insert(0, '/home/user/experiment/qsim/r62cf')
import calib_c as C, v8sim11 as V
lib = C.LIB; bad = 0
for i in range(0, 1615, 101):
    ue = lib[i]["ue"][:60]
    for arm, fam, key in (("B4c2", "B4", (3.5, 600)), ("B5c1", "B5", (4.0, "L2"))):
        a = V.run(ue, arm); T, x = key; mu = C.mu_of(fam, T)
        ctl = V.CtlB4(predictive=(fam == "B5"), mu=mu, target=T, tol=0.05, down=600, margin=0.8, lead=C.LEADS.get(x, (2, 5, 5)))
        b = C.run_ctl(ue, ctl, V.initial_fleet("B4", ue[0], target=T, mu=mu))
        ok = a["slo"] == b["slo"] and abs(a["alloc_vm"] - b["alloc_vm"]) < 1e-9; bad += not ok
        if not ok: print("MISMATCH", i, arm, a["slo"], b["slo"], a["alloc_vm"], b["alloc_vm"])
    a = V.run(ue, "B6", u=0.7); cfg, pr = V.cfg_prior(); b = C.run_ctl(ue, V.CtlB6(cfg, u=0.7), V.initial_fleet("B6", ue[0], u=0.7))
    ok = a["slo"] == b["slo"] and abs(a["alloc_vm"] - b["alloc_vm"]) < 1e-9; bad += not ok
    a = V.run(ue, "S", L={"vy": 2.0, "wk": 2.0, "up": 2.0}); b = C.run_ctl(ue, V.CtlSigma(cfg, pr, {"vy": 2.0, "wk": 2.0, "up": 2.0}), V.initial_fleet("S", ue[0], L={"vy": 2.0, "wk": 2.0, "up": 2.0}))
    ok = a["slo"] == b["slo"] and abs(a["alloc_vm"] - b["alloc_vm"]) < 1e-9; bad += not ok
print("mismatches:", bad, "of", 4 * len(range(0, 1615, 101)))

"""verify_dual.py: the dual-accounting copy equals the frozen v8sim10.sim_nest2 (acct dispatch and vmexist) on random (trace, λ) pairs,
and sim_v6_pm equals frozen v8sim2.sim_v6 (slo/alloc/acts/flaps)."""
import sys, json, random, numpy as np
sys.path.insert(0,'/home/user/experiment/qsim/r62ab')
import dual as D
from dual import Q2,S,M
lib=json.load(open('/home/user/experiment/qsim/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg)
rnd=random.Random(1); bad=0; N=int(sys.argv[1]) if len(sys.argv)>1 else 40
for k in range(N):
    i=rnd.randrange(len(lib)); lv=rnd.choice([0.5+0.25*j for j in range(13)]); lu=rnd.choice([0.5+0.25*j for j in range(17)]); L={"vy":lv,"wk":lv,"up":lu}; ue=lib[i]["ue"][:60]
    a=Q2.sim_nest2(ue,cfg,pr,L); b=Q2.sim_nest2(ue,cfg,pr,L,acct='vmexist'); c=D.sim_nest2_dual(ue,cfg,pr,L)
    ok=a["slo"]==c["slo"]==b["slo"] and a["alloc"]==c["alloc"] and b["alloc"]==c["alloc_vm"] and np.array_equal(a["pct"],c["pct"]) and a["ev"]==c["ev"]
    bad+=not ok
    a6=S.sim_v6(ue,cfg); c6=D.sim_v6_pm(ue,cfg); ok6=all(a6[x]==c6[x] for x in ("slo","alloc","acts","flaps")) and int((c6["pct"]<=0.1).sum())==c6["slo"]
    bad+=not ok6
print(f"dual vs frozen: {N} random (trace,λ) pairs, mismatches {bad}")

"""dual.py (r62ab): dual-accounting copy of the FROZEN v8sim10.sim_nest2, generated at import time from its source
(inspect.getsource) by a textual patch of the billing block only: one pass computes alloc (acct='dispatch') AND alloc_vm
(acct='vmexist'). Dynamics untouched (billing does not feed back). Equivalence vs the frozen function is verified in verify.py.
Also: sim_v6_pm = copy of frozen v8sim2.sim_v6 that additionally returns pct (per-minute loss %), same patch method."""
import timeit  # noqa: stdlib first, before qsim/timeit.py (which shadows it) is on the path
import sys, os, inspect
os.chdir('/home/user/experiment/qsim'); sys.path.insert(0,'/home/user/experiment/qsim')
import v8sim2 as S, v8sim7 as M, v8sim10 as Q2
src=inspect.getsource(Q2.sim_nest2)
old_burn="""        if acct=='vmexist':
            burn={k:sum(1 for u in units if u["k"]==k and (u["dispatch"]+(30 if k!="up" else 0))<=t and (u["gone"] if k=="up" else u.get("bend",u["gone"]))>t) for k in cur}
        else:
            burn={k:cnt(k,lambda u:u["dispatch"]<=t) for k in cur}
        c=sum(cfg.cores[k]*burn[k] for k in burn)*DT/60; alloc+=c; permin[i*DT//60]+=c
"""
new_burn="""        burn_v={k:sum(1 for u in units if u["k"]==k and (u["dispatch"]+(30 if k!="up" else 0))<=t and (u["gone"] if k=="up" else u.get("bend",u["gone"]))>t) for k in cur}
        burn={k:cnt(k,lambda u:u["dispatch"]<=t) for k in cur}
        c=sum(cfg.cores[k]*burn[k] for k in burn)*DT/60; alloc+=c; permin[i*DT//60]+=c
        alloc_v+=sum(cfg.cores[k]*burn_v[k] for k in burn_v)*DT/60
"""
assert src.count(old_burn)==1
src=src.replace(old_burn,new_burn)
o="alloc=0.0; ev=[];"; assert src.count(o)==1; src=src.replace(o,"alloc=0.0; alloc_v=0.0; ev=[];")
o="return dict(slo=int((pct<=0.1).sum()), alloc=alloc,"; assert src.count(o)==1
src=src.replace(o,"return dict(slo=int((pct<=0.1).sum()), alloc=alloc, alloc_vm=alloc_v,")
src=src.replace("def sim_nest2(","def sim_nest2_dual(",1)
g=dict(vars(Q2)); exec(compile(src,"<sim_nest2_dual>","exec"),g); sim_nest2_dual=g["sim_nest2_dual"]
s6=inspect.getsource(S.sim_v6)
o="return dict(slo=int((pct<=0.1).sum()), alloc=alloc, acts=acts, flaps=flaps)"; assert s6.count(o)==1
s6=s6.replace(o,"return dict(slo=int((pct<=0.1).sum()), alloc=alloc, acts=acts, flaps=flaps, pct=pct)").replace("def sim_v6(","def sim_v6_pm(",1)
g6=dict(vars(S)); exec(compile(s6,"<sim_v6_pm>","exec"),g6); sim_v6_pm=g6["sim_v6_pm"]
def flaps(ev, win=600):
    """same-layer opposite-direction scaling events ('out'/'in') within win seconds of the previous same-layer event"""
    last={}; n=0
    for t,a,k in ev:
        if a not in ("out","in"): continue
        d=+1 if a=="out" else -1
        if k in last and last[k][0]==-d and t-last[k][1]<=win: n+=1
        last[k]=(d,t)
    return n

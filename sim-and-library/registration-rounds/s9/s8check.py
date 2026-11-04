#!/usr/bin/env python3
"""(docstring removed)"""
import os, sys, json, time, numpy as np
Q="/home/user/experiment/qsim"; sys.path.insert(0,Q); sys.path.insert(0,Q+"/s7"); os.chdir(Q)
_argv=sys.argv; sys.argv=[sys.argv[0]]
import v8sim10_ablation as AB
sys.argv=_argv
import s7core as C
from v8sim3 import grouped_split
from concurrent.futures import ProcessPoolExecutor
lib=AB.lib; cfg=AB.cfg
S7=[json.loads(l) for l in open(f"{Q}/s7/out/cal.jsonl")]
def job(args):
    seed,tn=args; r=[x for x in S7 if x['seed']==seed and x['target_name']==tn][0]
    c,h=grouped_split(seed); sp=C.S7Prior([lib[i] for i in c],cfg); L={"vy":r['a'],"wk":r['a'],"up":r['b']}; out={}
    for name,B in (("S7",r['B']),("S8",None)):
        ms=[]
        for i in h:
            rv=C.sim_s7(lib[i]["ue"][:60],cfg,sp,L,B=B,w=r['w'],acct="vmexist"); m=AB.trace_metrics(rv)
            m["alloc_dispatch"]=C.sim_s7(lib[i]["ue"][:60],cfg,sp,L,B=B,w=r['w'],acct="dispatch")["alloc"]; ms.append(m)
        out[name]={k:float(np.mean([m[k] for m in ms])) for k in ('risk','alloc','alloc_dispatch','flaps','acts_up')}
    return dict(seed=seed,target=tn,a=r['a'],b=r['b'],w=r['w'],P=r['P'],n_ho=len(h),cal_ho=r['ho'],**out)
if __name__=="__main__":
    nproc=int(sys.argv[1]) if len(sys.argv)>1 else 4; t0=time.time()
    with ProcessPoolExecutor(nproc) as pool: rows=list(pool.map(job,[(s,t) for t in ('0.02','0.005') for s in range(6)]))
    L=["| target | split | lambda | w | P | S7 risk | S8 risk | S7 vmexist | S8 vmexist | S7 disp | S8 disp | S7 flaps | S8 flaps | S7 = cal.jsonl? |","|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        cons=abs(r['S7']['risk']-r['cal_ho']['risk'])<1e-9 and abs(r['S7']['alloc']-r['cal_ho']['alloc'])<1e-6
        L.append(f"| {r['target']} | {r['seed']} | {r['a']}/{r['b']} | {r['w']} | {r['P']} | {r['S7']['risk']:.4f} | {r['S8']['risk']:.4f} | {r['S7']['alloc']:.1f} | {r['S8']['alloc']:.1f} | {r['S7']['alloc_dispatch']:.1f} | {r['S8']['alloc_dispatch']:.1f} | {r['S7']['flaps']:.2f} | {r['S8']['flaps']:.2f} | {'yes' if cons else 'NO'} |")
    for t in ('0.02','0.005'):
        rs=[r for r in rows if r['target']==t]; m=lambda a,k: float(np.mean([r[a][k] for r in rs]))
        L.append(f"\ntarget {t} six-split mean: risk S7 {m('S7','risk'):.4f} / S8 {m('S8','risk'):.4f}; vmexist S7 {m('S7','alloc'):.1f} / S8 {m('S8','alloc'):.1f} ({100*(m('S8','alloc')/m('S7','alloc')-1):+.2f} %); flaps S7 {m('S7','flaps'):.2f} / S8 {m('S8','flaps'):.2f}")
    L.append(f"\ntime {time.time()-t0:.0f}s")
    open(f"{Q}/s9/out/s8_r1check.txt","w").write("\n".join(L)+"\n"); json.dump(rows,open(f"{Q}/s9/out/s8_r1check.json","w"),indent=1); print("\n".join(L))

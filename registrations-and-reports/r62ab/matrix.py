"""matrix.py (r62ab step 0): every library trace x 221 grid points (λ_VM 0.5..3.5, λ_UP 0.5..4.5, step 0.25), one dual-accounting
nest2 run each. Checkpointed in chunks of 16 traces under r62ab/mat/chunk_XXXX.npz; resumable. Merge -> r62ab/matrix.npz.
usage: nice -n 19 taskset -c 13,14 python3 matrix.py [nproc=2] | merge"""
import sys, os, json, time, numpy as np
sys.path.insert(0,'/home/user/experiment/qsim/r62ab')
import dual as D
from dual import S, M
OUT='/home/user/experiment/qsim/r62ab/mat'; CH=16
LV=[round(0.5+0.25*j,2) for j in range(13)]; LU=[round(0.5+0.25*j,2) for j in range(17)]
PTS=[(lv,lu) for lv in LV for lu in LU]
lib=json.load(open('/home/user/experiment/qsim/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg)
def one_trace(i):
    ue=lib[i]["ue"][:60]; n=len(PTS)
    slo=np.zeros(n,np.int16); vb=np.zeros(n,np.uint64); ad=np.zeros(n); av=np.zeros(n); fl=np.zeros(n,np.int16); na=np.zeros(n,np.int16)
    for j,(lv,lu) in enumerate(PTS):
        r=D.sim_nest2_dual(ue,cfg,pr,{"vy":lv,"wk":lv,"up":lu})
        v=(r["pct"]>0.1); assert int(60-v.sum())==r["slo"]
        slo[j]=r["slo"]; vb[j]=np.uint64(sum(1<<m for m in range(60) if v[m])); ad[j]=r["alloc"]; av[j]=r["alloc_vm"]
        fl[j]=D.flaps(r["ev"]); na[j]=sum(1 for e in r["ev"] if e[1] in ("out","in"))
    return slo,vb,ad,av,fl,na
def do_chunk(c):
    f=f"{OUT}/chunk_{c:04d}.npz"
    if os.path.exists(f): return c,0.0
    t=time.time(); idx=list(range(c*CH,min(len(lib),(c+1)*CH))); res=[one_trace(i) for i in idx]
    arr=[np.stack([r[k] for r in res]) for k in range(6)]
    np.savez(f+".tmp.npz",idx=np.array(idx),slo=arr[0],vbits=arr[1],alloc_d=arr[2],alloc_v=arr[3],flaps=arr[4],nact=arr[5]); os.replace(f+".tmp.npz",f)
    return c,time.time()-t
if __name__=="__main__":
    os.makedirs(OUT,exist_ok=True)
    if len(sys.argv)>1 and sys.argv[1]=="merge":
        nc=(len(lib)+CH-1)//CH; parts=[np.load(f"{OUT}/chunk_{c:04d}.npz") for c in range(nc)]
        d={k:np.concatenate([p[k] for p in parts]) for k in ("idx","slo","vbits","alloc_d","alloc_v","flaps","nact")}
        assert (d["idx"]==np.arange(len(lib))).all()
        np.savez('/home/user/experiment/qsim/r62ab/matrix.npz',lv=np.array([p[0] for p in PTS]),lu=np.array([p[1] for p in PTS]),**d); print("merged",d["slo"].shape); sys.exit()
    from concurrent.futures import ProcessPoolExecutor
    nproc=int(sys.argv[1]) if len(sys.argv)>1 else 2; nc=(len(lib)+CH-1)//CH; t0=time.time()
    todo=[c for c in range(nc) if not os.path.exists(f"{OUT}/chunk_{c:04d}.npz")]
    print(f"{len(PTS)} points x {len(lib)} traces; {len(todo)}/{nc} chunks to do",flush=True)
    with ProcessPoolExecutor(nproc) as pool:
        for k,(c,dt) in enumerate(pool.map(do_chunk,todo)):
            el=time.time()-t0; print(f"chunk {c} {dt:.0f}s  done {k+1}/{len(todo)} elapsed {el:.0f}s eta {el/(k+1)*(len(todo)-k-1):.0f}s",flush=True)

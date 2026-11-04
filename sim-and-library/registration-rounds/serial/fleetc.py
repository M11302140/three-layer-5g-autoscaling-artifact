#!/usr/bin/env python3
"""qsim/serial/fleetc.py (spec §4.134): fleet-level v6 (v8sim2.sim_v6) and B6 (v8sim_b6.sim_b6) with the executor slot-boot cap.
Built from the frozen sources by a checked text patch of the slot dispatch only: capC = 0 -> frozen code path (+ queue counter);
capC = C (None = inf) -> v6 requests the whole deficit, B6 at most maxbatch 3 per tick (daemon semantics), both limited by C booting slots;
a slot dispatched while another slot boots gets lead + delta."""
import sys, inspect, textwrap
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q)
import v8sim2 as S, v8sim_b6 as B
CAP_BLOCK='''
                if k=="up" and capC!=0:
                    nreq=int(math.ceil(WANT-cur["up"]-pend["up"]-1e-9)); _MB=MAXB; nmax=nreq if _MB is None else min(nreq,_MB)
                    for j in range(nmax):
                        if cur["up"]+pend["up"]>=FMAXUP or cur["up"]+pend["up"]+1>(cur["wk"]+pend["wk"])*cfg.spw: break
                        if capC is not None and pend["up"]>=capC:
                            if qbox is not None: qbox[0]+=nmax-j
                            break
                        teff=t+cfg.h["up"]+(delta if pend["up"]>=1 else 0)
                        if cur["up"]+pend["up"]+1>cur["wk"]*cfg.spw and any(x[1]=="wk" for x in infl): teff=max(teff,max(x[0] for x in infl if x[1]=="wk")+cfg.h["up"])
                        infl.append((teff,"up")); burn["up"]+=1; acts+=1; last_out["up"]=t; pend["up"]+=1
                        if last_dir["up"][0]==-1 and t-last_dir["up"][1]<=600: flaps+=1
                        last_dir["up"]=(+1,t)
                    continue
'''
def build(fn, name, want_expr, maxb, fmax):
    src=textwrap.dedent(inspect.getsource(fn))
    src=src.replace(f"def {fn.__name__}(", f"def {name}(capC=0, delta=0, qbox=None, *, _a=None, **_k):\n    pass\ndef _{name}_impl(",1) if False else src
    head=src.split("\n",1)[0]; args=head[head.index("(")+1:head.rindex(")")]
    src=src.replace(head, f"def {name}({args}, capC=0, delta=0, qbox=None):",1)
    anchor='                if want>cur[k]+pend[k] and cur[k]+pend[k]<FMAX[k]:' if fn is S.sim_v6 else '                if want > cur[k] + pend[k] and cur[k] + pend[k] < S.FMAX[k]:'
    assert src.count(anchor)==1, name
    blk=CAP_BLOCK.replace("WANT",want_expr).replace("MAXB",repr(maxb)).replace("FMAXUP",fmax)
    blk=textwrap.indent(textwrap.dedent(blk),' '*20)
    src=src.replace(anchor, anchor+"\n"+blk.rstrip("\n"),1)
    return src
NS={}
src_v6=build(S.sim_v6,"sim_v6c","want",None,"FMAX['up']")
src_b6=build(B.sim_b6,"sim_b6c","want",3,"S.FMAX['up']")
g6=dict(vars(S)); exec(src_v6,g6); sim_v6c=g6["sim_v6c"]
gb=dict(vars(B)); exec(src_b6,gb); sim_b6c=gb["sim_b6c"]
if __name__=="__main__": print(src_v6[:3000])

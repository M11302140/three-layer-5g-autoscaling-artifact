#!/usr/bin/env python3
"""spec §4.140 A: export S7Prior (s7core, CtlGen's prior = S7Prior(prior_traces.json, v8sim11.cfg_prior cfg)) R2 tables for the daemon.
D (integer UE count) and cap_up 5 make h = (n_up-1)*5 - D an integer, so p_exceed(k, D, h) and e_t(D, h) are tabulated per 10-UE bucket over
integer h in [HLO, HHI] (edges verified to be the limits 1.0 / 0.0 and the e_t index clamp). Self-check: table-based r2_ok == S7Prior.r2_ok
for D 0..45, n_up 2..8, n_wk 1..4, w in {0, 25, 100, 400, 1600}. Writes hhro-daemon-s4p/internal/hbo/prior_r2.json."""
import timeit  # noqa
import sys, json, math, hashlib
Q='/home/user/experiment/qsim'; sys.path[:0]=[Q,Q+'/s7',Q+'/r67band']; import os; os.chdir(Q)
import v8sim11 as V, s7core as C7, run as RB
cfg,_=V.cfg_prior(); P=C7.S7Prior(RB.LIB,cfg)
HLO,HHI=-60,60; NB=6
tab=dict(p_exceed={},e_t=[],h_lo=HLO,h_hi=HHI,bucket_ue=10,n_buckets=NB,cap_up=cfg.cap_up,spw=cfg.spw,cores_up=cfg.cores["up"],cores_wk=cfg.cores["wk"],
         l_up=C7.horizon(cfg,"up"),l_wk=C7.horizon(cfg,"wk"),xmax=C7.XMAX,
         source="experiment/qsim/r72hw/export_r2.py from s7core.S7Prior(prior_traces.json sha256 7d5a247b..., v8sim11.cfg_prior)")
for k in ("up","wk"):
    tab["p_exceed"][k]=[[P.p_exceed(k,10*b,h) for h in range(HLO,HHI+1)] for b in range(NB)]
    for b in range(NB): assert tab["p_exceed"][k][b][0]==1.0 and tab["p_exceed"][k][b][-1]==0.0, (k,b)
tab["e_t"]=[[P.e_t(10*b,h) for h in range(HLO,HHI+1)] for b in range(NB)]
for b in range(NB): assert tab["e_t"][b][0]==P.e_t(10*b,-1) and tab["e_t"][b][-1]==P.e_t(10*b,C7.XMAX)
# buckets beyond NB-1 must not occur (D <= 45 -> db <= 4); check db mapping
assert all(P.db(D)<NB for D in range(0,50))
def r2_tab(D,n_up,n_wk,w):
    h=(n_up-1)*tab["cap_up"]-D; hi=int(math.floor(h)); hi=min(HHI,max(HLO,hi)); b=int(D//10)
    bb=(n_up-1)<=(n_wk-1)*tab["spw"]; rate=tab["cores_up"]+(tab["cores_wk"] if bb else 0.0); L=tab["l_wk"] if bb else tab["l_up"]
    pe=tab["p_exceed"]["wk" if bb else "up"][b][hi-HLO]; et=tab["e_t"][b][hi-HLO]
    return rate*et/60.0-w*(pe*L/60.0)>0
bad=0; n=0
for D in range(0,46):
    for nu in range(2,9):
        for nw in range(1,5):
            for w in (0,25,100,400,1600):
                n+=1; bad+=r2_tab(D,nu,nw,w)!=P.r2_ok(cfg,D,nu,nw,w)
print("self-check cases",n,"mismatches",bad); assert bad==0
out='/home/user/hhro-daemon-s4p/internal/hbo/prior_r2.json'; s=json.dumps(tab); open(out,'w').write(s)
print("wrote",out,len(s),"bytes sha256",hashlib.sha256(s.encode()).hexdigest()[:16])
